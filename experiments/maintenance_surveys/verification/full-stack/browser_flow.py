"""Full UI -> real main API -> PostgreSQL -> mocked-provider integration check.

Requires the isolated Compose overlay. No Playwright routes or auth overrides.
Writes a report to the path supplied as argv[1]. Never targets an installed preview.
"""
import json
import subprocess
import sys
import time
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[4]
REPORT = Path(sys.argv[1])
PROJECT = 'boomsay-survey-full-20261101'
COMPOSE = ['docker', '--host=unix:///var/run/docker.sock', 'compose', '-p', PROJECT,
           '-f', str(ROOT/'experiments/maintenance_surveys/compose.yml'),
           '-f', str(Path(__file__).with_name('compose.mock.yml'))]
API = 'http://127.0.0.1:53205'; WEB = 'http://127.0.0.1:53204'
http = requests.Session(); http.trust_env = False
resume = '--resume' in sys.argv[2:]
steps = json.loads(REPORT.read_text())['steps'] if resume else []

def record(step, result, **details):
    steps.append({'step': step, 'result': result, **details})
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({'project': PROJECT, 'steps': steps}, indent=2)+'\n')
    print(step, result, flush=True)

def fixture(action):
    return json.loads(subprocess.check_output(COMPOSE+['exec', '-T', 'api', 'python', '-c',
        Path(__file__).with_name('sentinels.py').read_text(), action], text=True))

for attempt in range(60):
    try:
        if http.get(API+'/health', timeout=2).status_code == 200: break
    except requests.RequestException: pass
    time.sleep(1)
