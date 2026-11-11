"""Exercise both onboarding forms with real auth and no delivery or publishing."""
from copy import deepcopy

import pytest

from conftest import headers_for
from src.api.routes.agent_settings import router
from src.models.agent_settings import CommunityAgentSettings
from src.models.feedback import FeedbackItem
from src.models.survey import SurveyInstance, SurveyInvitation

BASE = '/api/v1/agent-settings'


@pytest.fixture
def flow(survey_flow):
    survey_flow['app'].include_router(router)
    return survey_flow


def current(flow, headers=None):
    response = flow['client'].get(BASE, headers=headers if headers is not None else flow['headers'])
    assert response.status_code == 200, response.text
    return response.json()


def save(flow, tab, state, headers=None, **changes):
    payload = {'version': state['version'], 'values': {**state['values'], **changes}}
    return flow['client'].put(f'{BASE}/{tab}', json=payload, headers=headers or flow['headers'])


def test_defaults_are_a_preview_and_do_not_create_work(flow):
    assert flow['client'].get(BASE).status_code in {401, 403}
    data = current(flow)
    assert data['community_name'] == flow['community'].name
    assert data['reviews']['values']['community_name'] == flow['community'].name
    assert data['reviews']['values']['mode'] == 'approval'
    assert data['reviews']['values']['public_email'] == ''
    assert data['reviews']['configured'] is False
    assert data['surveys']['configured'] is False
    assert data['reviews']['version'] == data['surveys']['version'] == 0
    schedule = data['surveys']['values']['schedule']
    assert set(schedule) == {
        'maintenance_completed', 'move_in_completed', 'lease_month_3', 'lease_month_6',
        'lease_month_9', 'lease_renewed', 'move_out_completed',
    }
    assert all(entry == {'enabled': True, 'delay_hours': 0} for entry in schedule.values())
    with flow['sessions']() as db:
        assert db.query(CommunityAgentSettings).count() == 0


def test_separate_confirmations_and_later_edit_preserve_the_rest(flow):
    data = current(flow)
    surveys = data['surveys']
    schedule = deepcopy(surveys['values']['schedule'])
    schedule['move_in_completed'] = {'enabled': True, 'delay_hours': 48}
    schedule['lease_month_9']['enabled'] = False
    response = save(flow, 'surveys', surveys, schedule=schedule, reminder_hours=72)
    assert response.status_code == 200, response.text
    assert response.json()['configured'] is True
    assert response.json()['version'] == 1
    assert current(flow)['reviews'] == data['reviews']

    response = save(flow, 'reviews', data['reviews'], mode='automatic', public_email='office@example.com',
                    public_phone='+1 (305) 555-0112', tone='warm', signature='Lake House team')
    assert response.status_code == 200, response.text
    response = save(flow, 'reviews', response.json(), tone='concise')
    assert response.status_code == 200, response.text
    saved = current(flow)
    assert saved['surveys']['values']['reminder_hours'] == 72
    assert saved['surveys']['values']['schedule'] == schedule
    assert saved['reviews']['version'] == 2
    assert saved['reviews']['values']['signature'] == 'Lake House team'
    assert saved['reviews']['values']['public_email'] == 'office@example.com'
    assert saved['reviews']['values']['tone'] == 'concise'
    with flow['sessions']() as db:
        assert db.query(CommunityAgentSettings).count() == 2
        assert all(row.updated_by == flow['manager'].id for row in db.query(CommunityAgentSettings))
        assert db.query(SurveyInstance).count() == db.query(SurveyInvitation).count() == 0
        assert db.query(FeedbackItem).count() == 0


def test_stale_first_confirmation_and_stale_edit_cannot_overwrite_another_manager(flow):
    initial = current(flow)['reviews']
    updated = save(flow, 'reviews', initial, signature='Office').json()
    assert save(flow, 'reviews', initial, signature='Stale initial setup').status_code == 409
    assert save(flow, 'reviews', updated, signature='Community team').status_code == 200
    assert save(flow, 'reviews', updated, signature='Stale edit').status_code == 409
    assert current(flow)['reviews']['values']['signature'] == 'Community team'


def test_member_views_without_editing_and_other_community_has_own_settings(flow):
    admin = current(flow)
    assert admin['can_edit']
    result = save(flow, 'reviews', admin['reviews'], facts='Office hours by appointment')
    assert result.status_code == 200, result.text
    member = headers_for(flow['member'])
    displayed = current(flow, member)
    assert not displayed['can_edit']
    assert displayed['reviews']['values']['facts'] == 'Office hours by appointment'
    for tab in ('surveys', 'reviews'):
        assert save(flow, tab, displayed[tab], headers=member).status_code == 403
    other = current(flow, flow['other_headers'])
    assert other['community_name'] == flow['other_community'].name
    assert other['reviews']['configured'] is False
    assert save(flow, 'reviews', other['reviews'], headers=flow['other_headers'],
                facts='Different public office hours').status_code == 200
    assert current(flow)['reviews'] == displayed['reviews']


def test_bad_contact_timing_and_partial_schedule_are_rejected_together_without_mutating_state(flow):
    initial = current(flow)
    assert save(flow, 'reviews', initial['reviews'], public_email='not-an-email').status_code == 422
    assert save(flow, 'reviews', initial['reviews'], organization_id=flow['other_community'].id).status_code == 422
    assert save(flow, 'surveys', initial['surveys'], reminder_hours=36).status_code == 422
    schedule = deepcopy(initial['surveys']['values']['schedule'])
    schedule['move_in_completed']['delay_hours'] = 12
    assert save(flow, 'surveys', initial['surveys'], schedule=schedule).status_code == 422
    schedule.pop('move_in_completed')
    assert save(flow, 'surveys', initial['surveys'], schedule=schedule).status_code == 422
    assert current(flow) == initial


def test_preview_is_scoped_to_the_configured_community(flow, monkeypatch):
    monkeypatch.setenv('BOOMSAY_REVIEW_PREVIEW', 'true')
    monkeypatch.setenv('BOOMSAY_PREVIEW_ORGANIZATION_ID', str(flow['community'].id))
    allowed = current(flow)
    other = flow['other_headers']
    assert flow['client'].get(BASE, headers=other).status_code == 403
    assert save(flow, 'reviews', allowed['reviews'], headers=other).status_code == 403
