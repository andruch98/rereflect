"""Failed attempts remain recoverable, but do not poison coherent follow-up context."""
from uuid import uuid4

from src.models.conversation_message import ConversationMessage


def test_failed_first_question_returns_persisted_chat_and_retry_is_not_duplicated(flow):
    request_id = str(uuid4())
    payload = {'question': 'What are the main staff themes?', 'request_id': request_id, 'period': {'preset': 'all_time'}}
    flow['model']['finish_reason'] = 'length'
    first = flow['client'].post('/api/v1/ask-genius/questions', headers=flow['headers'], json=payload)
    assert first.status_code == 502
    detail = first.json()['detail']
    chat = detail['conversation_id']
    assert detail['period'] == payload['period'] and detail['request_id'] == request_id
    assert detail['reason'] == 'InvalidModelAnswer'
    same = flow['client'].post('/api/v1/ask-genius/questions', headers=flow['headers'], json=payload)
    assert same.status_code == 502 and same.json()['detail']['conversation_id'] == chat
    assert len(flow['calls']) == 1  # Known failed request ID never generates again.
    history = flow['client'].get(f'/api/v1/ask-genius/conversations/{chat}', headers=flow['headers']).json()['messages']
    assert history[0]['status'] == 'failed'
    assert 'raw_request' not in history[0]
    failed = flow['db'].query(ConversationMessage).first()
    assert failed.raw_request['validation_reason'] == 'incomplete_output'
    assert failed.raw_request['finish_reason'] == 'length'
    flow['model'].pop('finish_reason')
    retry = flow['ask'](payload['question'], conversation_id=chat, period=payload['period'])
    assert retry.status_code == 200 and retry.json()['conversation_id'] == chat
    assert len(flow['calls']) == 2
    assert sum(m['content'] == payload['question'] for m in flow['calls'][1]) == 1


def test_followups_retain_completed_source_references_but_skip_failed_prompts(flow):
    row = flow['rows'][0]
    flow['model']['evidence'] = [{'review_id': row.id, 'kind': 'review', 'excerpt': 'Repairs took two weeks.'}]
    first = flow['ask']('Show supporting reviews.', period={'preset': 'all_time'})
    assert first.status_code == 200
    chat = first.json()['conversation_id']
    flow['model']['finish_reason'] = 'length'
    assert flow['ask']('A failed question', conversation_id=chat).status_code == 502
    flow['model'].pop('finish_reason')
    flow['model']['evidence'] = []
    followup = flow['ask']('Who wrote that?', conversation_id=chat)
    assert followup.status_code == 200
    history = flow['calls'][-1][2:-1]
    assert not any(m['content'] == 'A failed question' for m in history)
    assistant = next(m['content'] for m in history if m['role'] == 'assistant')
    assert 'Repairs took two weeks.' in assistant and str(row.id) in assistant
