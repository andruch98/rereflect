"""Verify source follow-ups and quoted date language through the real survey route."""
import json
from datetime import date

import pytest

from src.services import ask_genius as service
from test_surveys import ALL, PERIOD, survey_flow


@pytest.mark.parametrize('question', ['Show the sources', 'Yes, please'])
def test_survey_source_offer_uses_only_prior_authorized_question(survey_flow, question):
    f = survey_flow
    row = f['create_survey'](comment='I paid yesterday.')
    f['create_survey']('resolved', resident='other-resident', comment='Lighting issue.')
    ref = {'kind': 'survey', 'survey_id': row.public_id, 'question_id': 'maintenance_comment'}
    f['model'].update(answer='The resident wrote “I paid yesterday.” Would you like to see the original surveys?',
                      survey_context=[ref])
    first = f['ask']('Did the maintenance surveys mention “I paid yesterday”?', period=PERIOD)
    assert first.status_code == 200, first.text
    assert first.json()['period'] == PERIOD
    assert not first.json()['structured_data']['sources']
    result = f['ask'](question, conversation_id=first.json()['conversation_id']).json()
    assert [(s['survey_id'], s['question_id']) for s in result['structured_data']['sources']] == [
        (row.public_id, 'maintenance_comment')]
    assert len(f['calls']) == 1


@pytest.mark.parametrize('question', ["Don't show the sources", "Don’t give me any sources", "No sources please"])
def test_explicitly_suppress_sources(question):
    assert not service.evidence_requested(question, [])


def test_yes_to_unrelated_offer_keeps_source_cards_hidden():
    history = [{'role': 'assistant', 'content': 'Would you like me to summarize the surveys?\n\n'
                'Attached source cards: [{"kind":"survey"}]'}]
    assert not service.evidence_requested('Yes please', history)


def test_yesterday_filters_submitted_records_on_the_property_day(survey_flow):
    f = survey_flow  # Fixture property date is October 27 in New York.
    wanted = f['create_survey'](submitted='2026-10-27T03:59:59+00:00').public_id
    f['create_survey'](submitted='2026-10-27T04:00:00+00:00', resident='today')
    f['model'].update(answer='One survey was submitted yesterday.')
    result = f['ask']('Summarize surveys submitted yesterday.', period=ALL)
    assert result.status_code == 200, result.text
    assert result.json()['period'] == {'preset': 'custom', 'start_date': '2026-10-26', 'end_date': '2026-10-26'}
    evidence = json.loads(f['calls'][0][1]['content'].split('\n', 1)[1])
    assert [r['survey_id'] for r in evidence['surveys']] == [wanted]
    assert not f['user'].ask_genius_default_period

def test_exact_maintenance_count_with_explicit_day_needs_no_model(survey_flow):
    f = survey_flow
    f['create_survey'](submitted='2026-10-27T03:59:59+00:00')
    f['create_survey'](event_type='lease_month_3', submitted='2026-10-27T03:59:59+00:00')
    f['create_survey'](submitted='2026-10-27T04:00:00+00:00')
    result = f['ask']('How many maintenance surveys were submitted yesterday?', period=ALL)
    assert result.status_code == 200, result.text
    assert result.json()['answer'].startswith('1 completed maintenance survey response(s)')
    assert result.json()['period'] == {'preset': 'custom', 'start_date': '2026-10-26', 'end_date': '2026-10-26'}
    assert not f['calls']


def test_empty_authorized_prior_selection_never_promises_attached_sources(survey_flow):
    f = survey_flow
    f['create_survey']('resolved')
    first = f['ask']('Which submissions say the issue is still unresolved?', period=ALL).json()
    followup = f['ask']('Show the sources.', conversation_id=first['conversation_id']).json()
    assert followup['answer'] == 'No matching original survey answers are available for this selection.'
    assert followup['structured_data']['sources'] == []
    assert not f['calls']


@pytest.mark.parametrize('question', [
    'How many reviews have a posting date in November 2026?',
    'Which reviews are we leaving out when we look only at this month?',
    'Did anybody post about parking this month?',
])
def test_explicit_month_overrides_all_history_and_excludes_undated_reviews(flow, monkeypatch, question):
    monkeypatch.setattr('src.services.ask_genius_periods.community_today', lambda: date(2026, 11, 6))
    rows = flow['rows']
    rows[0].review_date, rows[1].review_date = date(2026, 11, 2), date(2026, 11, 4)
    flow['db'].commit()
    first = flow['ask']('Summarize the reviews.', period=ALL).json()
    response = flow['ask'](question, period=ALL, conversation_id=first['conversation_id'])
    assert response.status_code == 200, response.text
    assert response.json()['period'] == {'preset': 'custom', 'start_date': '2026-11-01', 'end_date': '2026-11-06'}
    evidence = json.loads(flow['calls'][-1][1]['content'].split('\n', 1)[1])
    assert {r['review_id'] for r in evidence['reviews']} == {rows[0].id, rows[1].id}
    assert evidence['excluded_undated_review_count'] == 1


def test_named_month_survey_count_uses_only_submitted_records(survey_flow, monkeypatch):
    monkeypatch.setattr('src.services.ask_genius_periods.community_today', lambda: date(2026, 11, 6))
    f = survey_flow
    f['create_survey'](submitted='2026-11-01T03:59:59+00:00')  # Oct 31 at the property
    f['create_survey'](submitted='2026-11-01T04:00:00+00:00')
    response = f['ask']('How many maintenance surveys were submitted in November 2026?', period=ALL)
    assert response.status_code == 200, response.text
    assert response.json()['answer'].startswith('1 completed maintenance survey response(s)')
    assert not f['calls']
