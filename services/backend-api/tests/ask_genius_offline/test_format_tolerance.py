"""Real-output replay plus safe syntax normalization. No model accuracy claim."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from src.services import ask_genius as service, ask_genius_surveys as surveys

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/summary-check-20261105.json').read_text())


def sample():
    evidence = deepcopy(FIXTURE['evidence'])
    evidence['survey_findings_required'] = True
    raw = FIXTURE['results'][4]['raw_response']['choices'][0]['message']['content']
    payload = json.loads(raw)
    payload['survey_findings'] = payload.pop('survey_findings_required')
    return evidence, payload


@pytest.mark.parametrize('index', range(5))
def test_original_paid_outputs_replay_without_new_calls(index):
    evidence = deepcopy(FIXTURE['evidence'])
    evidence['survey_findings_required'] = True
    raw = FIXTURE['results'][index]['raw_response']['choices'][0]['message']['content']
    notes = []
    if index == 3:
        with pytest.raises(ValueError, match='cover the supplied cohort'):
            service.validate_answer(raw, evidence, False, normalizations=notes)
    else:
        answer, _ = service.validate_answer(raw, evidence, False, normalizations=notes)
        assert answer == json.loads(raw)['answer'].strip()
        assert ('survey_findings_field_alias' in notes) == (index in (0, 1, 4))
    # Q1 and Q3 remain factually incomplete. Parsing success does not approve their prose.


def test_absent_optional_answer_can_be_referenced_without_inventing_an_answer():
    evidence, payload = sample()
    move_out = next(r for r in evidence['surveys'] if r['event_type'] == 'move_out_completed')
    note = next(n for n in payload['survey_findings'] if n['survey_id'] == move_out['survey_id'])
    note['question_ids'] = ['move_out_comment']
    note['finding'] = 'No optional comment submitted.'
    before = deepcopy(evidence)
    service.validate_answer(json.dumps(payload), evidence, False)
    assert evidence == before


def test_duplicates_are_harmless_only_when_identical():
    evidence, payload = sample()
    payload['survey_findings'][0]['question_ids'] *= 2
    payload['survey_findings'].append(deepcopy(payload['survey_findings'][0]))
    notes = []
    service.validate_answer(json.dumps(payload), evidence, False, normalizations=notes)
    assert 'duplicate_finding_question_reference' in notes
    assert 'duplicate_identical_finding' in notes
    payload['survey_findings'][-1]['finding'] = 'A different finding.'
    with pytest.raises(ValueError, match='Conflicting response fields'):
        service.validate_answer(json.dumps(payload), evidence, False)


def test_conflicting_alias_and_duplicate_json_fields_are_not_guessed():
    evidence, payload = sample()
    payload['survey_findings_required'] = []
    with pytest.raises(ValueError, match='Conflicting'):
        service.validate_answer(json.dumps(payload), evidence, False)
    with pytest.raises(ValueError, match='Duplicate JSON field'):
        service.validate_answer('{"answer":"one", "answer":"two"}', {'reviews': []}, False)


def test_null_lists_blank_optional_selector_and_redundant_kind():
    evidence, _ = sample()
    record = evidence['surveys'][0]
    evidence.pop('survey_findings_required')
    payload = {'answer': 'Original answers are available.', 'selections': None,
               'survey_context': [{'survey_id': record['survey_id'], 'topic': '', 'excerpt': ' '}]}
    context, notes = [], []
    service.validate_answer(json.dumps(payload), evidence, False, survey_context=context, normalizations=notes)
    assert context[0]['survey_id'] == record['survey_id']
    assert {'null_optional_list', 'blank_optional_selector', 'survey_reference_kind'} <= set(notes)


@pytest.mark.parametrize('field', ['answer', 'survey_findings'])
def test_resource_and_style_limits_are_distinct(field):
    evidence, payload = sample()
    if field == 'answer':
        payload[field] = 'A full sentence. ' * 300
    else:
        payload[field][0]['finding'] = 'A source note. ' * 30
    service.validate_answer(json.dumps(payload), evidence, False)


def test_display_labels_are_valid_only_for_the_actual_selected_answer():
    evidence, _ = sample()
    record = next(r for r in evidence['surveys'] if r['event_type'] == 'move_out_completed')
    label = 'Community conditions, such as noise or parking'
    result = surveys.source(record, excerpt=label, question_id='move_out_reason')
    assert result['excerpt'] == label
    assert surveys.source(record, excerpt='4 — Good', question_id='move_out_overall')['excerpt'] == '4 — Good'
    for quote, question in [(label, 'move_out_overall'), ('Buying a home', 'move_out_reason'), ('5 — Excellent', 'move_out_overall')]:
        with pytest.raises(ValueError):
            surveys.source(record, excerpt=quote, question_id=question)


@pytest.mark.parametrize('answer', ['See https://example.invalid', 'The resident wrote <broken>.',
                                    'Read [the source](https://example.invalid).'])
def test_safe_renderer_handles_markup_without_discarding_the_answer(answer):
    actual, sources = service.validate_answer(json.dumps({'answer': answer}), {'reviews': []}, True)
    assert actual == answer and sources == []  # Markdown grants no source access.


def test_survey_topic_format_is_a_display_label_not_a_reason_to_reject():
    evidence, _ = sample()
    evidence.pop('survey_findings_required')
    payload = {'answer': 'Maintenance concern.', 'evidence': [{'kind': 'survey',
        'survey_id': evidence['surveys'][0]['survey_id'], 'topic': '**Condition [reported]**'}]}
    answer, sources = service.validate_answer(json.dumps(payload), evidence, True)
    assert sources[0]['topic'] == '**Condition [reported]**'


def test_unknown_filter_fields_remain_errors_instead_of_silently_broadening():
    with pytest.raises(ValueError):
        service.validate_answer(json.dumps({'answer': 'Results.', 'selections': [{'unknown_filter': 'negative'}]}), {'reviews': []}, True)


def test_refusal_is_distinct_from_format_failure(flow, monkeypatch):
    from src.models.conversation_message import ConversationMessage
    async def refused(messages, config):
        return service.AnswerResult('', {'choices': [{'message': {'refusal': 'Declined.'}}]}, 10, 2, 'stop', refusal='Declined.')
    monkeypatch.setattr(service, 'generate_answer', refused)
    response = flow['ask'](period={'preset': 'all_time'})
    assert response.status_code == 502
    assert 'declined' in response.json()['detail']['message']
    assert flow['db'].query(ConversationMessage).filter_by(role='user').one().raw_request['validation_reason'] == 'model_refusal'


# Three saved gpt-4.1-mini replies to "What did the 3-month survey say about rent payments?"
RENT_SURVEY = 'dc0cc723-9ee2-4c65-bc74-36fca9e61232'
RENT_IDS = ['follow_up_requested', 'lease_month_3_comment']
RENT_EVIDENCE = {'reviews': [], 'surveys': [{'survey_id': RENT_SURVEY, 'questions': [
    {'id': RENT_IDS[0], 'answer_label': 'Yes'},
    {'id': RENT_IDS[1], 'answer': 'rent payments'},
]}]}


@pytest.mark.parametrize('attempt,answer', [
    (121, 'The 3-month survey response rates living overall as 5 — Excellent and community team help as 4 — Good. However, the resident requests follow-up on an unresolved concern, writing “rent payments” in the comment. The specific issue with rent payments is not explained in the submission.'),
    (122, 'The 3-month survey response rated overall living experience as 5 — Excellent and community team help as 4 — Good. However, it also indicated an unresolved concern that needs follow-up. The resident commented “rent payments,” implying some issue related to that but providing no further detail or explanation about the nature of the problem.'),
    (123, 'The 3-month survey response rated overall living as 5 — Excellent and the help from the community team as 4 — Good. Despite these positive ratings, the resident requested follow-up on an unresolved concern, writing "rent payments" in the comments. The specific issue with rent payments is not detailed.'),
])
def test_hosted_rent_replies(attempt, answer):
    ref = {'survey_id': RENT_SURVEY}
    if attempt != 122:
        ref['kind'] = 'survey'
    refs = ([{**ref, 'question_id': q} for q in RENT_IDS] if attempt == 123
            else [{**ref, 'question_ids': RENT_IDS}])
    raw = json.dumps({'answer': answer, 'evidence': [], 'selections': [],
                      'survey_selections': [] if attempt == 122 else {}, 'survey_context': refs})
    context = []
    text, sources = service.validate_answer(raw, RENT_EVIDENCE, False, survey_context=context)
    assert text == answer and not sources
    assert [r['question_id'] for r in context] == RENT_IDS


@pytest.mark.parametrize('group', [RENT_IDS + ['nonexistent'], [None], [''], []])
def test_malformed_or_unknown_grouped_reference_is_rejected(group):
    raw = json.dumps({'answer': 'Rent payments.', 'survey_context': {
        'survey_id': RENT_SURVEY, 'question_ids': group}})
    with pytest.raises(ValueError):
        service.validate_answer(raw, RENT_EVIDENCE, False)


def test_empty_selection_is_not_a_select_all_filter():
    raw = '{"answer":"Rent payments.","survey_selections":{}}'
    assert service.validate_answer(raw, RENT_EVIDENCE, True) == ('Rent payments.', [])
