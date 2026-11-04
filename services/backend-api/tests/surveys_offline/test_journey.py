"""Bounded synthetic event → real routes → original persisted answer checks."""
from copy import deepcopy
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from conftest import fictional_event, headers_for
from src.models.feedback import FeedbackItem
from src.models.survey import MaintenanceOccurrence, SurveyInstance, SurveyInvitation, SurveyResident


FINAL = {
    'maintenance_overall': 2,
    'issue_resolution': 'unresolved',
    'maintenance_response_time': 'not_sure',
    'maintenance_comment': 'The fictional faucet still leaks after the ticket was marked completed.',
}


def prepared(flow, **changes):
    response = flow['simulate'](**changes)
    assert response.status_code in (200, 201), response.text
    detail = response.json()
    token = urlsplit(detail['invitation']['survey_url']).path.split('/')[-1]
    return detail, '/api/v1/resident-surveys/' + token


def test_simulated_event_creates_bound_questionnaire_one_invitation_and_no_review(survey_flow):
    flow = survey_flow
    detail, resident_path = prepared(flow)
    assert detail['status'] == 'pending'
    invitation = detail['invitation']
    assert invitation['status'] == 'simulated'
    assert invitation['is_simulated'] is True
    assert invitation['provider'] == 'resend'
    assert invitation['recipient'] == 'jordan@boomsay.example.invalid'
    assert invitation['survey_url'].startswith('http://testserver/survey/')
    assert invitation['survey_url'] in invitation['text']
    assert invitation['survey_url'] in invitation['html']
    questionnaire = detail['questionnaire']
    assert questionnaire['id'] == 'maintenance_v1'
    assert questionnaire['version'] == 1
    assert questionnaire['catalog_version'] == 1
    assert questionnaire['rating_labels'] == {
        '1': 'Terrible', '2': 'Bad', '3': 'Okay', '4': 'Good', '5': 'Excellent'}
    questions = questionnaire['questions']
    assert [q['id'] for q in questions] == [
        'maintenance_overall', 'issue_resolution', 'maintenance_response_time', 'maintenance_comment']
    assert questions[0]['text'] == 'Overall, how would you rate the maintenance service for {request_description}?'
    assert questions[0]['rendered_text'] == 'Overall, how would you rate the maintenance service for the fictional kitchen faucet repair?'
    assert [q['required'] for q in questions] == [True, True, True, False]
    assert questions[1]['text'] == 'Is the issue fully resolved?'
    assert questions[1]['options'] == [
        {'value': 'resolved', 'label': 'Yes, fully resolved'},
        {'value': 'partially_resolved', 'label': 'Partially resolved'},
        {'value': 'unresolved', 'label': 'No, still unresolved'},
        {'value': 'not_checked', 'label': 'I haven’t checked yet'},
    ]
    assert questions[2]['text'] == 'How would you rate our maintenance team’s response time to your request?'
    assert questions[2]['special_options'] == [{'value': 'not_sure', 'label': 'Not sure'}]
    assert questions[3]['text'] == 'What would you like us to know about this maintenance experience?'
    assert questions[3]['max_length'] == 2000
    public = flow['client'].get(resident_path)
    assert public.status_code == 200
    assert public.json()['questionnaire'] == questionnaire
    with flow['sessions']() as db:
        assert db.query(MaintenanceOccurrence).count() == 1
        assert db.query(SurveyInstance).count() == 1
        assert db.query(SurveyInvitation).count() == 1
        assert db.query(FeedbackItem).count() == 0
        occurrence = db.query(MaintenanceOccurrence).one()
        assert occurrence.resident_id == 'synthetic-resident-1'
        assert occurrence.unit_number == '101'
        assert occurrence.employee_id is None
        assert occurrence.employee_name is None
        assert occurrence.is_simulated is True


