"""Survey evidence integration with real ingestion/routes/storage and mocked models."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from conftest import headers_for
from src.api.routes import surveys as survey_routes
from src.models.ask_genius_share import AskGeniusShare
from src.models.organization import Organization
from src.models.user import User
from src.services import ask_genius as service
from src.services import surveys

PERIOD = {'preset': 'custom', 'start_date': '2026-10-27', 'end_date': '2026-10-27'}
ALL = {'preset': 'all_time'}


@pytest.fixture
def survey_flow(flow, monkeypatch):
    flow['client'].app.include_router(survey_routes.router)
    monkeypatch.setenv('SURVEY_PUBLIC_BASE_URL', 'http://testserver')
    from src.services import email_service
    monkeypatch.setattr(email_service, '_send_email', lambda *args, **kwargs: pytest.fail('Live email forbidden'))
    sequence = []

    def create(resolution='unresolved', resident='fictional-r1', submitted='2026-10-27T12:00:00+00:00', org=None, comment='The faucet still leaks after the visit.', event_type='maintenance_completed'):
        index = len(sequence) + 1
        fixture = next(item for item in json.loads((Path(__file__).parents[4] /
            'experiments/lifecycle_surveys/fixtures.json').read_text()) if item['event']['event_type'] == event_type)
        data = {**fixture['event'], 'event_id': f'test-event-{index}', 'occurrence_id': f'test-occurrence-{index}',
                'community_id': (org or flow['org']).id, 'occurred_at': '2026-10-01T15:00:00-04:00',
                'resident_id': resident, 'resident_name': 'Fictional Resident',
                'resident_email': f'{resident}@example.invalid', 'unit_id': 'unit-201', 'unit_number': '201'}
        if event_type == 'maintenance_completed':
            data.update(ticket_id=f'fictional-ticket-{index}', request_description='a leaking kitchen faucet')
        event = survey_routes.SimulatedSurveyEvent(**data)
        row = surveys.ingest_simulated_event(flow['db'], event)
        sequence.append(row)
        if submitted:
            answers = {'maintenance_overall': 2, 'issue_resolution': resolution,
                'maintenance_response_time': 'not_sure', 'maintenance_comment': comment} if event_type == 'maintenance_completed' else fixture['final_answers']
            result = flow['client'].post(f'/api/v1/resident-surveys/{row.token}/submit', json={'answers': answers})
            assert result.status_code == 200, result.text
            row.submitted_at = datetime.fromisoformat(submitted)
            flow['db'].commit()
        return row

    flow['create_survey'] = create
    return flow


def context(flow):
    return json.loads(flow['calls'][-1][1]['content'].split('\n', 1)[1])


def test_survey_lists_use_submission_time_and_counts_distinguish_residents(survey_flow):
    f = survey_flow
    first = f['create_survey']()
    second = f['create_survey']('resolved', submitted='2026-10-27T13:00:00+00:00')
    third = f['create_survey']('partially_resolved', resident='fictional-r2')
    f['create_survey'](submitted=None)
    f['create_survey'](submitted='2026-10-27T03:59:59+00:00')  # Oct 26 New York
    f['create_survey'](submitted='2026-10-28T04:00:00+00:00')  # Oct 28 New York
    result = f['ask']('Show the completed maintenance surveys for this period.', period=PERIOD)
    assert result.status_code == 200, result.text
    body = result.json()
    assert '3 completed maintenance survey response(s)' in body['answer']
    assert not f['calls']
    metadata = body['structured_data']
    assert metadata['survey_counts']['submission_count'] == 3
    assert metadata['survey_counts']['distinct_resident_count'] == 2
    assert {source['survey_id'] for source in metadata['sources']} == {first.public_id, second.public_id, third.public_id}
    assert all(source['kind'] == 'survey' and 'review_id' not in source for source in metadata['sources'])


def test_unresolved_report_survives_completed_ticket_and_original_followup(survey_flow):
    f = survey_flow
    unresolved = f['create_survey']()
    f['create_survey']('resolved')
    f['create_survey']('partially_resolved')
    result = f['ask']('Which submissions say the issue is still unresolved?', period=PERIOD)
    assert result.status_code == 200, result.text
    body = result.json()
    assert '1 completed maintenance survey response(s)' in body['answer']
    assert 'Ticket completion does not change' in body['answer']
    assert [source['survey_id'] for source in body['structured_data']['sources']] == [unresolved.public_id]
    followup = f['ask']('Show the original answers behind that.', conversation_id=body['conversation_id'])
    assert followup.status_code == 200, followup.text
    assert followup.json()['period'] == PERIOD
    assert [source['survey_id'] for source in followup.json()['structured_data']['sources']] == [unresolved.public_id]
    assert not f['calls']


def test_original_question_context_options_labels_and_final_answers_reach_model(survey_flow):
    f = survey_flow
    row = f['create_survey']()
    f['create_survey'](submitted=None, comment='UNFINISHED PRIVATE DRAFT')
    foreign = Organization(name='Foreign community'); f['db'].add(foreign); f['db'].commit()
    f['create_survey'](org=foreign, resident='foreign-r', comment='FOREIGN PRIVATE SURVEY')
    f['model'].update(answer='One resident reports that the faucet still leaks.', evidence=[])
    result = f['ask']('What did residents say in surveys about their maintenance experience?', period=PERIOD)
    assert result.status_code == 200, result.text
    payload = context(f)
    assert payload['reviews'] == []
    assert payload['available_sources'] == ['surveys']
    assert payload['survey_calculated']['submission_count'] == 1
    original = payload['surveys'][0]
    assert original['survey_id'] == row.public_id
    assert original['context']['ticket_completed_at'].startswith('2026-10-01')
    assert original['template_id'] == 'maintenance_v1' and original['template_version'] == 1
    overall, resolution, response, comment = original['questions']
    assert 'a leaking kitchen faucet' in overall['text']
    assert overall['answer'] == 2 and overall['answer_label'] == '2 — Bad'
    assert resolution['answer_label'] == 'No, still unresolved'
    assert {choice['value'] for choice in resolution['options']} == {'resolved', 'partially_resolved', 'unresolved', 'not_checked'}
    assert response['answer_label'] == 'Not sure'
    assert comment['answer'] == 'The faucet still leaks after the visit.'
    assert original['saved_analysis'] == {'status': 'not_generated'}
    assert 'FOREIGN PRIVATE' not in json.dumps(payload) and 'UNFINISHED PRIVATE' not in json.dumps(payload)
    assert result.json()['structured_data']['sharing_unavailable_reason']


def test_survey_evidence_links_to_authorized_original_and_rejects_foreign_ids(survey_flow):
    f = survey_flow
    row = f['create_survey']()
    f['model'].update(answer='This resident reports an ongoing leak.', evidence=[{'survey_id': row.public_id, 'kind': 'survey'}])
    result = f['ask']('Show the survey answer describing the faucet.', period=PERIOD)
    assert result.status_code == 200, result.text
    source = result.json()['structured_data']['sources'][0]
    assert source['href'] == f'/surveys/{row.public_id}'
    original = f['client'].get('/api/v1/surveys/' + row.public_id, headers=f['headers'])
    assert original.status_code == 200
    assert original.json()['answers']['issue_resolution'] == 'unresolved'
    foreign = Organization(name='Foreign'); f['db'].add(foreign); f['db'].commit()
    other = f['create_survey'](org=foreign, resident='foreign-r')
    assert f['client'].get('/api/v1/surveys/' + other.public_id, headers=f['headers']).status_code == 404
    f['model']['evidence'] = [{'survey_id': other.public_id, 'kind': 'survey'}]
    assert f['ask']('Show the survey answer describing the faucet.', period=PERIOD).status_code == 502
    f['model']['evidence'] = [{'survey_id': row.public_id, 'kind': 'survey', 'excerpt': 'Everything was fixed.'}]
    assert f['ask']('Show the survey answer describing the faucet.', period=PERIOD).status_code == 502


def test_review_queries_do_not_receive_survey_records_and_existing_analysis_survives(survey_flow):
    f = survey_flow
    f['create_survey']()
    f['model'].update(answer='The review describes repair delays.', evidence=[{'review_id': f['rows'][0].id, 'kind': 'review'}])
    result = f['ask']('Show supporting reviews.', period=ALL)
    assert result.status_code == 200, result.text
    assert 'surveys' not in context(f)
    assert context(f)['calculated']['review_count'] == 5
    assert f['rows'][0].apartment_analysis['final_result']['topics'][0]['name'] == 'Maintenance'
    source = result.json()['structured_data']['sources'][0]
    assert source['href'] == f'/feedbacks/{f["rows"][0].id}'
    chat = result.json()['conversation_id']
    assert f['client'].post(f'/api/v1/ask-genius/conversations/{chat}/share', headers=f['headers']).status_code == 201


def test_survey_summaries_without_cards_and_mixed_chats_cannot_be_publicly_shared(survey_flow):
    f = survey_flow
    f['create_survey']()
    f['model'].update(answer='A resident reports an unresolved leak.', evidence=[])
    answer = f['ask']('Summarize the maintenance surveys.', period=ALL)
    assert answer.status_code == 200
    chat = answer.json()['conversation_id']
    assert not answer.json()['structured_data']['sources']
    # Explicitly switching back to reviews never makes earlier survey-backed prose public.
    assert f['ask']('Summarize the reviews.', conversation_id=chat).status_code == 200
    listed = f['client'].get('/api/v1/ask-genius/conversations', headers=f['headers']).json()['conversations'][0]
    assert listed['sharing_unavailable_reason']
    renamed = f['client'].patch(f'/api/v1/ask-genius/conversations/{chat}', headers=f['headers'], json={'title': 'Private findings'})
    assert renamed.json()['sharing_unavailable_reason']
    detail = f['client'].get(f'/api/v1/ask-genius/conversations/{chat}', headers=f['headers']).json()
    assert detail['sharing_unavailable_reason']
    shared = f['client'].post(f'/api/v1/ask-genius/conversations/{chat}/share', headers=f['headers'])
    assert shared.status_code == 422 and 'survey' in shared.json()['detail']
    assert f['db'].query(AskGeniusShare).count() == 0


def test_saved_survey_analysis_is_unavailable_without_jobs_or_model_calls(survey_flow):
    f = survey_flow
    f['create_survey']()
    result = f['ask']('Show saved survey sentiment analysis.', period=ALL)
    assert result.status_code == 200
    assert 'not available' in result.json()['answer'] and not f['calls']
    empty = f['ask']('Show completed maintenance surveys.', period={'preset': 'custom', 'start_date': '2025-01-01', 'end_date': '2025-01-31'})
    assert empty.json()['answer'].startswith('0 completed maintenance survey response(s)')


def test_wrong_community_account_cannot_retrieve_survey_context(survey_flow):
    f = survey_flow
    f['create_survey']()
    foreign = Organization(name='Foreign'); f['db'].add(foreign); f['db'].flush()
    user = User(email='foreign-manager@example.invalid', password_hash='unused', organization_id=foreign.id, role='member')
    f['db'].add(user); f['db'].commit()
    assert f['ask']('Show completed maintenance surveys.', period=ALL, headers=headers_for(user)).status_code == 403
    assert not f['calls']


@pytest.mark.parametrize('wording,resolution', [
    ('are resolved', 'resolved'), ('are partially resolved', 'partially_resolved'),
    ('say the issue is still unresolved', 'unresolved'), ('are not checked', 'not_checked'),
])
def test_count_questions_use_exact_resolution_values(survey_flow, wording, resolution):
    f = survey_flow
    for value in ['resolved', 'resolved', 'partially_resolved', 'unresolved', 'not_checked']:
        f['create_survey'](value)
    result = f['ask'](f'How many surveys {wording}?', period=ALL)
    assert result.status_code == 200, result.text
    expected = 2 if resolution == 'resolved' else 1
    assert result.json()['answer'].startswith(f'{expected} completed maintenance survey response(s)')
    assert not f['calls']


def test_unknown_narrative_count_predicate_never_returns_broad_total(survey_flow):
    f = survey_flow
    f['create_survey']('resolved', comment='The technician was prompt.')
    f['create_survey']('unresolved', resident='fictional-r2', comment='The team was late.')
    result = f['ask']('How many surveys say the team was late?', period=ALL)
    assert result.status_code == 200
    assert 'condition has no stored survey classification' in result.json()['answer']
    assert '2 submitted' not in result.json()['answer']
    assert not f['calls']


def test_narrow_survey_summary_keeps_verified_scope_for_original_answer_followup(survey_flow):
    f = survey_flow
    unresolved = f['create_survey']()
    f['create_survey']('resolved', comment='Completely fixed, thank you.')
    f['model'].update(answer='The resident reporting an unresolved issue says the faucet still leaks.', evidence=[])
    first = f['ask']('What did the unresolved surveys report about maintenance?', period=ALL)
    assert first.status_code == 200, first.text
    assert [record['survey_id'] for record in context(f)['surveys']] == [unresolved.public_id]
    followup = f['ask']('Show the original answers behind that.', conversation_id=first.json()['conversation_id'])
    assert followup.status_code == 200
    assert [source['survey_id'] for source in followup.json()['structured_data']['sources']] == [unresolved.public_id]
    assert len(f['calls']) == 1
    count = f['ask']('How many surveys?', conversation_id=first.json()['conversation_id'])
    assert count.json()['answer'].startswith('1 completed maintenance survey response(s)')


def test_review_only_maintenance_experience_question_keeps_surveys_out(survey_flow):
    f = survey_flow
    f['create_survey']()
    result = f['ask']('What do the reviews say about the maintenance experience?', period=ALL)
    assert result.status_code == 200
    assert 'surveys' not in context(f)


def test_narrative_summary_without_validated_subset_does_not_auto_attach_all_originals(survey_flow):
    f = survey_flow
    first = f['create_survey']()
    second = f['create_survey']('resolved', comment='The visit was quick.')
    f['model'].update(answer='One survey mentions a leak.', evidence=[])
    summary = f['ask']('What do the surveys say about leaks?', period=ALL)
    assert 'survey_match_ids' not in summary.json()['structured_data']
    f['model'].update(answer='Here is the original answer about the leak.', evidence=[{'kind': 'survey', 'survey_id': first.public_id}])
    result = f['ask']('Show the original answers behind that.', conversation_id=summary.json()['conversation_id'])
    assert result.status_code == 200
    assert [source['survey_id'] for source in result.json()['structured_data']['sources']] == [first.public_id]
    assert second.public_id not in result.json()['structured_data']['survey_match_ids']
    assert len(f['calls']) == 2


@pytest.mark.parametrize('question', [
    'Which surveys report unresolved issues but no staff problems?',
    'Which surveys do not report unresolved issues?',
    'Which unresolved surveys mention the faucet?',
])
def test_compound_or_negated_resolution_requests_are_not_silently_prefiltered(survey_flow, question):
    f = survey_flow
    unresolved = f['create_survey']()
    resolved = f['create_survey']('resolved')
    f['model'].update(answer='I will use the original answers to address that condition.', evidence=[])
    result = f['ask'](question, period=ALL)
    assert result.status_code == 200, result.text
    assert {record['survey_id'] for record in context(f)['surveys']} == {unresolved.public_id, resolved.public_id}
    assert 'survey_match_ids' not in result.json()['structured_data']


def test_zero_matching_resolution_is_counted_without_claiming_period_has_no_submissions(survey_flow):
    f = survey_flow
    f['create_survey']('resolved')
    result = f['ask']('Which submissions say the issue is still unresolved?', period=ALL)
    assert result.status_code == 200
    assert result.json()['answer'].startswith('0 completed maintenance survey response(s)')
    assert not result.json()['structured_data']['sources']
    assert not f['calls']


def test_source_clarification_resumes_original_question_and_keeps_period(survey_flow):
    f = survey_flow
    f['create_survey']()
    question = 'What did residents say about their maintenance experience?'
    first = f['ask'](question, period=PERIOD)
    assert first.json()['answer'] == 'Reviews, surveys, or both?'
    assert not f['calls']
    chat = first.json()['conversation_id']
    result = f['ask']('Surveys', conversation_id=chat)
    assert result.status_code == 200, result.text
    assert f['calls'][-1][-1]['content'] == question
    assert context(f)['source_scope'] == 'surveys'
    assert result.json()['period'] == PERIOD
    detail = f['client'].get(f'/api/v1/ask-genius/conversations/{chat}', headers=f['headers']).json()
    assert [m['content'] for m in detail['messages'] if m['role'] == 'user'] == [question, 'Surveys']


@pytest.mark.parametrize('correction,expected', [
    ('Reviews, not surveys', 'reviews'), ('Surveys, not reviews', 'surveys'),
    ('Use reviews instead of surveys', 'reviews'), ('Both', 'mixed'),
])
def test_explicit_source_corrections_and_maintenance_followup(survey_flow, correction, expected):
    f = survey_flow
    f['create_survey']()
    first = f['ask']('Summarize the reviews.', period=ALL).json()
    chat = first['conversation_id']
    followup = f['ask']('What did residents say about their maintenance experience?', conversation_id=chat)
    assert followup.json()['structured_data']['source_scope'] == 'reviews'
    assert 'surveys' not in context(f)
    result = f['ask'](correction, conversation_id=chat)
    assert result.json()['structured_data']['source_scope'] == expected
    assert ('surveys' in context(f)) == (expected != 'reviews')
    if expected == 'surveys':
        assert not context(f)['reviews']


def test_count_starter_counts_submissions_and_residents_only_when_asked(survey_flow):
    f = survey_flow
    f['create_survey']()
    f['create_survey']('resolved')
    f['create_survey'](submitted=None, resident='draft-only')
    f['create_survey'](submitted='2026-10-27T03:59:59+00:00', resident='outside-period')
    result = f['ask']('How many survey responses did we receive during this period?', period=PERIOD)
    assert result.status_code == 200
    assert result.json()['answer'].startswith('2 completed maintenance survey response(s)')
    assert 'resident' not in result.json()['answer']
    residents = f['ask']('How many unique residents responded?', conversation_id=result.json()['conversation_id'])
    assert residents.json()['answer'].startswith('1 unique resident(s)')
    assert not f['calls']


def test_survey_topic_context_attaches_only_relevant_original_questions(survey_flow):
    f = survey_flow
    leak = f['create_survey']()
    f['create_survey']('resolved', comment='The repair was excellent.')
    reference = {'survey_id': leak.public_id, 'kind': 'survey', 'topic': 'Ongoing leak',
                 'question_id': 'maintenance_comment', 'excerpt': 'The faucet still leaks after the visit.'}
    f['model'].update(answer='- **Ongoing leak:** One resident reports that the faucet still leaks.',
                      evidence=[], survey_context=[reference])
    first = f['ask']('What problems did residents describe in surveys?', period=ALL)
    assert first.status_code == 200, first.text
    assert first.json()['structured_data']['sources'] == []
    result = f['ask']('Let me see each answer.', conversation_id=first.json()['conversation_id'])
    assert result.status_code == 200, result.text
    sources = result.json()['structured_data']['sources']
    assert len(sources) == 1
    assert sources[0]['survey_id'] == leak.public_id
    assert sources[0]['topic'] == 'Ongoing leak'
    assert sources[0]['question_id'] == 'maintenance_comment'
    assert result.json()['answer'] == first.json()['answer']
    assert len(sources[0]['survey']['questions']) == 4  # Full submission stays in popup.
    assert len(f['calls']) == 1
    count = f['ask']('How many surveys?', conversation_id=first.json()['conversation_id'])
    assert count.json()['structured_data']['sources'] == []
    repeated = f['ask']('Show each answer.', conversation_id=first.json()['conversation_id'])
    assert repeated.json()['structured_data']['sources'][0]['topic'] == 'Ongoing leak'
    assert len(f['calls']) == 1


@pytest.mark.parametrize('reference', [
    {'question_id': 'invented'},
    {'question_id': 'issue_resolution', 'excerpt': 'The faucet still leaks after the visit.'},
    {'question_id': 'maintenance_comment', 'excerpt': 'Everything was fixed.'},
])
def test_survey_question_context_is_validated_against_original(survey_flow, reference):
    f = survey_flow
    row = f['create_survey']()
    f['model'].update(survey_context=[{'survey_id': row.public_id, 'kind': 'survey', 'topic': 'Resolution', **reference}])
    result = f['ask']('Summarize the surveys.', period=ALL)
    assert result.status_code == 502
    assert result.json()['detail']['reason'] == 'InvalidModelAnswer'


def test_preview_simulation_is_idempotent_and_preserves_existing_records(survey_flow, monkeypatch):
    from src.survey_preview import simulate_preview
    from src.models.survey import SurveyInstance
    f = survey_flow
    monkeypatch.delenv('SURVEY_PUBLIC_BASE_URL')
    monkeypatch.setenv('BOOMSAY_SURVEY_SIMULATION', 'false')
    monkeypatch.setenv('APP_URL', 'http://localhost:3000')
    snapshots = [(row.id, row.text, row.apartment_analysis) for row in f['rows']]
    user_before = (f['user'].email, f['user'].password_hash, f['user'].ask_genius_default_period)
    row = simulate_preview(f['db'])
    assert row.invitation.status == 'simulated'
    assert row.context_snapshot['resident_name'] == 'Jamie Example (fictional)'
    assert row.invitation.survey_url.startswith('http://127.0.0.1:53004/survey/')
    response = f['client'].put(f'/api/v1/resident-surveys/{row.token}/draft',
        headers={'Origin': 'http://127.0.0.1:53004'}, json={'answers': {'maintenance_overall': 2}})
    assert response.status_code == 200
    again = simulate_preview(f['db'])
    f['db'].refresh(again)
    assert again.public_id == row.public_id and again.draft_answers == {'maintenance_overall': 2}
    assert f['db'].query(SurveyInstance).count() == 1
    assert snapshots == [(r.id, r.text, r.apartment_analysis) for r in f['rows']]
    assert user_before == (f['user'].email, f['user'].password_hash, f['user'].ask_genius_default_period)
    assert os.environ['ASK_GENIUS_API_KEY'] == 'synthetic-never-sent'
    assert not f['calls']
    monkeypatch.setenv('BOOMSAY_REVIEW_PREVIEW', 'false')
    with pytest.raises(ValueError, match='requires the configured'):
        simulate_preview(f['db'])
    assert f['db'].query(SurveyInstance).count() == 1


LIFECYCLE_WORDING = [
    ('move_in_completed', 'move-in'), ('maintenance_completed', 'maintenance'),
    ('lease_month_3', '3-month'), ('lease_month_6', '6-month'),
    ('lease_month_9', '9-month renewal intent'), ('lease_renewed', 'completed renewal'),
    ('move_out_completed', 'move-out'),
]


def mixed_surveys(f):
    return {kind: f['create_survey'](event_type=kind) for kind, _ in LIFECYCLE_WORDING}


@pytest.mark.parametrize('kind,wording', LIFECYCLE_WORDING)
def test_each_named_type_count_list_and_originals_are_separate(survey_flow, kind, wording):
    f = survey_flow
    rows = mixed_surveys(f)
    result = f['ask'](f'How many {wording} surveys?', period=ALL)
    assert result.status_code == 200, result.text
    assert result.json()['answer'].startswith('1 completed ')
    metadata = result.json()['structured_data']
    assert metadata['survey_counts']['submission_count'] == 1
    assert metadata['survey_counts']['survey_type_counts'] == {kind: 1}
    assert metadata['survey_event_types'] == [kind]
    assert metadata['sources'] == []  # Counts do not dump private answers.
    listed = f['ask'](f'Show the {wording} surveys.', period=ALL)
    assert listed.status_code == 200, listed.text
    source = listed.json()['structured_data']['sources'][0]
    assert source['survey_id'] == rows[kind].public_id
    assert source['survey']['event_type'] == kind
    assert source['survey']['title'] == rows[kind].questionnaire_snapshot['title']
    assert [q['original_text'] for q in source['survey']['questions']] == [q['text'] for q in rows[kind].questionnaire_snapshot['questions']]
    assert source['survey']['context']['event_type'] == kind
    if kind != 'maintenance_completed':
        assert source['survey']['context']['ticket_id'] is None
        assert source['survey']['context'].get('ticket_completed_at') is None
    assert not f['calls']


def test_mixed_totals_keep_maintenance_resolution_and_renewal_semantics_separate(survey_flow):
    f = survey_flow
    rows = mixed_surveys(f)
    f['create_survey']('resolved', resident='fictional-r2')
    result = f['ask']('How many surveys?', period=ALL)
    assert result.status_code == 200, result.text
    metadata = result.json()['structured_data']
    assert result.json()['answer'].startswith('8 completed survey response(s)')
    assert metadata['survey_counts']['distinct_resident_count'] == 2
    assert metadata['survey_counts']['issue_resolution_counts'] == {'unresolved': 1, 'resolved': 1}
    assert metadata['survey_counts']['survey_type_counts']['lease_month_9'] == 1
    assert metadata['survey_counts']['survey_type_counts']['lease_renewed'] == 1
    ambiguous = f['ask']('How many surveys are unresolved?', period=ALL)
    assert 'different questions' in ambiguous.json()['answer']
    assert ambiguous.json()['structured_data']['sources'] == []
    exact = f['ask']('How many maintenance surveys are unresolved?', period=ALL)
    assert exact.json()['answer'].startswith('1 completed maintenance survey response(s)')
    assert exact.json()['structured_data']['survey_match_ids'] == [rows['maintenance_completed'].public_id]
    assert not f['calls']


def test_type_change_discards_prior_cohort_and_preserves_new_type_followups(survey_flow):
    f = survey_flow
    rows = mixed_surveys(f)
    extra = f['create_survey'](event_type='move_out_completed', resident='fictional-extra')
    first = f['ask']('Show unresolved maintenance surveys.', period=ALL)
    chat = first.json()['conversation_id']
    second = f['ask']('How many move-out surveys?', conversation_id=chat)
    assert second.json()['answer'].startswith('2 completed move-out survey response(s)')
    followup = f['ask']('Show the original answers.', conversation_id=chat)
    assert {s['survey_id'] for s in followup.json()['structured_data']['sources']} == {rows['move_out_completed'].public_id, extra.public_id}
    all_types = f['ask']('How many all surveys?', conversation_id=chat)
    assert all_types.json()['answer'].startswith('8 completed survey response(s)')
    assert not f['calls']


@pytest.mark.parametrize('question,expected', [
    ('How many move-in and maintenance surveys?', {'move_in_completed', 'maintenance_completed'}),
    ('How many all surveys except maintenance surveys?', {'move_in_completed','lease_month_3','lease_month_6','lease_month_9','lease_renewed','move_out_completed'}),
    ('How many surveys excluding maintenance?', {'move_in_completed','lease_month_3','lease_month_6','lease_month_9','lease_renewed','move_out_completed'}),
])
def test_shared_nouns_and_exclusions_never_silently_drop_or_add_types(survey_flow, question, expected):
    f = survey_flow
    mixed_surveys(f)
    result = f['ask'](question, period=ALL)
    assert result.status_code == 200, result.text
    assert result.json()['answer'].startswith(f'{len(expected)} completed ')
    assert set(result.json()['structured_data']['survey_event_types']) == expected
    assert not f['calls']


def test_comparison_and_topics_use_authorized_originals_and_reject_wrong_type_evidence(survey_flow):
    f = survey_flow
    rows = mixed_surveys(f)
    f['model'].update(answer='The original responses cover different stages of the resident experience.', evidence=[])
    result = f['ask']('Compare move-in and maintenance surveys.', period=ALL)
    assert result.status_code == 200, result.text
    payload = context(f)
    assert {row['event_type'] for row in payload['surveys']} == {'move_in_completed','maintenance_completed'}
    f['ask']('What do all surveys say about maintenance?', period=ALL)
    assert len(context(f)['surveys']) == 7  # Topic mentions do not narrow to one questionnaire.
    f['model']['evidence'] = [{'kind': 'survey', 'survey_id': rows['maintenance_completed'].public_id}]
    wrong_type = f['ask']('Explain the move-in surveys.', period=ALL)
    assert wrong_type.status_code == 502
    f['model']['evidence'] = [{'kind': 'survey', 'survey_id': rows['move_in_completed'].public_id,
                              'excerpt': 'Everything was fixed.'}]
    invented_quote = f['ask']('Explain the move-in surveys.', period=ALL)
    assert invented_quote.status_code == 502


def test_excluding_every_type_requires_a_new_selection(survey_flow):
    f = survey_flow
    mixed_surveys(f)
    result = f['ask']('Show all surveys except move-in, maintenance, 3-month, 6-month, 9-month, renewal and move-out surveys.', period=ALL)
    assert result.status_code == 422
    assert 'No survey types remain' in result.json()['detail']
    assert not f['calls']


def test_or_between_survey_types_requests_clear_selection(survey_flow):
    mixed_surveys(survey_flow)
    result = survey_flow['ask']('How many move-in or maintenance surveys?', period=ALL)
    assert result.status_code == 422
    assert 'Choose one survey type' in result.json()['detail']
    assert not survey_flow['calls']
