"""Replay the reported failure and reject meaningful errors. No provider calls."""
import json

import pytest

from src.models.conversation_message import ConversationMessage
from src.services import ask_genius as service
from src.api.routes.ask_genius import failure_message
from test_surveys import survey_flow  # shared real survey ingestion fixture


QUESTION = 'What did residents say in surveys about their maintenance experience?'
COMMENT = 'it is still leaaking a lot and i nearly fell with the watr'
# Reconstructed from the pasted diagnostic, not independently captured provider bytes.
ANSWER = ('The single maintenance survey response reports the following:\n\n'
          '- "Overall, how would you rate the maintenance service for a fictional leaking kitchen faucet?": Rated 2 — Bad.\n'
          '- "Is the issue fully resolved?": Answered "No, still unresolved."\n'
          '- "How would you rate our maintenance team’s response time to your request?": Answered "Not sure."\n'
          f'- Resident comment: "{COMMENT}"\n\n'
          'This indicates the resident is dissatisfied with the maintenance service, especially since the leaking persists and poses a safety risk.')


@pytest.mark.parametrize('break_style', ['escaped', 'literal', 'continuation'])
def test_reported_summary_recovers_and_original_answer_followup_stays_scoped(survey_flow, break_style):
    f = survey_flow
    row = f['create_survey'](comment=COMMENT)
    f['create_survey']('resolved', resident='unrelated', comment='Everything is repaired.')
    raw = json.dumps({'answer': ANSWER, 'evidence': [{'kind': 'survey', 'survey_id': row.public_id}], 'selections': []})
    if break_style != 'escaped':
        raw = raw.replace('\\n', '\n' if break_style == 'literal' else '\\\n')
    f['model']['raw'] = raw
    result = f['ask'](QUESTION, period={'preset': 'all_time'})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body['answer'] == ANSWER
    assert body['structured_data']['sources'] == []
    assert body['structured_data']['survey_match_ids'] == [row.public_id]
    request = f['db'].query(ConversationMessage).filter_by(role='user').one()
    assert request.raw_response['content'] == raw  # never rewrite the audit original
    assert 'unrequested_evidence_hidden' in request.raw_request['normalizations']
    assert ('json_string_line_breaks' in request.raw_request['normalizations']) == (break_style != 'escaped')
    followup = f['ask']('Show each answer.', conversation_id=body['conversation_id'])
    assert followup.status_code == 200
    sources = followup.json()['structured_data']['sources']
    assert [s['survey_id'] for s in sources] == [row.public_id]
    assert sources[0]['survey']['questions'][-1]['answer'] == COMMENT
    assert len(f['calls']) == 1  # no paid retry or model call for evidence navigation


@pytest.mark.parametrize('raw', ['{"answer": "unfinished', '{"answer": "bad \\q"}',
                                '{"answer": "a "quote" without escapes"}'])
def test_ambiguous_or_incomplete_json_is_not_guessed_and_has_specific_reason(flow, raw):
    flow['model']['raw'] = raw
    result = flow['ask'](period={'preset': 'all_time'})
    assert result.status_code == 502
    assert 'couldn’t read' in result.json()['detail']['message']
    assert 'narrower' not in result.text
    failed = flow['db'].query(ConversationMessage).filter_by(role='user').one()
    assert failed.raw_request['validation_reason'] == 'invalid_json'
    assert failed.raw_response['content'] == raw
    assert len(flow['calls']) == 1
    history = flow['client'].get('/api/v1/ask-genius/conversations/' + result.json()['detail']['conversation_id'], headers=flow['headers']).json()
    assert history['messages'][0]['error_message'] == result.json()['detail']['message']
    assert 'raw_response' not in history['messages'][0] and 'raw_request' not in history['messages'][0]


@pytest.mark.parametrize('extra', [
    {'evidence': [{'kind': 'review', 'review_id': 99999}]},
    {'evidence': [{'kind': 'review', 'review_id': 1, 'excerpt': 'Invented quote.'}]},
    {'selections': [{'topic': 'Invented topic'}]},
])
def test_unrequested_but_invalid_references_still_fail(flow, extra):
    flow['model'].update(extra)
    result = flow['ask'](period={'preset': 'all_time'})
    assert result.status_code == 502
    failed = flow['db'].query(ConversationMessage).filter_by(role='user').one()
    assert failed.raw_request['validation_reason'] in {'unknown_source', 'source_mismatch', 'unknown_topic'}
    assert 'couldn’t match' in result.json()['detail']['message']
    assert len(flow['calls']) == 1


