"""Regression coverage for ordinary survey-type changes in a real saved chat.

Routes/auth/storage/evidence are real; narrative model outputs are deliberate mocks.
These tests assess selected original records, not live-model factual accuracy.
"""
import pytest

from test_surveys import ALL, PERIOD, context, mixed_surveys, survey_flow


def nine_surveys(flow):
    rows = mixed_surveys(flow)
    flow['create_survey']('resolved', resident='fictional-extra-1')
    flow['create_survey']('partially_resolved', resident='fictional-extra-2')
    flow['model'].update(answer='The selected original survey answers are available.', evidence=[])
    return rows


def assert_selection(flow, response, types, expected_count):
    assert response.status_code == 200, response.text
    metadata = response.json()['structured_data']
    assert set(metadata['survey_event_types']) == set(types)
    assert metadata['survey_counts']['submission_count'] == expected_count
    payload = context(flow)
    assert payload['survey_calculated']['submission_count'] == expected_count
    assert {row['event_type'] for row in payload['surveys']} == set(types or [
        'move_in_completed', 'maintenance_completed', 'lease_month_3', 'lease_month_6',
        'lease_month_9', 'lease_renewed', 'move_out_completed'])
    return payload


@pytest.mark.parametrize('question,kind,count', [
    ('what does the move in completed say', 'move_in_completed', 1),
    ('what does the maintenance completed say', 'maintenance_completed', 3),
    ('what about the 3 month', 'lease_month_3', 1),
    ('what does the 6-month say', 'lease_month_6', 1),
    ('what does the 9-month renewal planning say', 'lease_month_9', 1),
    ('what does the lease renewal say', 'lease_renewed', 1),
    ('what does the move out completed say', 'move_out_completed', 1),
])
def test_ordinary_named_type_change_retrieves_that_types_originals(survey_flow, question, kind, count):
    f = survey_flow
    rows = nine_surveys(f)
    initial = 'Show the 6-month surveys.' if kind == 'maintenance_completed' else 'Show unresolved maintenance surveys.'
    first = f['ask'](initial, period=ALL)
    response = f['ask'](question, conversation_id=first.json()['conversation_id'])
    payload = assert_selection(f, response, [kind], count)
    original = next(row for row in payload['surveys'] if row['survey_id'] == rows[kind].public_id)
    assert original['saved_analysis'] == {'status': 'not_generated'}
    assert {q['id']: q['answer'] for q in original['questions']} == rows[kind].answers


@pytest.mark.parametrize('question', [
    'which are the bad surveys, summarize them in a list',
    'which surveys are low-rated?',
    'list the bad surveys',
])
def test_unqualified_survey_evaluation_leaves_the_previous_type(survey_flow, question):
    f = survey_flow
    nine_surveys(f)
    first = f['ask']('Show the 6-month surveys.', period=ALL)
    response = f['ask'](question, conversation_id=first.json()['conversation_id'])
    assert_selection(f, response, [], 9)


def test_short_followups_keep_type_and_explicit_type_beats_broad_wording(survey_flow):
    f = survey_flow
    nine_surveys(f)
    first = f['ask']('what do the maintenance surveys say?', period=ALL)
    chat = first.json()['conversation_id']
    for question in ['what does the bad say', 'what issue is it', 'what about response time?',
                     'which are the bad maintenance surveys?']:
        response = f['ask'](question, conversation_id=chat)
        assert_selection(f, response, ['maintenance_completed'], 3)
    response = f['ask']('What do all surveys say about maintenance?', conversation_id=chat)
    assert_selection(f, response, [], 9)


def test_broad_type_reset_preserves_selected_period(survey_flow):
    f = survey_flow
    nine_surveys(f)
    f['create_survey'](submitted='2026-10-28T12:00:00+00:00')
    first = f['ask']('Show the 6-month surveys.', period=PERIOD)
    response = f['ask']('which are the bad surveys, summarize them in a list',
                       conversation_id=first.json()['conversation_id'])
    assert_selection(f, response, [], 9)
    assert response.json()['period'] == PERIOD


def test_users_fourteen_turn_sequence_selects_correct_types(survey_flow):
    f = survey_flow
    nine_surveys(f)
    questions = [
        ('How many survey responses did we receive during this period?', [], 9),
        ('break it down by type', [], 9),
        ('what do the maintenance surveys say?', ['maintenance_completed'], 3),
        ('what does the bad say', ['maintenance_completed'], 3),
        ('what issue is it', ['maintenance_completed'], 3),
        ('what does the move in completed say', ['move_in_completed'], 1),
        ('what does the lease renewal survey say?', ['lease_renewed'], 1),
        ('what about the 3 month survey?', ['lease_month_3'], 1),
        ('what about move out?', ['move_out_completed'], 1),
        ('what about 6-month?', ['lease_month_6'], 1),
        ('which are the bad surveys, summarize them in a list', [], 9),
        ('what are the main improvements suggested by all surveys?', [], 9),
        ('do you think we charge good rent?', [], 9),
        ('are we doing a good job?', [], 9),
    ]
    chat = None
    for index, (question, types, count) in enumerate(questions):
        before = len(f['calls'])
        response = f['ask'](question, **({'conversation_id': chat} if chat else {'period': ALL}))
        assert response.status_code == 200, response.text
        chat = response.json()['conversation_id']
        metadata = response.json()['structured_data']
        assert set(metadata['survey_event_types']) == set(types), question
        assert metadata['survey_counts']['submission_count'] == count, question
        assert response.json()['period'] == ALL
        if len(f['calls']) > before:
            assert_selection(f, response, types, count)
        if index == 0:
            assert response.json()['answer'] == '9 completed survey response(s) in All available history.'
            assert metadata['survey_counts']['survey_type_counts']['maintenance_completed'] == 3
