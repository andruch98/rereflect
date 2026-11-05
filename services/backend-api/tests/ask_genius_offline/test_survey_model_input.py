"""Compact model evidence must retain originals and leave source popups intact."""
from copy import deepcopy
import json

from test_surveys import ALL, context, mixed_surveys, survey_flow
from src.services import ask_genius as service, ask_genius_surveys as surveys
from src.services.ask_genius_periods import Period


def test_all_questionnaires_keep_answer_meaning_and_original_source_records(survey_flow):
    f = survey_flow
    rows = mixed_surveys(f)
    # Exercise an exact, unnormalized comment and a nonnumeric rating choice.
    maintenance = rows['maintenance_completed']
    maintenance.answers = {**maintenance.answers, 'maintenance_response_time': 'not_sure',
                           'maintenance_comment': 'STILL leaking — I nearly slipped!\nPlease help.'}
    f['db'].commit()
    evidence = surveys.build_evidence(f['org'].id, f['db'], Period(**ALL))
    originals = deepcopy(evidence)
    f['model'].update(answer='The original answers contain mixed feedback.', evidence=[])
    response = f['ask']('What do all surveys say?', period=ALL)
    assert response.status_code == 200, response.text
    payload = context(f)
    assert payload['survey_calculated'] == originals['survey_calculated']
    assert payload['survey_event_types'] == originals['survey_event_types']
    for original, sent in zip(originals['surveys'], payload['surveys']):
        assert sent['survey_id'] == original['survey_id']
        assert sent['context'] == original['context']
        assert 'maintenance_context' not in sent
        for key in ('submitted_at', 'template_id', 'template_version', 'event_type',
                    'survey_type_label', 'title', 'saved_analysis'):
            assert sent[key] == original[key]
        for before, after in zip(original['questions'], sent['questions']):
            for key in ('id', 'type', 'text', 'answer'):
                assert after[key] == before[key]
            assert after.get('answer_label', after['answer']) == before['answer_label']
            for key in ('options', 'special_options'):
                assert after.get(key) == before.get(key)
            if before['type'] == 'rating':
                assert after.get('rating_labels', sent.get('rating_labels')) == before['rating_labels']
            assert not {'rendered_text', 'original_text', 'required', 'max_length'} & after.keys()
        # The UI and reference validator still read the complete original record.
        source = surveys.source(original)
        assert source['survey'] == original
    assert surveys.build_evidence(f['org'].id, f['db'], Period(**ALL)) == originals
    comment = next(q for r in payload['surveys'] if r['event_type'] == 'maintenance_completed'
                   for q in r['questions'] if q['id'] == 'maintenance_comment')
    assert 'answer_label' not in comment  # No duplicate free-text answer.
    assert len(json.dumps(payload['surveys'])) < len(json.dumps(originals['surveys']))


def test_message_projection_changes_only_survey_representation(survey_flow):
    f = survey_flow
    mixed_surveys(f)
    evidence = {**surveys.build_evidence(f['org'].id, f['db'], Period(**ALL)),
                'source_scope': 'mixed', 'reviews': [{'review_id': 42, 'text': 'Original review.'}],
                'calculated': {'review_count': 1}, 'period': ALL}
    before = deepcopy(evidence)
    history = [{'role': 'assistant', 'content': 'Previous answer with its original wording.'}]
    messages = service.build_messages('Compare all feedback.', evidence, history,
                                      default_period=ALL)
    sent = json.loads(messages[1]['content'].split('\n', 1)[1])
    assert messages[0]['content'] == service.SYSTEM_PROMPT + '\n\n' + service.RUNTIME_RULES
    assert messages[2:] == [*history, {'role': 'user', 'content': 'Compare all feedback.'}]
    assert {k: sent[k] for k in evidence if k != 'surveys'} == {
        k: v for k, v in before.items() if k != 'surveys'}
    assert evidence == before
    assert sent['personal_preferences']['default_period'] == ALL
    assert sent['available_sources'] == ['reviews', 'analysis', 'surveys']


def test_different_question_scales_are_not_combined():
    record = {'context': {'request_description': 'Original issue'}, 'questions': [
        {'id': 'one', 'type': 'rating', 'text': 'One?', 'rating_labels': {'1': 'Poor'},
         'answer': 1, 'answer_label': '1 — Poor'},
        {'id': 'two', 'type': 'rating', 'text': 'Two?', 'rating_labels': {'1': 'Excellent'},
         'answer': 1, 'answer_label': '1 — Excellent'}]}
    before = deepcopy(record)
    compact = surveys.model_record(record)
    assert compact['questions'] == before['questions']
    compact['context']['request_description'] = 'Changed only in the copy'
    assert record == before


def test_compaction_does_not_discard_a_different_legacy_context():
    record = {'context': {'event_id': 'current'},
              'maintenance_context': {'event_id': 'different'}, 'questions': []}
    assert surveys.model_record(record) == record
