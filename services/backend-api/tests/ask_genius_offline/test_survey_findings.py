"""Source-linked summary coverage: software checks, never a factual judge."""
from copy import deepcopy
import json

import pytest
from test_surveys import ALL, context, mixed_surveys, survey_flow
from src.services import ask_genius as service, ask_genius_surveys as surveys


@pytest.mark.parametrize('question', [
    'Which are the bad surveys? Summarize them in a list.',
    'What are the main improvements suggested by all surveys?',
    'Based on all the surveys, are we doing a good job?',
    'What do all surveys say?', 'Give me an overall summary.',
])
def test_broad_scope_requires_coverage(question):
    evidence = {'source_scope': 'surveys', 'surveys': [{'survey_id': 'fixture'}]}
    before = deepcopy(evidence)
    assert surveys.needs_findings(question, evidence)
    assert evidence == before  # This is not a new record filter.
    assert not surveys.needs_findings(question, {**evidence, 'source_scope': 'reviews'})
    assert not surveys.needs_findings(question, {**evidence, 'surveys': []})


@pytest.mark.parametrize('question', [
    'What does the move-in completed survey say?', 'What issue is it?',
    'What about the 9-month renewal planning survey?', 'Do you think we charge good rent?',
    'Show the original survey answers.', 'How many survey responses did we receive?',
])
def test_individual_questions_keep_existing_response_format(question):
    assert not surveys.needs_findings(question, {'source_scope': 'surveys', 'surveys': [{}]})


def evidence_and_findings(f):
    rows = mixed_surveys(f)
    original = service.build_authorized_evidence(f['org'].id, f['db'], service.Period(**ALL), 'surveys')
    original['survey_findings_required'] = True
    notes = [{'survey_id': row['survey_id'], 'question_ids': [q['id'] for q in row['questions']
              if q.get('answer') is not None and q.get('answer') != ''],
              'finding': 'Synthetic source-linked note; no accuracy judgment.'} for row in original['surveys']]
    return original, notes


@pytest.mark.parametrize('fault', ['missing_all', 'missing_one', 'duplicate', 'foreign', 'wrong_question',
                                   'empty_question_list', 'blank_finding'])
def test_bad_coverage_rejected_before_display(survey_flow, fault):
    f = survey_flow
    evidence, notes = evidence_and_findings(f)
    if fault == 'missing_all': notes = []
    elif fault == 'missing_one': notes.pop()
    elif fault == 'duplicate': notes[-1] = deepcopy(notes[0])
    elif fault == 'foreign': notes[0]['survey_id'] = '00000000-0000-4000-8000-999999999999'
    elif fault == 'wrong_question': notes[0]['question_ids'] = ['not-in-this-survey']
    elif fault == 'empty_question_list': notes[0]['question_ids'] = []
    elif fault == 'duplicate_question': notes[0]['question_ids'] *= 2
    elif fault == 'blank_finding': notes[0]['finding'] = '   '
    f['model']['raw'] = json.dumps({'survey_findings': notes, 'answer': 'Synthetic summary.'})
    response = f['ask']('Which are the bad surveys?', period=ALL)
    assert response.status_code == 502
    assert len(f['calls']) == 1  # No automatic retry.
    assert response.json()['detail']['reason'] == 'InvalidModelAnswer'
    assert context(f)['survey_findings_required'] is True


def test_findings_preserve_input_but_are_not_chat_history_or_display(survey_flow):
    f = survey_flow
    evidence, notes = evidence_and_findings(f)
    notes[0]['finding'] = 'INTERNAL_NOTE_SENTINEL'
    f['model'].update(survey_findings=notes, answer='Mixed findings need follow-up.', evidence=[])
    response = f['ask']('What are the main improvements suggested by all surveys?', period=ALL)
    assert response.status_code == 200, response.text
    assert 'INTERNAL_NOTE_SENTINEL' not in response.text
    payload = context(f)
    assert payload['survey_calculated'] == evidence['survey_calculated']
    assert payload['surveys'] == [surveys.model_record(r) for r in evidence['surveys']]
    assert f['calls'][-1][0]['content'].count(service.SURVEY_ANSWER_EXAMPLES) == 1
    assert service.completion_budget(f['calls'][-1]) == 1200 + 160 * len(notes)
    f['model'].pop('survey_findings')
    followup = f['ask']('What issue is it?', conversation_id=response.json()['conversation_id'])
    assert followup.status_code == 200
    assert 'INTERNAL_NOTE_SENTINEL' not in json.dumps(f['calls'][-1])
    assert service.completion_budget(f['calls'][-1]) == 1200
    assert [r['answers'] if 'answers' in r else [q['answer'] for q in r['questions']]
            for r in evidence['surveys']] == [[q['answer'] for q in r['questions']] for r in
            service.build_authorized_evidence(f['org'].id, f['db'], service.Period(**ALL), 'surveys')['surveys']]


def test_coverage_is_not_factual_verification(survey_flow):
    evidence, notes = evidence_and_findings(survey_flow)
    # Valid references cannot establish that arbitrary prose is true. Capture this
    # limitation explicitly; live factual acceptance remains a human assessment.
    answer, _ = service.validate_answer(json.dumps({'survey_findings': notes,
        'answer': 'All residents are happy.'}), evidence, False)
    assert answer == 'All residents are happy.'
