"""Offline handoff verification uses the saved resident submission and real routes."""
from urllib.parse import urlsplit
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from conftest import fictional_event, headers_for
from src.api.routes import surveys as survey_routes
from src.database.session import get_db
from src.models.ask_genius_share import AskGeniusShare
from src.models.base import Base
from src.models.conversation import Conversation
from src.models.conversation_message import ConversationMessage
from src.models.organization import Organization
from src.models.survey import SurveyInstance
from src.models.user import User
from src.services import ask_genius as ask_service
from src.survey_demo import initialize_demo, verify_ask
from test_journey import FINAL


@pytest.fixture
def demo_ask_flow(survey_flow, monkeypatch, tmp_path):
    # Reuse the outer fixture's fail-closed provider/job boundaries, but use a
    # different file database initialized by the actual guarded demo bootstrap.
    monkeypatch.setenv('BOOMSAY_SURVEY_DEMO', 'true')
    monkeypatch.setenv('BOOMSAY_REVIEW_PREVIEW', 'true')
    monkeypatch.setenv('BOOMSAY_PREVIEW_ORGANIZATION_ID', '1')
    monkeypatch.setenv('ASK_GENIUS_ENABLED', 'false')
    monkeypatch.setenv('ASK_GENIUS_PROVIDER', 'openai')
    monkeypatch.setenv('ASK_GENIUS_MODEL', 'synthetic-config-must-stay-unchanged')
    monkeypatch.setenv('ASK_GENIUS_API_KEY', 'synthetic-config-key-never-sent')
    engine = create_engine('sqlite:///' + str(tmp_path / 'isolated-demo-ask.sqlite3'),
                           connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        initialize_demo(db, password='isolated-demo-password-123')
        user = db.query(User).one()
    app = FastAPI(); app.include_router(survey_routes.router)
    def isolated_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = isolated_db
    with TestClient(app) as client:
        yield {'client': client, 'sessions': sessions, 'headers': headers_for(user)}
    engine.dispose()


def ingest_demo(flow):
    response = flow['client'].post('/api/v1/surveys/simulate', headers=flow['headers'],
        json=fictional_event(1))
    assert response.status_code == 200, response.text
    detail = response.json()
    token = urlsplit(detail['invitation']['survey_url']).path.split('/')[-1]
    return detail, '/api/v1/resident-surveys/' + token


def test_offline_verify_ask_uses_actual_submission_and_restores_configuration(demo_ask_flow):
    flow = demo_ask_flow
    detail, path = ingest_demo(flow)
    submitted = flow['client'].post(path + '/submit', json={'answers': FINAL})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()['status'] == 'submitted'
    config_keys = ('ASK_GENIUS_ENABLED', 'ASK_GENIUS_PROVIDER', 'ASK_GENIUS_MODEL',
                   'ASK_GENIUS_API_KEY', 'BOOMSAY_PREVIEW_ORGANIZATION_ID')
    environment_before = {key: os.environ.get(key) for key in config_keys}
    configured_before = ask_service.configured_llm
    generator_before = ask_service.generate_answer
    with flow['sessions']() as db:
        original_reason = configured_before(1, db)
        result = verify_ask(db)
        assert result['verification_mode'] == 'offline_mock'
        assert result['live_model_calls'] == 0
        assert result['counts_source'] == 'application_records'
        assert result['conversation_title'] == '[OFFLINE MOCK] Survey verification'
        assert result['sharing_status'] == 'unavailable'
        assert len(result['results']) == 4
        assert len(result['mocked_model_calls']) == 2
        assert all(call['mocked'] is True for call in result['mocked_model_calls'])
        assert all(call['survey_ids'] == [detail['public_id']] for call in result['mocked_model_calls'])
        assert all(call['original_question_count'] == 4 for call in result['mocked_model_calls'])
        links = [link for answer in result['results'] for link in answer['evidence_links']]
        assert links
        assert all(link == {'survey_id': detail['public_id'], 'href': '/surveys/' + detail['public_id'],
                            'detail_http_status': 200} for link in links)
        assert all(answer['survey_counts']['submission_count'] == 1 for answer in result['results'])
        assert all(answer['survey_counts']['distinct_resident_count'] == 1 for answer in result['results'])
        assert all(answer['survey_counts']['issue_resolution_counts']['unresolved'] == 1 for answer in result['results'])
        conversation = db.query(Conversation).filter_by(public_id=result['conversation_id']).one()
        assert conversation.title == '[OFFLINE MOCK] Survey verification'
        messages = db.query(ConversationMessage).filter_by(conversation_id=conversation.id).all()
        assert len(messages) == 8
        assert len([message for message in messages if message.role == 'assistant']) == 4
        assert db.query(AskGeniusShare).count() == 0
        assert db.query(SurveyInstance).one().answers == FINAL
        assert db.query(Organization).one().ai_analysis_enabled is False
        assert configured_before(1, db) == original_reason
    assert {key: os.environ.get(key) for key in config_keys} == environment_before
    assert ask_service.configured_llm is configured_before
    assert ask_service.generate_answer is generator_before


def test_offline_verify_ask_requires_final_submission_and_creates_no_chat(demo_ask_flow):
    flow = demo_ask_flow
    _, path = ingest_demo(flow)
    assert flow['client'].put(path + '/draft', json={'answers': {'maintenance_overall': 2}}).status_code == 200
    configured_before = ask_service.configured_llm
    generator_before = ask_service.generate_answer
    with flow['sessions']() as db:
        with pytest.raises(ValueError, match='Submit the actual resident form'):
            verify_ask(db)
        assert db.query(Conversation).count() == 0
        assert db.query(ConversationMessage).count() == 0
        assert db.query(AskGeniusShare).count() == 0
    assert ask_service.configured_llm is configured_before
    assert ask_service.generate_answer is generator_before


def test_offline_verify_ask_refuses_foreign_storage_without_changing_it(survey_flow, monkeypatch):
    monkeypatch.setenv('BOOMSAY_SURVEY_DEMO', 'true')
    with survey_flow['sessions']() as db:
        original = [(org.id, org.name) for org in db.query(Organization).order_by(Organization.id)]
        with pytest.raises(ValueError, match='not the isolated fictional survey database'):
            verify_ask(db)
        assert [(org.id, org.name) for org in db.query(Organization).order_by(Organization.id)] == original
        assert db.query(Conversation).count() == 0
        assert db.query(AskGeniusShare).count() == 0


@pytest.mark.parametrize('event_type', ['move_in_completed', 'maintenance_completed', 'lease_month_3', 'lease_month_6', 'lease_month_9', 'lease_renewed', 'move_out_completed'])
def test_selected_lifecycle_demo_verifies_actual_submitted_type_without_live_model(demo_ask_flow, event_type):
    import json
    from pathlib import Path
    cases = json.loads((Path(__file__).parents[4] / 'experiments/lifecycle_surveys/fixtures.json').read_text())
    expected = None
    for case in cases:
        response = demo_ask_flow['client'].post('/api/v1/surveys/simulate', headers=demo_ask_flow['headers'], json=case['event'])
        assert response.status_code == 200, response.text
        row = response.json()
        token = urlsplit(row['invitation']['survey_url']).path.split('/')[-1]
        assert demo_ask_flow['client'].post('/api/v1/resident-surveys/' + token + '/submit', json={'answers': case['final_answers']}).status_code == 200
        if case['event']['event_type'] == event_type:
            expected = row['public_id']
    with demo_ask_flow['sessions']() as db:
        result = verify_ask(db, event_type)
        assert result['live_model_calls'] == 0
        assert len(result['mocked_model_calls']) == 2
        assert all(call['survey_ids'] == [expected] for call in result['mocked_model_calls'])
        assert all(answer['survey_counts']['submission_count'] == 1 for answer in result['results'])
        assert all(answer['survey_counts']['survey_type_counts'] == {event_type: 1} for answer in result['results'])
        assert all(link['survey_id'] == expected for answer in result['results'] for link in answer['evidence_links'])
        assert result['sharing_status'] == 'unavailable'
