"""Survey shares use frozen, allowlisted originals and existing ownership checks."""
import json
import os
from pathlib import Path

import pytest

from test_surveys import ALL, survey_flow
from src.models.conversation_message import ConversationMessage
from src.models.organization import Organization
from src.services import ask_genius_surveys as surveys

BASE = '/api/v1/ask-genius'


def share(f, chat):
    result = f['client'].post(f'{BASE}/conversations/{chat}/share', headers=f['headers'])
    assert result.status_code == 201, result.text
    path = f'{BASE}/shared/{result.json()["token"]}'
    public = f['client'].get(path)
    assert public.status_code == 200, public.text
    return path, public.json()


def capture(request, **values):
    if path := os.getenv('BOOMSAY_TEST_CAPTURE'):
        with Path(path).open('a') as output:
            output.write(json.dumps({'test': request.node.nodeid, 'kind': 'survey_share',
                                     'live_requests': 0, **values}) + '\n')


def test_shared_mixed_evidence_preserves_questions_without_private_context(survey_flow, request):
    f = survey_flow
    row = f['create_survey']()
    original = surveys.original_record(row)
    f['model'].update(answer='- **Maintenance:** The survey reports an unresolved leak.', evidence=[
        {'kind': 'survey', 'survey_id': row.public_id, 'question_id': 'issue_resolution', 'topic': 'Maintenance'},
        {'kind': 'review', 'review_id': f['rows'][0].id}])
    answer = f['ask']('Show supporting surveys and reviews.', period=ALL)
    assert answer.status_code == 200, answer.text
    chat = answer.json()['conversation_id']
    path, data = share(f, chat)
    sources = data['messages'][1]['structured_data']['sources']
    survey = next(s for s in sources if s.get('kind') == 'survey')
    assert survey['survey_id'] != row.public_id
    assert survey['question_id'] == 'issue_resolution'
    assert survey['topic'] == 'Maintenance'
    assert survey['survey']['questions'] == [{k: q[k] for k in ('id', 'text', 'answer_label')} for q in original['questions']]
    assert next(s for s in sources if s['kind'] == 'review')['review']['original_review'] == f['rows'][0].text
    text = json.dumps(data)
    for forbidden in [row.token, row.public_id, 'resident_email', 'resident_name', 'resident_id',
                      'unit_number', 'context_snapshot', 'raw_request', 'survey_context', '/surveys/', 'href']:
        assert forbidden not in text
    capture(request, private_answer=answer.json(), public_snapshot=data, original_questions=original['questions'])
    row.answers = {**row.answers, 'maintenance_comment': 'Later private change'}
    f['db'].commit()
    f['model'].update(answer='A later answer.', evidence=[])
    assert f['ask']('What else?', conversation_id=chat).status_code == 200
    assert f['client'].get(path).json() == data
    assert f['client'].delete(f'{BASE}/conversations/{chat}', headers=f['headers']).status_code == 204
    assert f['client'].get(path).json() == data


def test_legacy_block_flags_and_forged_survey_metadata_do_not_leak(survey_flow, request):
    f = survey_flow
    local = f['create_survey']()
    draft = f['create_survey'](submitted=None)
    foreign_org = Organization(name='Other'); f['db'].add(foreign_org); f['db'].commit()
    foreign = f['create_survey'](org=foreign_org, resident='other-resident', comment='FOREIGN SECRET')
    result = f['ask']('Summarize surveys.', period=ALL).json()
    message = f['db'].get(ConversationMessage, result['message_id'])
    message.structured_data = {**message.structured_data,
        'sharing_unavailable_reason': 'Legacy survey sharing block',
        'sources': [{'kind': 'survey', 'source': 'survey', 'survey_id': row.public_id,
                     'href': 'https://attacker.invalid', 'survey': {'questions': ['FORGED SECRET']}}
                    for row in (local, draft, foreign)]}
    message.raw_request = {'private': 'AUDIT SECRET'}
    f['db'].commit()
    chat = result['conversation_id']
    assert f['client'].get(f'{BASE}/conversations/{chat}', headers=f['headers']).json()['sharing_unavailable_reason'] is None
    _, public = share(f, chat)
    sources = public['messages'][1]['structured_data']['sources']
    assert len(sources) == 1
    assert len(sources[0]['survey']['questions']) == 4
    for forbidden in ['FOREIGN SECRET', 'FORGED SECRET', 'AUDIT SECRET', 'attacker.invalid', draft.public_id, foreign.public_id]:
        assert forbidden not in json.dumps(public)
    capture(request, public_snapshot=public, assessment='Only owned submitted source rebuilt from originals; forged/draft/foreign fields excluded.')


@pytest.mark.parametrize('invalid', [{'question_id': 'invented'}, {'excerpt': 'Invented resident quote'}])
def test_invalid_attached_question_or_excerpt_cannot_publish_a_share(survey_flow, invalid, request):
    f = survey_flow
    row = f['create_survey']()
    result = f['ask']('Summarize surveys.', period=ALL).json()
    message = f['db'].get(ConversationMessage, result['message_id'])
    message.structured_data = {**message.structured_data, 'sources': [
        {'kind': 'survey', 'survey_id': row.public_id, **invalid}]}
    f['db'].commit()
    response = f['client'].post(f'{BASE}/conversations/{result["conversation_id"]}/share', headers=f['headers'])
    assert response.status_code == 422
    capture(request, source=invalid, rejection=response.json(), expected_rejection=True)
