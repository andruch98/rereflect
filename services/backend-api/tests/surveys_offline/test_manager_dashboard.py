"""Manager journeys through the real survey routes; all data is fictional."""
from datetime import datetime, timedelta, timezone

from conftest import headers_for
from src.models.survey import SurveyInstance, SurveyInvitation
from src.services.survey_schedule import process_due_simulations
from src.api.routes.agent_settings import router as settings_router
from test_journey import prepared, FINAL


def listing(flow, **params):
    response = flow['client'].get('/api/v1/surveys', headers=flow['headers'], params=params)
    assert response.status_code == 200, response.text
    return response.json()


def save_settings(flow, **changes):
    base = '/api/v1/agent-settings'
    state = flow['client'].get(base, headers=flow['headers']).json()['surveys']
    state['values'].update(changes)
    saved = flow['client'].put(base + '/surveys', headers=flow['headers'],
                               json={'values': state['values'], 'version': state['version']})
    assert saved.status_code == 200, saved.text
    return saved.json()['values']


def test_move_from_needs_review_to_receipt_preserves_original_answer(survey_flow):
    f = survey_flow
    detail, public = prepared(f)
    path = '/api/v1/surveys/' + detail['public_id']
    assert f['client'].post(path + '/reviewed', headers=f['headers']).status_code == 409
    f['client'].put(public + '/draft', json={'answers': {'maintenance_overall': 1}})
    assert listing(f)['counts'] == {'sent': 0, 'submitted': 0, 'needs_review': 0}
    response = f['client'].post(public + '/submit', json={'answers': FINAL})
    assert response.status_code == 200
    original = response.json()
    queue = listing(f, view='needs_review')
    assert queue['counts'] == {'sent': 0, 'submitted': 1, 'needs_review': 1}
    row = queue['surveys'][0]
    assert [r['question_id'] for r in row['attention_reasons']] == ['maintenance_overall', 'issue_resolution']
    assert row['attention_reasons'][1] == {
        'question_id': 'issue_resolution', 'label': 'Is the issue fully resolved?', 'answer': 'No, still unresolved'}
    assert f['client'].get(path, headers=headers_for(f['member'])).json()['can_mark_reviewed'] is False
    assert f['client'].post(path + '/reviewed', headers=headers_for(f['member'])).status_code == 403
    assert f['client'].post(path + '/reviewed', headers=f['other_headers']).status_code == 404
    reviewed = f['client'].post(path + '/reviewed', headers=f['headers']).json()
    assert reviewed['reviewed_at'] and reviewed['reviewed_by'] == f['manager'].email
    assert f['client'].post(path + '/reviewed', headers=f['headers']).json()['reviewed_at'] == reviewed['reviewed_at']
    assert listing(f, view='needs_review')['surveys'] == []
    assert listing(f, view='reviewed')['total'] == 1
    assert reviewed['attention_reasons'] == row['attention_reasons']
    assert f['client'].get(public).json() == original


def test_current_rules_apply_to_existing_surveys_follow_up_always_visible(survey_flow):
    f = survey_flow
    f['app'].include_router(settings_router)
    _, main = prepared(f)
    f['client'].post(main + '/submit', json={'answers': FINAL})
    _, resident = prepared(f, event_type='lease_month_3', ticket_id=None, request_description=None,
                           event_id='event3', occurrence_id='occ3')
    answers = {'community_overall': 5, 'community_team_help': 4, 'follow_up_requested': 'yes',
               'lease_month_3_comment': 'rent payments'}
    assert f['client'].post(resident + '/submit', json={'answers': answers}).status_code == 200
    assert listing(f, view='needs_review')['total'] == 2
    save_settings(f, flag_unresolved=False, flag_low_ratings=False)
    queue = listing(f, view='needs_review')
    assert queue['total'] == 1 and queue['counts']['submitted'] == 2
    assert [r['question_id'] for r in queue['surveys'][0]['attention_reasons']] == ['follow_up_requested']


