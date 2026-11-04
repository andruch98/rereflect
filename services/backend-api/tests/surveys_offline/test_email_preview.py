import importlib.util
from pathlib import Path
import io
import json
import pytest
from src.survey_email_preview import operate, RECIPIENT
from src.models.survey import SurveyInstance, SurveyInvitation, SurveyEmailOptOut

@pytest.fixture
def email_flow(survey_flow, monkeypatch):
    monkeypatch.setenv('BOOMSAY_REVIEW_PREVIEW', 'true')
    monkeypatch.setenv('BOOMSAY_PREVIEW_ORGANIZATION_ID', str(survey_flow['community'].id))
    monkeypatch.setenv('SURVEY_PUBLIC_BASE_URL', 'http://127.0.0.1:53004')
    with survey_flow['sessions']() as db:
        from src.models.organization import Organization
        db.get(Organization, survey_flow['community'].id).name = 'Lake House Apartments'
        db.commit()
    return survey_flow

def test_prepare_replay_reserve_and_receipt(email_flow):
    with email_flow['sessions']() as db:
        first = operate(db, 'prepare', 'first-test')
        assert first == operate(db, 'prepare', 'first-test')
        assert db.query(SurveyInstance).count() == 1
        assert first['payload']['to'] == [RECIPIENT]
        assert first['payload']['from'] == 'BoomSay <andres@boomsay.com>'
        assert 'fictional maintenance request' in first['payload']['text']
        assert operate(db, 'reserve', 'first-test')['status'] == 'email_test_reserved'
    with email_flow['sessions']() as db:
        with pytest.raises(ValueError, match='duplicate'):
            operate(db, 'reserve', 'first-test')
        assert operate(db, 'accepted', 'first-test')['status'] == 'email_test_accepted'
        assert db.query(SurveyInvitation).one().is_simulated is False
        assert db.query(SurveyInstance).one().occurrence.is_simulated is True
        assert operate(db, 'prepare', 'explicit-second-test')['status'] == 'simulated'
        assert db.query(SurveyInstance).count() == 2

@pytest.mark.parametrize('reason', ['optout', 'completed', 'other-recipient'])
def test_refuses_ineligible(email_flow, reason):
    with email_flow['sessions']() as db:
        operate(db, 'prepare', 'first-test')
        survey = db.query(SurveyInstance).one()
        if reason == 'optout':
            db.add(SurveyEmailOptOut(organization_id=survey.organization_id, email=RECIPIENT))
        elif reason == 'completed':
            survey.status = 'submitted'
        else:
            survey.invitation.recipient = 'someone@example.com'
        db.commit()
        with pytest.raises(ValueError):
            operate(db, 'reserve', 'first-test')
        assert survey.invitation.is_simulated

def test_refuses_nonpreview_before_writes(email_flow, monkeypatch):
    monkeypatch.setenv('BOOMSAY_REVIEW_PREVIEW', 'false')
    with email_flow['sessions']() as db:
        with pytest.raises(ValueError):
            operate(db, 'prepare', 'first-test')
        assert db.query(SurveyInstance).count() == 0

def helper():
    path = Path(__file__).resolve().parents[4] / 'experiments/maintenance_surveys/email_preview/survey-email-test.py'
    spec = importlib.util.spec_from_file_location('email_helper', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.mark.parametrize('outcome', ['accepted', 'timeout', 'bad-json', 'ack-fails'])
def test_host_delivery_boundary(email_flow, outcome):
    module = helper()
    calls = []
    def call(action, name):
        if outcome == 'ack-fails' and action == 'accepted':
            raise ValueError('database unavailable')
        with email_flow['sessions']() as db:
            return operate(db, action, name)
    call('prepare', 'first-test')
    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            assert request.full_url == 'https://api.resend.com/emails'
            assert json.loads(request.data)['to'] == [RECIPIENT]
            if outcome == 'timeout':
                raise TimeoutError('secret must not leak')
            response = io.BytesIO(b'no-json' if outcome == 'bad-json' else b'{"id":"fictional-receipt"}')
            response.status = 200
            return response
    if outcome in ('timeout', 'bad-json'):
        with pytest.raises(ValueError, match='uncertain'):
            module.send_once('first-test', 're_fake', call, Opener())
    else:
        assert 'accepted' in module.send_once('first-test', 're_fake', call, Opener())
    with pytest.raises(ValueError, match='duplicate'):
        module.send_once('first-test', 're_fake', call, Opener())
    assert len(calls) == 1

def test_no_redirect():
    assert helper().NoRedirect().redirect_request(None) is None


def test_email_test_links_submit_and_unsubscribe(email_flow):
    with email_flow['sessions']() as db:
        data = operate(db, 'prepare', 'first-test')
        operate(db, 'reserve', 'first-test')
        operate(db, 'accepted', 'first-test')
        token = db.query(SurveyInstance).one().token
    path = '/api/v1/resident-surveys/' + token
    client = email_flow['client']
    assert client.get(path).status_code == 200
    answers = {'maintenance_overall': 2, 'issue_resolution': 'unresolved',
               'maintenance_response_time': 'not_sure', 'maintenance_comment': 'Fictional faucet still leaks.'}
    result = client.post(path + '/submit', json={'answers': answers}, headers={'Origin': 'http://127.0.0.1:53004'})
    assert result.status_code == 200, result.text
    assert result.json()['answers'] == answers
    assert client.post(path + '/unsubscribe', headers={'Origin': 'http://127.0.0.1:53004'}).status_code == 200
    with email_flow['sessions']() as db:
        assert operate(db, 'prepare', 'second-test')['status'] == 'suppressed_opt_out'
        with pytest.raises(ValueError, match='opted out'):
            operate(db, 'reserve', 'second-test')
