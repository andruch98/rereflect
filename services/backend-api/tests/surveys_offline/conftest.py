"""Real survey HTTP/auth/persistence tests with every outbound boundary blocked.

Run from backend-api:
  ../../work/venv/bin/pytest --confcutdir=tests/surveys_offline tests/surveys_offline
"""
import os

os.environ.setdefault('JWT_SECRET', 'survey-offline-test-not-a-production-secret')
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['CACHE_ENABLED'] = 'false'

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.api.auth import create_access_token
from src.database.session import get_db
from src.models.base import Base
from src.models.organization import Organization
from src.models.user import User


def headers_for(user):
    return {'Authorization': 'Bearer ' + create_access_token({
        'user_id': user.id, 'organization_id': user.organization_id, 'role': user.role})}


def fictional_event(community_id, **changes):
    return {
        'event_id': 'synthetic-event-001', 'occurrence_id': 'synthetic-occurrence-001',
        'event_type': 'maintenance_completed', 'community_id': community_id,
        'ticket_id': 'SYNTH-M-1001', 'request_description': 'the fictional kitchen faucet repair',
        'completed_at': '2026-10-28T14:30:00-04:00',
        'resident_id': 'synthetic-resident-1', 'resident_name': 'Fictional Jordan',
        'resident_email': 'jordan@boomsay.example.invalid',
        'unit_id': 'synthetic-unit-101', 'unit_number': '101', 'is_simulated': True,
        **changes,
    }


@pytest.fixture
def survey_flow(monkeypatch, tmp_path):
    # A fake key deliberately exists: the simulator must remain fake regardless.
    monkeypatch.setenv('RESEND_API_KEY', 'synthetic-never-sent')
    monkeypatch.setenv('BOOMSAY_SURVEY_SIMULATION', 'true')
    monkeypatch.setenv('BOOMSAY_REVIEW_PREVIEW', 'false')
    monkeypatch.setenv('SURVEY_PUBLIC_BASE_URL', 'http://testserver')

    blocked_calls = []
    def forbidden(*args, **kwargs):
        blocked_calls.append((args, kwargs))
        raise AssertionError('Survey tests must not contact a provider or queue background work')

    import requests
    from celery import Celery
    from celery.app.task import Task
    from src.services import email_service
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)
    monkeypatch.setattr(email_service, '_send_email', forbidden)
    monkeypatch.setattr(Celery, 'send_task', forbidden)
    monkeypatch.setattr(Task, 'delay', forbidden)
    monkeypatch.setattr(Task, 'apply_async', forbidden)

    database_url = 'sqlite:///' + str(tmp_path / 'fictional-survey-tests.sqlite3')
    engine = create_engine(database_url, connect_args={'check_same_thread': False})
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        community = Organization(name='Fictional Survey Test Community', plan='enterprise')
        other_community = Organization(name='Other Fictional Community', plan='enterprise')
        db.add_all([community, other_community]); db.flush()
        manager = User(email='manager@survey.example.invalid', password_hash='unused',
                       organization_id=community.id, role='admin')
        member = User(email='member@survey.example.invalid', password_hash='unused',
                      organization_id=community.id, role='member')
        other_manager = User(email='other@survey.example.invalid', password_hash='unused',
                             organization_id=other_community.id, role='admin')
        db.add_all([manager, member, other_manager]); db.commit()

    from src.api.routes import surveys as routes
    app = FastAPI()
    app.include_router(routes.router)
    # The service intentionally uses one request/transaction session at a time.
    def get_test_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = get_test_db
    with TestClient(app, raise_server_exceptions=False) as client:
        def simulate(**changes):
            return client.post('/api/v1/surveys/simulate', headers=headers_for(manager),
                               json=fictional_event(community.id, **changes))
        yield {
            'client': client, 'app': app, 'sessions': sessions, 'engine': engine,
            'database_url': database_url, 'community': community, 'other_community': other_community,
            'manager': manager, 'member': member, 'other_manager': other_manager,
            'headers': headers_for(manager), 'other_headers': headers_for(other_manager),
            'simulate': simulate, 'blocked_calls': blocked_calls,
        }
    engine.dispose()
    assert blocked_calls == [], 'A simulation attempted outbound delivery or background work'