def test_event_and_occurrence_replay_are_durable_and_separate_occurrences_keep_links(survey_flow):
    first, first_path = prepared(survey_flow)
    replay, replay_path = prepared(survey_flow)
    alias, alias_path = prepared(survey_flow, event_id='synthetic-replayed-event-alias')
    second, second_path = prepared(survey_flow, event_id='synthetic-event-002',
        occurrence_id='synthetic-occurrence-002', ticket_id='SYNTH-M-1002',
        request_description='the fictional dishwasher repair')
    assert first['public_id'] == replay['public_id'] == alias['public_id']
    assert first_path == replay_path == alias_path
    assert first_path != second_path
    assert first['public_id'] != second['public_id']
    assert 'faucet' in survey_flow['client'].get(first_path).json()['questionnaire']['questions'][0]['rendered_text']
    assert 'dishwasher' in survey_flow['client'].get(second_path).json()['questionnaire']['questions'][0]['rendered_text']
    with survey_flow['sessions']() as db:
        assert db.query(MaintenanceOccurrence).count() == 2
        assert db.query(SurveyInstance).count() == 2
        assert db.query(SurveyInvitation).count() == 2
        assert {r.status for r in db.query(SurveyInvitation)} == {'simulated'}
    conflict = survey_flow['simulate'](resident_id='another-synthetic-resident')
    assert conflict.status_code in (409, 422)


def test_partial_draft_resumes_after_engine_restart_and_final_answers_are_immutable(survey_flow):
    flow = survey_flow
    detail, path = prepared(flow)
    draft = {'maintenance_overall': 2, 'maintenance_comment': '  Exact draft wording.  '}
    saved = flow['client'].put(path + '/draft', json={'answers': draft})
    assert saved.status_code == 200, saved.text
    assert saved.json()['status'] == 'draft'
    # A new engine and session read disk: this is not just an ORM identity map check.
    flow['engine'].dispose()
    restarted = create_engine(flow['database_url'])
    with sessionmaker(bind=restarted)() as db:
        persisted = db.query(SurveyInstance).filter_by(public_id=detail['public_id']).one()
        assert persisted.draft_answers == draft
        assert persisted.answers == {}
        assert persisted.submitted_at is None
    restarted.dispose()
    reloaded = flow['client'].get(path).json()
    assert reloaded['draft_answers'] == draft
    submitted = flow['client'].post(path + '/submit', json={'answers': FINAL})
    assert submitted.status_code == 200, submitted.text
    completed = submitted.json()
    assert completed['submitted_at'] is not None
    assert completed['status'] == 'submitted'
    assert completed['answers'] == FINAL
    assert completed['draft_answers'] == {}
    assert flow['client'].post(path + '/submit', json={'answers': {**FINAL, 'issue_resolution': 'resolved'}}).json()['answers'] == FINAL
    assert flow['client'].put(path + '/draft', json={'answers': {'issue_resolution': 'resolved'}}).json()['answers'] == FINAL
    assert flow['client'].get(path).json()['submitted_at'] == completed['submitted_at']
    manager_detail = flow['client'].get('/api/v1/surveys/' + detail['public_id'], headers=flow['headers'])
    assert manager_detail.status_code == 200
    assert manager_detail.json()['answer_labels']['maintenance_overall'] == '2 — Bad'
    assert manager_detail.json()['answer_labels']['issue_resolution'] == 'No, still unresolved'
    assert manager_detail.json()['answer_labels']['maintenance_response_time'] == 'Not sure'
    assert manager_detail.json()['context']['ticket_completed_at'] == '2026-10-28T14:30:00-04:00'
    assert manager_detail.json()['context']['employee_name'] is None
    dashboard = flow['client'].get('/api/v1/surveys', headers=flow['headers']).json()
    assert dashboard['total'] == 1
    assert dashboard['surveys'][0]['public_id'] == detail['public_id']
    assert dashboard['surveys'][0]['status'] == 'submitted'
    assert dashboard['surveys'][0]['invitation']['status'] == 'simulated'


@pytest.mark.parametrize('answers', [
    {}, {'maintenance_overall': True}, {'maintenance_overall': '2'},
    {'maintenance_overall': 2.0}, {'maintenance_overall': 0}, {'maintenance_overall': 6},
    {'issue_resolution': 'yes'}, {'issue_resolution': 1},
    {'maintenance_response_time': 'unknown'}, {'maintenance_comment': 7},
    {'maintenance_comment': 'x' * 2001}, {'invented_question': 'invented answer'},
])
def test_invalid_final_answers_do_not_report_success_or_persist_completion(survey_flow, answers):
    _, path = prepared(survey_flow)
    response = survey_flow['client'].post(path + '/submit', json={'answers': answers})
    assert response.status_code == 422, response.text
    state = survey_flow['client'].get(path).json()
    assert state['submitted_at'] is None
    assert state['answers'] == {}
    assert state['status'] == 'pending'


