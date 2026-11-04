"""Approved questionnaires traverse the same real private survey routes."""
import json
from pathlib import Path
from urllib.parse import urlsplit
import pytest
from src.models.survey import SurveyInstance, SurveyOccurrence

FIXTURES = json.loads((Path(__file__).parents[4] / 'experiments/lifecycle_surveys/fixtures.json').read_text())


def create(flow, case):
    event = {**case['event'], 'community_id': flow['community'].id}
    response = flow['client'].post('/api/v1/surveys/simulate', headers=flow['headers'], json=event)
    assert response.status_code == 200, response.text
    detail = response.json()
    path = '/api/v1/resident-surveys/' + urlsplit(detail['invitation']['survey_url']).path.split('/')[-1]
    return detail, path, event


@pytest.mark.parametrize('case', FIXTURES, ids=lambda c:c['event']['event_type'])
def test_each_type_draft_submission_evidence_and_replay(survey_flow, case):
    f = survey_flow
    detail, path, event = create(f, case)
    kind = event['event_type']
    assert detail['questionnaire']['event_type'] == kind
    assert len(detail['questionnaire']['questions']) == 4
    assert detail['context']['event_type'] == kind
    assert detail['context']['event_occurred_at'] == event['occurred_at']
    assert '{community_name}' not in detail['questionnaire']['title']
    if kind != 'maintenance_completed':
        assert detail['context'].get('ticket_id') is None
        assert 'maintenance experience' not in detail['invitation']['text']
    final = case['final_answers']; partial = dict(list(final.items())[:1])
    assert f['client'].put(path+'/draft',json={'answers':partial}).status_code==200
    assert f['client'].get(path).json()['draft_answers']==partial
    assert f['client'].get(path).json()['status']=='draft'
    submitted=f['client'].post(path+'/submit',json={'answers':final})
    assert submitted.status_code==200,submitted.text
    assert submitted.json()['answers']==final
    assert submitted.json()['status']=='submitted'
    assert f['client'].put(path+'/draft',json={'answers':{}}).json()['answers']==final
    assert f['client'].post(path+'/submit',json={'answers':{}}).json()['answers']==final
    again,same_path,_=create(f,case)
    assert same_path==path and again['public_id']==detail['public_id']
    manager=f['client'].get('/api/v1/surveys/'+detail['public_id'],headers=f['headers']).json()
    assert manager['questionnaire']==detail['questionnaire'] and manager['answers']==final
    assert f['client'].get('/api/v1/surveys/'+detail['public_id'],headers=f['other_headers']).status_code==404
    changed={**event,'event_type':'lease_month_6' if kind!='lease_month_6' else 'lease_month_3'}
    for key in ('ticket_id','request_description'): changed.pop(key,None)
    assert f['client'].post('/api/v1/surveys/simulate',headers=f['headers'],json=changed).status_code==409


def test_dashboard_filters_and_legacy_links(survey_flow):
    f=survey_flow; records=[create(f,case) for case in FIXTURES]
    assert f['client'].get('/api/v1/surveys',headers=f['headers']).json()['total']==7
    for detail,path,event in records:
        listing=f['client'].get('/api/v1/surveys',params={'event_type':event['event_type']},headers=f['headers']).json()
        assert listing['total']==1 and listing['surveys'][0]['public_id']==detail['public_id']
        assert f['client'].get(path).json()['questionnaire']['event_type']==event['event_type']
    assert f['client'].get('/api/v1/surveys?event_type=invented',headers=f['headers']).status_code==422
    maintenance=next(item for item in records if item[2]['event_type']=='maintenance_completed')
    with f['sessions']() as db:
        row=db.query(SurveyInstance).filter_by(public_id=maintenance[0]['public_id']).one()
        old_context={k:v for k,v in row.context_snapshot.items() if k not in ('survey_type_label','event_occurred_at','event_type')}
        row.context_snapshot=old_context;db.commit()
    restored=f['client'].get(maintenance[1]).json()
    assert restored['context']['event_type']=='maintenance_completed'
    assert restored['context']['event_occurred_at']==old_context['ticket_completed_at']
    with f['sessions']() as db:
        assert db.query(SurveyInstance).filter_by(public_id=maintenance[0]['public_id']).one().context_snapshot==old_context


@pytest.mark.parametrize('change',[{'event_type':'invented'},{'event_type':'maintenance_completed'},
 {'ticket_id':'FAKE-MAINTENANCE'},{'employee_name':'Fake technician'},
 {'resident_email':'real@example.com'},{'is_simulated':False},{'occurred_at':'not-a-date'}])
def test_wrong_context_unknown_events_and_live_targets_rejected(survey_flow,change):
    event={**FIXTURES[0]['event'],'community_id':survey_flow['community'].id,**change}
    assert survey_flow['client'].post('/api/v1/surveys/simulate',headers=survey_flow['headers'],json=event).status_code==422
    with survey_flow['sessions']() as db: assert db.query(SurveyOccurrence).count()==0


@pytest.mark.parametrize('case',FIXTURES,ids=lambda c:c['event']['event_type'])
def test_each_type_rejects_missing_and_foreign_answers(survey_flow,case):
    _,path,_=create(survey_flow,case)
    for answers in ({},{'made_up_question':'yes'}):
        assert survey_flow['client'].post(path+'/submit',json={'answers':answers}).status_code==422
    assert survey_flow['client'].get(path).json()['status']=='pending'


def test_fictional_cli_is_idempotent_and_never_sends(survey_flow,monkeypatch):
    from src.survey_lifecycle_demo import prepare
    f=survey_flow
    with f['sessions']() as db:
        first=prepare(db,f['community'].id,'lease_month_9','review')
        expected=(first.public_id,first.token)
        replay=prepare(db,f['community'].id,'lease_month_9','review')
        assert (replay.public_id,replay.token)==expected
        assert replay.invitation.status=='simulated' and replay.context_snapshot.get('ticket_id') is None
        monkeypatch.setenv('BOOMSAY_SURVEY_SIMULATION','false')
        with pytest.raises(ValueError,match='Enable'): prepare(db,f['community'].id,'lease_month_9','another')