def test_typed_date_cards_use_actual_send_and_submission_dates(survey_flow):
    f = survey_flow
    at = datetime(2026, 11, 5, 5, tzinfo=timezone.utc)  # Eastern midnight after DST.
    for i, (status, simulated) in enumerate([
            ('provider_accepted', False), ('email_test_accepted', False), ('simulated', True),
            ('provider_failed', False), ('provider_accepted', True), ('provider_accepted', False)]):
        detail, public = prepared(f, occurrence_id=f'occ{i}', event_id=f'event{i}')
        if i <= 1:
            f['client'].post(public + '/submit', json={'answers': FINAL})
        with f['sessions']() as db:
            survey = db.query(SurveyInstance).filter_by(public_id=detail['public_id']).one()
            survey.created_at = at - timedelta(days=3)
            if i <= 1:
                survey.submitted_at = at - timedelta(minutes=i)
            survey.invitation.status = status
            survey.invitation.is_simulated = simulated
            survey.invitation.sent_at = at + timedelta(hours=1) if i < 5 else None
            db.commit()
    dates = {'start_date': '2026-11-05', 'end_date': '2026-11-05'}
    assert listing(f, **dates)['counts'] == {'sent': 1, 'submitted': 1, 'needs_review': 1}
    assert listing(f, **dates, view='sent')['total'] == 1
    assert listing(f, **dates, view='submitted')['total'] == 1
    assert listing(f, **dates, event_type='lease_month_3')['total'] == 0
    assert listing(f, view='sent')['total'] == 2  # includes undated legacy receipt
    assert listing(f, page_size=1)['total'] == 6
    assert len(listing(f, page_size=1)['surveys']) == 1
    assert f['client'].get('/api/v1/surveys', headers=f['headers'],
                           params={'start_date': '2026-11-06', 'end_date': '2026-11-05'}).status_code == 422


def test_due_schedules_and_reminders_process_once_and_never_count_as_sent(survey_flow):
    f = survey_flow
    f['app'].include_router(settings_router)
    config = save_settings(f)
    schedule = config['schedule']
    schedule['maintenance_completed']['delay_hours'] = 48
    schedule['lease_month_3']['enabled'] = False
    save_settings(f, schedule=schedule, reminder_hours=24)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    detail, _ = prepared(f, completed_at=now.isoformat())
    assert detail['invitation']['status'] == 'scheduled'
    assert prepared(f, completed_at=now.isoformat())[0]['public_id'] == detail['public_id']
    paused, _ = prepared(f, event_id='new', occurrence_id='new', event_type='lease_month_3',
                         ticket_id=None, request_description=None)
    assert paused['invitation']['status'] == 'suppressed_disabled'
    with f['sessions']() as db:
        dispatch = now + timedelta(hours=48)
        assert process_due_simulations(db, dispatch - timedelta(seconds=1)) == 0
        assert process_due_simulations(db, dispatch) == 1
        assert process_due_simulations(db, dispatch) == 0
        assert process_due_simulations(db, dispatch + timedelta(hours=24)) == 1
        assert process_due_simulations(db, dispatch + timedelta(days=3)) == 0
        row = db.query(SurveyInvitation).filter_by(status='simulated').one()
        assert row.reminder_simulated_at and row.reminder_due_at is None and row.sent_at is None
    assert listing(f)['counts'] == {'sent': 0, 'submitted': 0, 'needs_review': 0}


def test_submitting_opt_out_and_disabling_prevent_queued_work(survey_flow):
    f = survey_flow
    f['app'].include_router(settings_router)
    config = save_settings(f)
    schedule = config['schedule']
    save_settings(f, reminder_hours=24)
    _, path = prepared(f)
    assert listing(f)['surveys'][0]['invitation']['reminder_due_at']
    f['client'].post(path + '/submit', json={'answers': FINAL})
    now = datetime.now(timezone.utc)
    assert listing(f)['surveys'][0]['invitation']['reminder_due_at'] is None
    # An unsubscribe after scheduling immediately removes outstanding work.
    schedule['maintenance_completed']['delay_hours'] = 24
    save_settings(f, schedule=schedule)
    _, to_stop = prepared(f, completed_at=now.isoformat(), occurrence_id='opt-out', event_id='opt-out')
    assert f['client'].post(to_stop + '/unsubscribe').status_code == 200
    assert listing(f)['surveys'][0]['invitation']['status'] == 'suppressed_opt_out'
    prepared(f, completed_at=now.isoformat(), occurrence_id='new', event_id='new',
             resident_id='another', resident_email='another@survey.example.invalid')
    schedule['maintenance_completed']['enabled'] = False
    save_settings(f, schedule=schedule)
    with f['sessions']() as db:
        assert process_due_simulations(db, now + timedelta(days=10)) == 0
        assert db.query(SurveyInvitation).filter_by(status='suppressed_disabled').count() == 1
        assert not any(row.reminder_simulated_at for row in db.query(SurveyInvitation))


