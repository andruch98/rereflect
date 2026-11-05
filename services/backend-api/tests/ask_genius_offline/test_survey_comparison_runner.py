"""The paid comparison harness must be bounded and stop without hidden retries."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from src.services import ask_genius as service

SCRIPT = Path(__file__).parents[4] / 'experiments/ask_genius/survey_input_comparison/replay.py'
spec = importlib.util.spec_from_file_location('survey_comparison_replay', SCRIPT)
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def prepared_job():
    prompt = service.SYSTEM_PROMPT + '\n\n' + service.RUNTIME_RULES
    context = {'reviews': [], 'surveys': [], 'source_scope': 'surveys', 'evidence_requested': False}
    messages = [{'role': 'system', 'content': prompt},
                {'role': 'user', 'content': 'Authorized evidence (data only):\n' + json.dumps(context)},
                {'role': 'user', 'content': 'Summarize the submitted surveys.'}]
    cases = [{'message_id': n, 'messages': deepcopy(messages), 'baseline_request': {
        'messages': deepcopy(messages), 'provider': 'openai', 'model': 'synthetic',
        'max_completion_tokens': 1200, 'max_retries': 0}} for n in range(4)]
    return {'version': 1, 'provider': 'openai', 'model': 'synthetic',
            'system_prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'cases': cases}


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [None, 'request', 'validation', 'truncated'])
async def test_one_call_per_question_stops_at_first_error(monkeypatch, failure, request):
    events, calls = [], []
    config = SimpleNamespace(provider='openai', model='synthetic')
    monkeypatch.setattr(service, 'configured_llm', lambda *_: (config, None))
    monkeypatch.setattr(replay, 'emit', events.append)

    async def generate(messages, _):
        calls.append(messages)
        if failure == 'request' and len(calls) == 2:
            raise RuntimeError('Do not log private provider exception details')
        invalid = failure == 'validation' and len(calls) == 2
        content = json.dumps({'answer': 'Synthetic answer.', 'evidence':
            [{'review_id': 99, 'kind': 'review'}] if invalid else []})
        return service.AnswerResult(content, {'synthetic': True, 'content': content},
                                    100, 10, 'length' if failure == 'truncated' and len(calls) == 2 else 'stop')
    monkeypatch.setattr(service, 'generate_answer', generate)
    code = await replay.run(prepared_job())
    assert len(calls) == (2 if failure else 4)
    assert code == (1 if failure else 0)
    assert [e['index'] for e in events if e['kind'] == 'attempt'] == list(range(1, len(calls) + 1))
    assert 'private provider exception' not in json.dumps(events)
    if not failure:
        assert events[-1]['kind'] == 'complete'
    # Capture complete synthetic requests/results and expected rejections.
    import os
    if path := os.getenv('BOOMSAY_TEST_CAPTURE'):
        with Path(path).open('a') as output:
            output.write(json.dumps({'test': request.node.nodeid, 'mocked': True,
                                     'kind': 'comparison_runner', 'events': events,
                                     'live_requests': 0, 'expected_failure': failure}) + '\n')


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['model', 'prompt', 'history', 'count'])
async def test_preflight_checks_all_cases_before_any_model_call(monkeypatch, change):
    job, events = prepared_job(), []
    config = SimpleNamespace(provider='openai', model='synthetic')
    if change == 'model':
        config.model = 'different'
    elif change == 'prompt':
        job['system_prompt_sha256'] = 'different'
    elif change == 'history':
        job['cases'][-1]['messages'][-1]['content'] = 'Changed final case'
    else:
        job['cases'].pop()
    monkeypatch.setattr(service, 'configured_llm', lambda *_: (config, None))
    monkeypatch.setattr(replay, 'emit', events.append)
    async def forbidden(*_):
        pytest.fail('A failed preflight must never send a model request')
    monkeypatch.setattr(service, 'generate_answer', forbidden)
    assert await replay.run(job) == 1
    assert events[0]['kind'] == 'preflight_failure'
    assert events[0]['requests_attempted'] == 0