def test_valid_unrequested_review_references_are_hidden_but_available_to_followups(flow):
    row = flow['rows'][0]
    flow['model'].update(evidence=[{'kind': 'review', 'review_id': row.id, 'topic': 'Maintenance'}])
    result = flow['ask'](period={'preset': 'all_time'})
    assert result.status_code == 200
    body = result.json()
    assert body['structured_data']['sources'] == []
    assert body['structured_data']['review_context'][0]['review_id'] == row.id
    flow['model'].update(evidence=[])
    assert flow['ask']('Explain that concern.', conversation_id=body['conversation_id']).status_code == 200
    assert 'Repairs took two weeks.' in flow['calls'][-1][3]['content']


@pytest.mark.parametrize('ending', ['\n', '\r\n'])
@pytest.mark.parametrize('slash', ['', '\\'])
def test_only_string_line_breaks_are_normalized_without_changing_quotes_or_backslashes(ending, slash):
    text = 'Quoted "resident" and literal \\n and path C:\\temp\nNext line'
    raw = json.dumps({'answer': text}, indent=2).replace('temp\\nNext', 'temp' + slash + ending + 'Next')
    result, _ = service.validate_answer(raw, {'reviews': []}, False)
    assert result == text


@pytest.mark.parametrize('field,expected', [
    ({'answer': 'x' * (service.MAX_ANSWER_CHARS + 1)}, 'answer_too_long'),
    ({'answer': ''}, 'empty_answer'),
    ({'answer': ['not a string']}, 'invalid_structure'),
])
def test_failures_have_safe_specific_diagnostics(flow, field, expected):
    flow['model'].update(field)
    result = flow['ask'](period={'preset': 'all_time'})
    assert result.status_code == 502
    row = flow['db'].query(ConversationMessage).filter_by(role='user').one()
    assert row.raw_request['validation_reason'] == expected
    assert row.raw_request['validation_detail']
    assert 'narrower' not in result.text


def test_diagnostics_never_echo_arbitrary_exception_text():
    details = service.validation_failure(ValueError('private-provider-secret'))
    assert 'private-provider-secret' not in json.dumps(details)


def test_duplicate_survey_reference_cannot_hide_invalid_excerpt(survey_flow):
    f = survey_flow
    row = f['create_survey']()
    ref = {'kind': 'survey', 'survey_id': row.public_id}
    f['model'].update(evidence=[ref, {**ref, 'excerpt': 'Invented quotation.'}])
    assert f['ask'](QUESTION, period={'preset': 'all_time'}).status_code == 502


@pytest.mark.parametrize('status,phrase', [(401, 'administrator'), (403, 'administrator'), (429, 'limiting requests'), (503, 'wait a moment')])
def test_provider_messages_explain_known_cause_without_exposing_provider_body(status, phrase):
    assert phrase in failure_message({'error': 'ProviderHTTPError', 'http_status': status})


def test_hidden_survey_evidence_retains_topic_and_relevant_question(survey_flow):
    f = survey_flow
    row = f['create_survey']()
    f['create_survey']('resolved', comment='Excellent repair.')
    f['model'].update(answer='- **Ongoing leak:** The faucet still leaks.', evidence=[{
        'survey_id': row.public_id, 'kind': 'survey', 'topic': 'Ongoing leak',
        'question_id': 'maintenance_comment', 'excerpt': 'The faucet still leaks after the visit.'}])
    first = f['ask'](QUESTION, period={'preset': 'all_time'}).json()
    assert first['structured_data']['sources'] == []
    followup = f['ask']('Show each answer.', conversation_id=first['conversation_id']).json()
    assert followup['answer'] == first['answer']
    assert len(followup['structured_data']['sources']) == 1
    assert followup['structured_data']['sources'][0]['question_id'] == 'maintenance_comment'
    assert followup['structured_data']['sources'][0]['topic'] == 'Ongoing leak'
    assert len(f['calls']) == 1


def test_unrequested_foreign_survey_reference_is_rejected(survey_flow):
    from src.models.organization import Organization
    f = survey_flow
    f['create_survey']()
    foreign = Organization(name='Other community')
    f['db'].add(foreign); f['db'].commit()
    other = f['create_survey'](org=foreign, resident='other-private')
    f['model'].update(evidence=[{'kind': 'survey', 'survey_id': other.public_id}])
    assert f['ask'](QUESTION, period={'preset': 'all_time'}).status_code == 502


def test_valid_json_is_not_rewritten():
    answer = 'A quote: "hello", escaped backslash \\n, then a real newline\nand tab\t.'
    raw = json.dumps({'answer': answer})
    normalizations = []
    actual, _ = service.validate_answer(raw, {'reviews': []}, False, normalizations=normalizations)
    assert actual == answer
    assert normalizations == []
