"""No live model calls: scope, original data preservation, history and continuation behavior."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

import pytest
from src.services.survey_catalog import bind_questionnaire

ROOT = Path(__file__).parents[4]
spec = importlib.util.spec_from_file_location('four_survey_runner',
    ROOT / 'experiments/ask_genius/round2_acceptance/runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def synthetic_answer(messages):
    context = json.loads(messages[1]['content'].split('\n', 1)[1])
    answer = {'answer': 'Synthetic test answer.', 'evidence': []}
    if context.get('survey_findings_required'):
        answer['survey_findings'] = [{'survey_id': r['survey_id'],
            'question_ids': [q['id'] for q in r['questions'] if q.get('answer') not in (None, '')],
            'finding': 'Synthetic coverage only.'} for r in context['surveys']]
    return answer


def rows():
    result = []
    for n, (test_id, kind) in enumerate(runner.COHORT.items()):
        context = {'community_name': 'Test community', 'event_type': kind, 'resident_id': test_id,
                   'request_description': 'Synthetic door lock', 'ticket_id': test_id}
        snapshot = bind_questionnaire(context, kind)
        answers = {}
        for q in snapshot['questions']:
            if q['type'] == 'rating':
                answers[q['id']] = 2 if n == 0 else 4
            elif q['type'] == 'text':
                answers[q['id']] = 'Fixture comment ' + test_id
            else:
                options = q.get('options', [])
                answers[q['id']] = next(iter(options)) if isinstance(options, dict) else options[0]['value']
        result.append({'event_id': 'boomsay-email-test-' + test_id, 'event_type': kind,
            'public_id': f'00000000-0000-4000-8000-{n+1:012d}', 'is_simulated': True,
            'completed_at': datetime(2026, 11, 5, 14, tzinfo=timezone.utc), 'ticket_id': test_id,
            'request_description': 'Synthetic door lock', 'questionnaire_snapshot': snapshot,
            'context_snapshot': context, 'answers': answers, 'status': 'submitted',
            'submitted_at': datetime(2026, 11, 5, 15, n, tzinfo=timezone.utc)})
    return result


@pytest.mark.parametrize('problem', ['missing', 'wrong_type', 'unsubmitted', 'wrong_day', 'real_record'])
def test_reject_wrong_cohort(problem):
    values = rows()
    if problem == 'missing': values.pop()
    if problem == 'wrong_type': values[0]['event_type'] = 'move_out_completed'
    if problem == 'unsubmitted': values[0]['status'] = 'pending'
    if problem == 'wrong_day': values[0]['submitted_at'] = datetime(2026, 11, 4, 15)
    if problem == 'real_record': values[0]['is_simulated'] = False
    with pytest.raises(ValueError): runner.validate_rows(values)


def test_read_only_selection_and_exact_copy(tmp_path):
    values = rows()
    unrelated = deepcopy(values[0])
    unrelated.update(event_id='boomsay-email-test-old', public_id='00000000-0000-4000-8000-000000000099')
    engine, db, user = runner.isolated_database('Test community', [*values, unrelated], 1)
    # Persist a fixture copy to exercise the real reader with an unrelated fifth survey.
    disk_url = 'sqlite:///' + str(tmp_path / 'fixture.db')
    disk_engine = runner.create_engine(disk_url)
    runner.Base.metadata.create_all(disk_engine)
    with engine.connect() as source, disk_engine.begin() as target:
        for table in runner.Base.metadata.sorted_tables:
            data = [dict(r) for r in source.execute(table.select()).mappings()]
            if data: target.execute(table.insert(), data)
    disk_engine.dispose()
    before = (tmp_path / 'fixture.db').read_bytes()
    name, copied = runner.read_cohort(disk_url, 1)
    assert (tmp_path / 'fixture.db').read_bytes() == before
    assert len(copied) == 4
    for original, clone in zip(values, sorted(copied, key=lambda x: x['submitted_at'])):
        for key in ('answers', 'context_snapshot', 'questionnaire_snapshot', 'public_id'):
            assert clone[key] == original[key]
    assert all('token' not in row and 'draft_answers' not in row for row in copied)
    with pytest.raises(ValueError): runner.read_cohort(disk_url, 999)
    db.close(); engine.dispose()


@pytest.mark.parametrize("answer_errors", [False, True])
@pytest.mark.parametrize("summary_check", [False, True])
def test_packaged_source_with_fake_provider(tmp_path, answer_errors, summary_check):
    """Exercise the actual SDK/bootstrap/main path; HTTP goes only to a local fixture."""
    import base64
    import hashlib
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import os
    import subprocess
    import sys
    from threading import Thread

    path = ROOT / 'experiments/ask_genius/round2_acceptance/build-package.py'
    spec = importlib.util.spec_from_file_location('four_survey_build', path)
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    package = tmp_path / 'package'
    builder.build(package, summary_check=summary_check)
    original, db, user = runner.isolated_database('Test community', rows(), 1)
    url = 'sqlite:///' + str(tmp_path / 'source.db')
    target_engine = runner.create_engine(url)
    runner.Base.metadata.create_all(target_engine)
    with original.connect() as source, target_engine.begin() as target:
        for table in runner.Base.metadata.sorted_tables:
            data = [dict(r) for r in source.execute(table.select()).mappings()]
            if data: target.execute(table.insert(), data)
    target_engine.dispose(); db.close(); original.dispose()
    before = (tmp_path / 'source.db').read_bytes()
    requests = []
    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(request)
            response = {'id': 'fixture-response', 'object': 'chat.completion', 'created': 1,
                'model': 'offline-synthetic', 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': json.dumps(synthetic_answer(request['messages']))}}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
            if answer_errors and len(requests) == 2:
                response['choices'][0]['message'].update(content=None, refusal='Captured fixture refusal.')
            if answer_errors and len(requests) == 5:
                response['choices'][0]['message']['content'] = json.dumps({
                    'answer': 'Invalid selection fixture.', 'selections': [{'kind': 'survey', 'survey_id': 'bad'}]})
            data = json.dumps(response).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    env = {**os.environ, 'DATABASE_URL': url, 'JWT_SECRET': 'offline-fixture-not-production',
        'BOOMSAY_REVIEW_PREVIEW': 'true', 'BOOMSAY_PREVIEW_ORGANIZATION_ID': '1',
        'ASK_GENIUS_ENABLED': 'true', 'ASK_GENIUS_PROVIDER': 'openai_compatible',
        'ASK_GENIUS_MODEL': 'offline-synthetic', 'ASK_GENIUS_API_KEY': 'never-a-live-key',
        'ASK_GENIUS_BASE_URL': f'http://127.0.0.1:{server.server_port}/v1', 'NO_PROXY': '127.0.0.1'}
    # This fixture talks exclusively to the local fake provider. The test runtime
    # has a SOCKS proxy whose optional client dependency is not installed.
    for name in ('ALL_PROXY', 'all_proxy'):
        env.pop(name, None)
    archive = (package / 'pr12-source.zip').read_bytes()
    payload = {'archive': base64.b64encode(archive).decode(), 'sha256': hashlib.sha256(archive).hexdigest()}
    try:
        run = subprocess.run([sys.executable, str(package / 'bootstrap.py')], input=json.dumps(payload),
            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=45)
    finally:
        server.shutdown(); server.server_close(); thread.join()
    if capture := os.getenv('BOOMSAY_TEST_CAPTURE'):
        with Path(capture).open('a') as out:
            out.write(json.dumps({'mocked': True, 'test': 'packaged source + local fake HTTP provider',
                'requests': requests, 'stdout': run.stdout, 'stderr': run.stderr, 'returncode': run.returncode}) + '\n')
    assert run.returncode == (1 if answer_errors else 0), run.stdout + run.stderr
    events = [json.loads(line) for line in run.stdout.splitlines()]
    assert events[-1]['kind'] == 'complete' and len(requests) == (5 if summary_check else 14)
    assert events[0]['questions'] == [list(q) for q in (runner.SUMMARY_QUESTIONS if summary_check else runner.QUESTIONS)]
    if summary_check:
        assert not (package / 'survey-email-test.py').exists()
    assert events[-1]['failed_questions'] == (2 if answer_errors else 0)
    if answer_errors:
        results = [e for e in events if e['kind'] == 'result']
        assert [e['index'] for e in results if e['status'] == 'failed'] == ([2, 5] if summary_check else [3, 6])
        assert results[2 if summary_check else 6]['prior_failed_questions_in_chat'] == ([2] if summary_check else [3, 6])
        assert results[-1]['prior_failed_questions_in_chat'] == []
        assert all('Captured fixture refusal.' not in json.dumps(r['messages']) for r in requests)
        assert results[1 if summary_check else 2]['raw_response']['choices'][0]['message']['refusal']
    assert events[0]['source']['application_commit']
    assert requests[0]['messages'][0]['content'].count(runner.service.SURVEY_ANSWER_EXAMPLES) == 1
    assert len(events[0]['evidence']['surveys']) == 4
    assert (tmp_path / 'source.db').read_bytes() == before
    assert 'never-a-live-key' not in run.stdout
    assert all(r['max_completion_tokens'] == runner.service.completion_budget(r['messages']) for r in requests)
    if summary_check:
        assert all(r['max_completion_tokens'] == 1840 for r in requests)
        assert len(requests[0]['messages']) == len(requests[-2]['messages']) == len(requests[-1]['messages']) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [None, 'provider', 'validation', 'truncated'])
async def test_actual_route_and_history_continues(monkeypatch, failure):
    values = rows()
    engine, db, user = runner.isolated_database('Test community', values, 1)
    monkeypatch.setenv('BOOMSAY_REVIEW_PREVIEW', 'true')
    monkeypatch.setenv('BOOMSAY_PREVIEW_ORGANIZATION_ID', '1')
    monkeypatch.setenv('ASK_GENIUS_ENABLED', 'true')
    monkeypatch.setenv('ASK_GENIUS_PROVIDER', 'openai')
    monkeypatch.setenv('ASK_GENIUS_MODEL', 'offline-synthetic')
    monkeypatch.setenv('ASK_GENIUS_API_KEY', 'never-send-fixture')
    calls, events = [], []
    monkeypatch.setattr(runner, 'emit', events.append)
    async def generate(messages, config):
        calls.append(deepcopy(messages))
        if failure == 'provider': raise RuntimeError('NEVER LOG PRIVATE EXCEPTION')
        output = synthetic_answer(messages)
        if failure == 'validation':
            output['evidence'] = [{'survey_id': 'not-in-authorized-cohort', 'kind': 'survey'}]
        content = json.dumps(output)
        return runner.service.AnswerResult(content, {'fixture': True, 'content': content},
            10, 5, 'length' if failure == 'truncated' else 'stop')
    monkeypatch.setattr(runner.service, 'generate_answer', generate)
    code = await runner.execute_questions(db, user)
    # Preserve attempts before assertions, including failures while developing this test.
    import os
    if capture := os.getenv('BOOMSAY_TEST_CAPTURE'):
        with Path(capture).open('a') as out:
            out.write(json.dumps({'mocked': True, 'failure_case': failure, 'events': events,
                'model_messages': calls, 'assessment': 'Assertions follow; not live accuracy.'}, default=str) + '\n')
    assert code == (1 if failure else 0), events
    assert len(calls) == 14, events
    result = [e for e in events if e['kind'] == 'result']
    assert result[0]['response']['answer'].startswith('4 completed')
    for messages in calls:
        assert messages[0]['content'].count(runner.service.SURVEY_ANSWER_EXAMPLES) == 1
        evidence = json.loads(messages[1]['content'].split('\n', 1)[1])
        assert {r['survey_id'] for r in evidence['surveys']} <= {r['public_id'] for r in values}
    assert len(result) == 15 and events[-1]['kind'] == 'complete'
    assert events[-1]['failed_questions'] == (14 if failure else 0)
    assert result[-1]['prior_failed_questions_in_chat'] == []
    if failure:
        assert result[2]['prior_failed_questions_in_chat'] == [2]
        assert result[1]['continued_after_failure'] is True
    if not failure:
        assert len(calls[-2]) == len(calls[-1]) == 3  # fresh, no previous chat replies
        assert len(calls[1]) > 3  # actual follow-up history
        assert result[2]['raw_response'] and result[2]['tokens_in'] == 10
    assert 'NEVER LOG PRIVATE EXCEPTION' not in json.dumps(events)
    db.close(); engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize('error', [runner.HTTPException(403, 'Forbidden'), RuntimeError('SECRET_SENTINEL_93')])
async def test_access_or_unexpected_errors_still_stop(monkeypatch, error):
    engine, db, user = runner.isolated_database('Test community', rows(), 1)
    events, calls = [], []
    async def fail(*args, **kwargs):
        calls.append(1)
        raise error
    monkeypatch.setattr(runner.routes, 'ask_question', fail)
    monkeypatch.setattr(runner, 'emit', events.append)
    assert await runner.execute_questions(db, user) == 1
    assert len(calls) == 1 and events[-1]['continued_after_failure'] is False
    assert 'SECRET_SENTINEL_93' not in json.dumps(events)
    db.close(); engine.dispose()


def test_report_distinguishes_completed_failures_and_context_gaps():
    spec = importlib.util.spec_from_file_location('continuing_launcher',
        ROOT / 'experiments/ask_genius/round2_acceptance/run-local.py')
    launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)
    events = [dict(kind='result', index=1, status='failed', tokens_in=1, tokens_out=2,
                   failure={'reason': 'empty'}, raw_response={'choices': [{'message': {'refusal': 'Fixture text'}}]}),
              dict(kind='result', index=2, status='completed', tokens_in=1, tokens_out=2,
                   response={'answer': 'Later answer'}, prior_failed_questions_in_chat=[1]),
              dict(kind='complete', questions=2, failed_questions=1)]
    text = launcher.report(events, [('a', 'First'), ('a', 'Second')], {'application_commit': 'fixture'}, 1)
    assert 'completed with answer failures' in text
    assert 'refusal (NOT an accepted application answer)' in text
    assert 'earlier questions in this chat failed: 1' in text
    assert 'Later answer' in text