else: raise RuntimeError('Full main API did not become healthy')
before = fixture('seed')
record('full_stack_health', 'pass', api_http=200, sentinel_review_count=before['review_count'])

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
    manager = browser.new_context(viewport={'width':1440, 'height':1000})
    page = manager.new_page(); errors=[]
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(WEB+'/login')
    page.get_by_label('Email', exact=True).fill('manager@survey-demo.example.com')
    page.get_by_label('Password', exact=True).fill('fictional-survey-demo-login')
    with page.expect_response(lambda r: r.url == API+'/api/v1/auth/login') as login:
        page.get_by_role('button', name='Sign in', exact=True).click()
    assert login.value.status == 200, login.value.text()
    expect(page.get_by_label('Time period')).to_be_enabled(timeout=30000)
    token = page.evaluate('localStorage.getItem("access_token")')
    assert token
    auth={'Authorization':'Bearer '+token}
    me=http.get(API+'/api/v1/auth/me',headers=auth).json()
    assert me['organization_id']==1
    record('actual_browser_login', 'pass', login_http=200, community_id=1)
    prior=http.post(API+'/api/v1/ask-genius/questions',headers=auth,json={
        'question':'Show the completed maintenance surveys for this period.', 'period':{'preset':'all_time'}})
    assert prior.status_code==200, prior.text
    prior_id=prior.json()['conversation_id']
    prior_chat=http.get(API+'/api/v1/ask-genius/conversations/'+prior_id,headers=auth).json()

    if not resume:
        event=json.loads((ROOT/'experiments/maintenance_surveys/fixtures/maintenance-completed.json').read_text())
        response=http.post(API+'/api/v1/surveys/simulate',headers=auth,json=event)
        assert response.status_code==200, response.text
        survey=response.json(); survey_id=survey['public_id']
        invitation=survey['invitation']; url=invitation['survey_url']
        assert url.startswith(WEB+'/survey/') and invitation['status']=='simulated' and invitation['is_simulated']
        assert survey['status']=='pending' and not survey['submitted_at']
        record('generic_event_and_immediate_invitation','pass', http=200, survey_id=survey_id,
            event_id=event['event_id'],ticket=event['ticket_id'],invitation_status=invitation['status'],resident_url=url)
        replay=http.post(API+'/api/v1/surveys/simulate',headers=auth,json=event).json()
        assert replay['public_id']==survey_id and replay['invitation']['survey_url']==url
        record('event_replay','pass',same_survey_and_link=True)

        resident=browser.new_context(viewport={'width':390,'height':844})
        form=resident.new_page(); form.on('pageerror',lambda e:errors.append(str(e)))
        form.goto(url)
        expect(form.get_by_role('heading',name='Tell us about your maintenance experience')).to_be_visible()
        assert form.evaluate('localStorage.getItem("access_token")') is None
        form.locator('input[name="maintenance_overall"][value="2"]').check()
        form.locator('input[name="issue_resolution"][value="unresolved"]').check()
        form.locator('input[name="maintenance_response_time"][value="not_sure"]').check()
        comment='The kitchen faucet still leaks after the ticket was marked completed.'
        form.get_by_role('textbox').fill(comment)
        expect(form.get_by_role('status')).to_contain_text('Draft saved',timeout=15000)
        form.reload()
        expect(form.locator('input[name="issue_resolution"][value="unresolved"]')).to_be_checked()
        expect(form.get_by_role('textbox')).to_have_value(comment)
        with form.expect_response(lambda r:r.url.endswith('/submit')) as saved:
            form.get_by_role('button',name='Submit survey',exact=True).click()
        assert saved.value.status==200
        expect(form.get_by_role('heading',name='Thank you for your feedback')).to_be_visible()
        final=saved.value.json()
        assert final['status']=='submitted' and final['submitted_at'] and final['answers']['issue_resolution']=='unresolved'
        record('resident_draft_reload_and_submit','pass',submit_http=200,submitted_at=final['submitted_at'],answers=final['answers'])

        page.goto(WEB+'/surveys')
        expect(page.get_by_role('heading',name='Surveys',exact=True)).to_be_visible()
        expect(page.get_by_text('Jamie Example',exact=True)).to_be_visible()
        row=page.get_by_role('row').filter(has_text='Jamie Example')
        expect(row).to_contain_text('204')
        expect(row).to_contain_text('DEMO-WO-1001')
        expect(row).to_contain_text('submitted')
        expect(page.get_by_text('Simulated invitation — no email sent',exact=True)).to_be_visible()
        page.get_by_role('link',name='View answers').click()
        expect(page.get_by_role('heading',name='Original questions and answers')).to_be_visible()
        expect(page.get_by_text('2 — Bad',exact=True)).to_be_visible()
        expect(page.get_by_text('No, still unresolved',exact=True)).to_be_visible()
        expect(page.get_by_text('Not sure',exact=True)).to_be_visible()
        expect(page.get_by_text(comment,exact=True)).to_be_visible()
        original=http.get(API+'/api/v1/surveys/'+survey_id,headers=auth)
        assert original.status_code==200
        assert len(original.json()['questionnaire']['questions'])==4
        assert original.json()['answers']==final['answers']
        import re
        for question in original.json()['questionnaire']['questions']:
            expect(page.get_by_role('heading',name=re.compile('^'+re.escape(question['rendered_text'])))).to_be_visible()
        record('dashboard_and_original_answers','pass',detail_http=200,questions=original.json()['questionnaire']['questions'])
        page.screenshot(path=str(REPORT.parent/'full-stack-answers.png'),full_page=True)

    else:
        event_step=next(s for s in steps if s['step']=='generic_event_and_immediate_invitation')
        final=next(s for s in steps if s['step']=='resident_draft_reload_and_submit')
        survey_id=event_step['survey_id'];url=event_step['resident_url']
        comment=final['answers']['maintenance_comment']
        resident=browser.new_context(viewport={'width':390,'height':844})
        form=resident.new_page();form.goto(url)
        expect(form.get_by_role('heading',name='Thank you for your feedback')).to_be_visible()
        record('resume_preserved_submission','pass',survey_id=survey_id)

    page.goto(WEB+'/ask-genius')
    expect(page.get_by_label('Time period')).to_be_enabled()
    page.get_by_label('Time period').select_option('all_time')
    conversation_id=None
    for question in ['Show the completed maintenance surveys for this period.',
                     'What did residents say about their maintenance experience?',
                     'Show the original answers behind that.']:
        page.get_by_role('textbox').last.fill(question)
        with page.expect_response(lambda r:r.url==API+'/api/v1/ask-genius/questions') as answered:
            page.get_by_role('button',name='Send question').click()
        assert answered.value.status==200,answered.value.text()
        payload=answered.value.json(); conversation_id=payload['conversation_id']
        assert payload['structured_data']['source_scope']=='surveys'
        assert payload['structured_data']['survey_counts']['submission_count']==1
        record('ask_genius_question','pass',question=question,answer=payload['answer'],conversation_id=conversation_id,
               survey_counts=payload['structured_data']['survey_counts'])
    evidence=page.get_by_role('link',name='View original answers',exact=False).last
    expect(evidence).to_have_attribute('href','/surveys/'+survey_id)
    page.screenshot(path=str(REPORT.parent/'full-stack-ask.png'),full_page=True)
    evidence.click()
    expect(page.get_by_role('heading',name='Original questions and answers')).to_be_visible()
    expect(page.get_by_text(comment,exact=True)).to_be_visible()
    assert page.url==WEB+'/surveys/'+survey_id
    record('ask_evidence_navigation','pass',href='/surveys/'+survey_id)
    share=http.post(API+'/api/v1/ask-genius/conversations/'+conversation_id+'/share',headers=auth)
    assert share.status_code==422
    assert http.get(API+'/api/v1/surveys/'+survey_id).status_code in (401,403)
    record('private_access_and_sharing','pass',share_http=422,anonymous_manager_access='blocked')
    observations=http.get('http://127.0.0.1:53206/observations').json()['calls']
    assert len(observations)==2, observations
    for call in observations:
        rows=call['context']['surveys']
        assert len(rows)==1 and rows[0]['survey_id']==survey_id
        assert len(rows[0]['questions'])==4
        assert any(q['id']=='issue_resolution' and q['answer']=='unresolved' for q in rows[0]['questions'])
    record('actual_mock_provider_boundary','pass',http_model_calls=2,live_model_calls=0,original_questions_per_call=4)

    subprocess.run(COMPOSE+['restart','api'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    for attempt in range(60):
        try:
            if http.get(API+'/health',timeout=2).status_code==200:break
        except requests.RequestException:pass
        time.sleep(1)
    else:raise RuntimeError('API restart failed')
    form.reload()
    expect(form.get_by_role('heading',name='Thank you for your feedback')).to_be_visible()
    reloaded=http.get(API+'/api/v1/surveys/'+survey_id,headers=auth).json()
    assert reloaded['answers']==final['answers'] and reloaded['submitted_at']==final['submitted_at']
    after=fixture('snapshot');assert before==after,(before,after)
    retained=http.get(API+'/api/v1/ask-genius/conversations/'+prior_id,headers=auth).json()
    assert retained['messages']==prior_chat['messages']
    record('restart_and_prior_data_preservation','pass',survey_unchanged=True,review_settings_credentials_unchanged=True,prior_chat_unchanged=True)
    assert not errors,errors
    record('browser_errors','pass',page_errors=errors)
    browser.close()
record('complete_flow','pass',production_app='src.api.main:app',auth_overrides=False,application_route_stubs=False)