def test_optional_comment_and_not_sure_are_valid_and_template_remains_frozen(survey_flow, monkeypatch):
    from src.services import survey_catalog
    detail, path = prepared(survey_flow)
    changed = deepcopy(survey_catalog.CATALOG)
    changed['rating_labels']['2'] = 'Future wording'
    changed['templates'][0]['questions'][0]['text'] = 'A future different question?'
    monkeypatch.setattr(survey_catalog, 'CATALOG', changed)
    answers = {k: v for k, v in FINAL.items() if k != 'maintenance_comment'}
    response = survey_flow['client'].post(path + '/submit', json={'answers': answers})
    assert response.status_code == 200, response.text
    assert response.json()['answers']['maintenance_comment'] == ''
    assert response.json()['questionnaire'] == detail['questionnaire']
    assert response.json()['answer_labels']['maintenance_overall'] == '2 — Bad'


def test_failed_submission_commit_returns_failure_and_rolls_back_answer_set(survey_flow, monkeypatch):
    from sqlalchemy.orm import Session
    _, path = prepared(survey_flow)
    original_commit = Session.commit
    def fail_answer_commit(db):
        # Public submission uses an UPDATE; the committed state must remain pending.
        if db.query(SurveyInstance).filter(SurveyInstance.status == 'submitted').first():
            raise RuntimeError('Synthetic isolated-storage failure')
        return original_commit(db)
    with monkeypatch.context() as patched:
        patched.setattr(Session, 'commit', fail_answer_commit)
        failed = survey_flow['client'].post(path + '/submit', json={'answers': FINAL})
        assert failed.status_code >= 500
    state = survey_flow['client'].get(path).json()
    assert state['submitted_at'] is None
    assert state['answers'] == {}
    assert state['status'] == 'pending'
    assert survey_flow['client'].post(path + '/submit', json={'answers': FINAL}).status_code == 200


def test_failed_draft_commit_does_not_claim_saved_or_lose_prior_draft(survey_flow, monkeypatch):
    from sqlalchemy.orm import Session
    _, path = prepared(survey_flow)
    prior = {'maintenance_overall': 2}
    assert survey_flow['client'].put(path + '/draft', json={'answers': prior}).status_code == 200
    def fail_commit(db):
        raise RuntimeError('Synthetic draft storage failure')
    with monkeypatch.context() as patched:
        patched.setattr(Session, 'commit', fail_commit)
        failed = survey_flow['client'].put(path + '/draft', json={'answers': {'maintenance_overall': 5}})
        assert failed.status_code >= 500
    state = survey_flow['client'].get(path).json()
    assert state['draft_answers'] == prior
    assert state['submitted_at'] is None


def test_existing_review_and_saved_analysis_are_unchanged(survey_flow):
    from datetime import date
    saved_analysis = {'final_result': {'method': 'ai_model', 'sentiment': 'negative',
        'topics': [{'name': 'Maintenance', 'sentiment': 'negative',
                    'quotations': [{'text': 'Fictional review repair delay.', 'sentiment': 'negative'}]}]}}
    with survey_flow['sessions']() as db:
        review = FeedbackItem(organization_id=survey_flow['community'].id,
            source='apartment_review_ai', review_date=date(2026, 10, 1),
            text='Fictional review repair delay.', star_rating=2, apartment_analysis=saved_analysis)
        db.add(review); db.commit()
        original_id = review.id
    _, path = prepared(survey_flow)
    assert survey_flow['client'].post(path + '/submit', json={'answers': FINAL}).status_code == 200
    with survey_flow['sessions']() as db:
        assert db.query(FeedbackItem).count() == 1
        original = db.get(FeedbackItem, original_id)
        assert original.text == 'Fictional review repair delay.'
        assert original.source == 'apartment_review_ai'
        assert original.review_date == date(2026, 10, 1)
        assert original.apartment_analysis == saved_analysis