def test_pausing_reminders_never_requeues_an_existing_invitation(survey_flow):
    f = survey_flow
    f['app'].include_router(settings_router)
    save_settings(f, reminder_hours=24)
    prepared(f)
    assert listing(f)['surveys'][0]['invitation']['reminder_due_at'] is not None
    save_settings(f, reminder_hours=None)
    save_settings(f, reminder_hours=48)
    with f['sessions']() as db:
        assert process_due_simulations(db, datetime.now(timezone.utc) + timedelta(days=7)) == 0
        invite = db.query(SurveyInvitation).one()
        assert invite.status == 'simulated' and invite.reminder_simulated_at is None


def test_move_in_secondary_rating_and_unresolved_issue_are_separate(survey_flow):
    f = survey_flow
    _, public = prepared(f, event_type='move_in_completed', ticket_id=None, request_description=None)
    answers = {'move_in_overall': 5, 'apartment_condition': 2, 'move_in_unresolved': 'yes',
               'move_in_comment': 'Could someone check the bedroom window?'}
    f['client'].post(public + '/submit', json={'answers': answers}).raise_for_status()
    row = listing(f, view='needs_review')['surveys'][0]
    assert [r['question_id'] for r in row['attention_reasons']] == ['apartment_condition', 'move_in_unresolved']
    assert row['answers'] == answers and row['attention_reasons'][0]['answer'] == '2 — Bad'


async def test_api_timer_catches_up_on_a_persisted_simulation(survey_flow, monkeypatch):
    import asyncio
    from src.database import session
    from src.services.survey_schedule import simulated_delivery_timer

    f = survey_flow
    f['app'].include_router(settings_router)
    schedule = save_settings(f)['schedule']
    schedule['maintenance_completed']['delay_hours'] = 24
    save_settings(f, schedule=schedule)
    now = datetime.now(timezone.utc)
    detail, _ = prepared(f, completed_at=now.isoformat())
    with f['sessions']() as db:
        invitation = db.query(SurveyInvitation).one()
        assert invitation.status == 'scheduled'
        invitation.scheduled_for = now - timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(session, 'SessionLocal', f['sessions'])
    async with simulated_delivery_timer():
        for _ in range(200):
            with f['sessions']() as db:
                if db.query(SurveyInvitation.status).scalar() == 'simulated':
                    break
            await asyncio.sleep(.025)
        else:
            raise AssertionError('The API timer did not process the due simulation')
    assert listing(f)['surveys'][0]['public_id'] == detail['public_id']
    assert listing(f)['counts']['sent'] == 0


def test_simulation_queue_only_operates_in_bound_preview_community(survey_flow, monkeypatch):
    f = survey_flow
    f['app'].include_router(settings_router)
    schedule = save_settings(f)['schedule']
    schedule['maintenance_completed']['delay_hours'] = 24
    save_settings(f, schedule=schedule)
    now = datetime.now(timezone.utc)
    prepared(f, completed_at=now.isoformat())
    monkeypatch.setenv('BOOMSAY_REVIEW_PREVIEW', 'true')
    monkeypatch.setenv('BOOMSAY_PREVIEW_ORGANIZATION_ID', str(f['other_community'].id))
    with f['sessions']() as db:
        assert process_due_simulations(db, now + timedelta(days=2)) == 0
        assert db.query(SurveyInvitation).one().status == 'scheduled'
        monkeypatch.setenv('BOOMSAY_PREVIEW_ORGANIZATION_ID', str(f['community'].id))
        assert process_due_simulations(db, now + timedelta(days=2)) == 1
        assert db.query(SurveyInvitation).one().status == 'simulated'