def test_dashboard_pending_and_submitted_are_community_scoped_and_simulation_is_admin_only(survey_flow):
    flow = survey_flow
    first, first_path = prepared(flow)
    second, _ = prepared(flow, event_id='synthetic-event-002', occurrence_id='synthetic-occurrence-002', ticket_id='SYNTH-M-1002')
    assert flow['client'].post(first_path + '/submit', json={'answers': FINAL}).status_code == 200
    dashboard = flow['client'].get('/api/v1/surveys', headers=headers_for(flow['member']))
    assert dashboard.status_code == 200
    assert dashboard.json()['total'] == 2
    assert {r['status'] for r in dashboard.json()['surveys']} == {'pending', 'submitted'}
    assert flow['client'].get('/api/v1/surveys').status_code in (401, 403)
    assert flow['client'].get('/api/v1/surveys/' + first['public_id'], headers=flow['other_headers']).status_code == 404
    assert flow['client'].get('/api/v1/surveys', headers=flow['other_headers']).json()['total'] == 0
    forbidden = flow['client'].post('/api/v1/surveys/simulate', headers=flow['other_headers'],
        json=fictional_event(flow['community'].id))
    assert forbidden.status_code in (403, 404)
    member_attempt = flow['client'].post('/api/v1/surveys/simulate', headers=headers_for(flow['member']),
        json=fictional_event(flow['community'].id))
    assert member_attempt.status_code == 403


def test_optout_is_durable_by_identity_and_email_without_affecting_resident_submission(survey_flow):
    flow = survey_flow
    first, path = prepared(flow, resident_opt_out=True)
    assert first['invitation']['status'] == 'suppressed_opt_out'
    second, _ = prepared(flow, event_id='synthetic-event-002', occurrence_id='synthetic-occurrence-002',
        ticket_id='SYNTH-M-1002', resident_opt_out=False)
    alias, _ = prepared(flow, event_id='synthetic-event-003', occurrence_id='synthetic-occurrence-003',
        ticket_id='SYNTH-M-1003', resident_id='synthetic-email-alias')
    assert second['invitation']['status'] == 'suppressed_opt_out'
    assert alias['invitation']['status'] == 'suppressed_opt_out'
    assert flow['client'].post(path + '/submit', json={'answers': FINAL}).status_code == 200
    with flow['sessions']() as db:
        assert db.query(SurveyResident).filter_by(resident_id='synthetic-resident-1').one().email_opt_out is True


def test_fictional_timezone_and_simulated_event_guards(survey_flow, monkeypatch):
    for changes in ({'completed_at': '2026-10-28T14:30:00'}, {'is_simulated': False},
                    {'event_type': 'move_in_completed'}, {'resident_email': 'real@example.com'}):
        response = survey_flow['simulate'](**changes)
        assert response.status_code == 422, response.text
    monkeypatch.setenv('BOOMSAY_SURVEY_SIMULATION', 'false')
    assert survey_flow['simulate']().status_code in (403, 404)


def test_invalid_private_link_and_privacy_headers(survey_flow):
    _, path = prepared(survey_flow)
    response = survey_flow['client'].get(path)
    assert response.headers.get('cache-control') == 'no-store'
    assert response.headers.get('referrer-policy') == 'no-referrer'
    assert survey_flow['client'].get('/api/v1/resident-surveys/not-a-private-token').status_code == 404
    assert survey_flow['client'].put(path + '/draft', headers={'Origin': 'https://unrelated.example.invalid'},
        json={'answers': {'maintenance_overall': 2}}).status_code in (400, 403)
    context = response.json()['context']
    assert 'resident_email' not in context
    assert 'resident_id' not in context
    assert 'unit_id' not in context
    assert 'event_id' not in context


def test_unsubscribe_requires_post_and_preserves_answers_and_original_recipient(survey_flow):
    flow = survey_flow
    first, path = prepared(flow)
    assert flow['client'].post(path + '/submit', json={'answers': FINAL}).status_code == 200
    # Opening an email link cannot mutate preferences; it renders the web confirmation.
    assert flow['client'].get(path + '/unsubscribe').status_code == 405
    with flow['sessions']() as db:
        assert db.query(SurveyResident).one().email_opt_out is False
    for _ in range(2):
        response = flow['client'].post(path + '/unsubscribe')
        assert response.status_code == 200
        assert response.json()['status'] == 'unsubscribed'
    assert flow['client'].get(path).json()['answers'] == FINAL
    following, _ = prepared(flow, event_id='synthetic-event-002', occurrence_id='synthetic-occurrence-002',
        ticket_id='SYNTH-M-1002', resident_email='updated@survey.example.invalid')
    assert following['invitation']['status'] == 'suppressed_opt_out'
    original = flow['client'].get('/api/v1/surveys/' + first['public_id'], headers=flow['headers']).json()
    assert original['invitation']['recipient'] == 'jordan@boomsay.example.invalid'


def test_existing_customer_optout_is_honored_without_customer_outreach(survey_flow):
    from src.models.customer_health import CustomerHealth
    with survey_flow['sessions']() as db:
        db.add(CustomerHealth(organization_id=survey_flow['community'].id,
            customer_email='JORDAN@BOOMSAY.EXAMPLE.INVALID', outreach_opt_out=True))
        db.commit()
    detail, _ = prepared(survey_flow)
    assert detail['invitation']['status'] == 'suppressed_opt_out'
    with survey_flow['sessions']() as db:
        assert db.query(CustomerHealth).count() == 1


def test_unsubscribe_uses_invitation_email_snapshot_after_contact_changes(survey_flow):
    flow = survey_flow
    first, _ = prepared(flow)
    updated, updated_path = prepared(flow, event_id='synthetic-updated-contact-event',
        occurrence_id='synthetic-updated-contact-occurrence', ticket_id='SYNTH-M-UPDATED',
        resident_email='changed@survey.example.invalid')
    assert updated['invitation']['recipient'] == 'changed@survey.example.invalid'
    assert updated['invitation']['status'] == 'simulated'
    assert flow['client'].post(updated_path + '/unsubscribe').status_code == 200
    alias, _ = prepared(flow, event_id='synthetic-email-alias-event',
        occurrence_id='synthetic-email-alias-occurrence', ticket_id='SYNTH-M-ALIAS',
        resident_id='synthetic-resident-alias', resident_email='changed@survey.example.invalid')
    assert alias['invitation']['status'] == 'suppressed_opt_out'
    identity, _ = prepared(flow, event_id='synthetic-identity-event',
        occurrence_id='synthetic-identity-occurrence', ticket_id='SYNTH-M-IDENTITY',
        resident_email='third@survey.example.invalid')
    assert identity['invitation']['status'] == 'suppressed_opt_out'
    original = flow['client'].get('/api/v1/surveys/' + first['public_id'], headers=flow['headers']).json()
    assert original['invitation']['recipient'] == 'jordan@boomsay.example.invalid'
    assert original['invitation']['survey_url'] == first['invitation']['survey_url']


def test_resend_adapter_uses_existing_transport_only_when_explicitly_allowed(monkeypatch):
    from src.services import email_service
    from src.services.survey_delivery import ResendSurveySender, SimulatedSurveySender
    invitation = SurveyInvitation(is_simulated=True, recipient='fictional@survey.example.invalid',
        subject='Synthetic maintenance invitation', html='<p>Synthetic only</p>', text='Synthetic only')
    calls = []
    def transport(**values):
        calls.append(values)
        return True
    monkeypatch.setattr(email_service, '_send_email', transport)
    assert SimulatedSurveySender().send(invitation) == 'simulated'
    with pytest.raises(ValueError):
        ResendSurveySender().send(invitation, allow_live=True)
    assert calls == []
    # Exercise only the adapter wiring against a mocked transport; no HTTP is made.
    invitation.is_simulated = False
    with pytest.raises(ValueError):
        ResendSurveySender().send(invitation)
    assert ResendSurveySender().send(invitation, allow_live=True) == 'provider_accepted'
    assert calls == [{'to': invitation.recipient, 'subject': invitation.subject,
                      'html': invitation.html, 'text': invitation.text}]
