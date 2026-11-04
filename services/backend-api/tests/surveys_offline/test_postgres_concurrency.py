"""Optional genuine PostgreSQL races in a newly generated, disposable schema."""
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from conftest import fictional_event
from src.database.session import get_db
from src.models.base import Base
from src.models.organization import Organization
from src.models.survey import SurveyInstance, SurveyInvitation, MaintenanceOccurrence
from test_journey import FINAL


@pytest.fixture
def postgres_flow(survey_flow):
    url = os.getenv('TEST_SURVEY_POSTGRES_URL')
    if not url:
        pytest.skip('Set TEST_SURVEY_POSTGRES_URL to isolated loopback test PostgreSQL')
    parsed = make_url(url)
    if parsed.host not in ('127.0.0.1', 'localhost') or parsed.database not in ('survey_test', 'survey_concurrency'):
        pytest.fail('Concurrency tests require the named, isolated loopback survey test database')
    schema = 'survey_race_' + uuid4().hex
    base_engine = create_engine(url)
    with base_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    engine = base_engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        community = Organization(name='Isolated Fictional Concurrent Community', plan='enterprise')
        db.add(community); db.commit()
    from src.api.routes import surveys as routes
    from src.services.surveys import ingest_simulated_event
    with sessions() as db:
        survey = ingest_simulated_event(db, routes.MaintenanceCompletedEvent.model_validate(fictional_event(community.id)))
        path = '/api/v1/resident-surveys/' + survey.token
    app = FastAPI(); app.include_router(routes.router)
    def get_test_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = get_test_db
    try:
        yield {'app': app, 'sessions': sessions, 'path': path, 'community': community, 'routes': routes}
    finally:
        # Only this UUID schema is removed; existing application/test tables are untouched.
        with base_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        base_engine.dispose()


def test_concurrent_final_submissions_choose_one_immutable_answer_set(postgres_flow, monkeypatch):
    flow = postgres_flow
    original_lookup = flow['routes'].resident_survey
    ready = Barrier(2)
    def both_read_pending(token, db):
        row = original_lookup(token, db)
        ready.wait(timeout=10)
        return row
    monkeypatch.setattr(flow['routes'], 'resident_survey', both_read_pending)
    alternate = {**FINAL, 'issue_resolution': 'resolved', 'maintenance_overall': 5}
    def submit(answers):
        with TestClient(flow['app']) as client:
            return client.post(flow['path'] + '/submit', json={'answers': answers})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, [FINAL, alternate]))
    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json()['answers'] == responses[1].json()['answers']
    assert responses[0].json()['answers'] in (FINAL, alternate)
    with flow['sessions']() as db:
        row = db.query(SurveyInstance).one()
        assert row.answers == responses[0].json()['answers']
        assert row.status == 'submitted'
        assert row.draft_answers == {}


def test_concurrent_late_draft_cannot_overwrite_completed_answers(postgres_flow, monkeypatch):
    flow = postgres_flow
    original_lookup = flow['routes'].resident_survey
    ready = Barrier(2)
    def both_read_pending(token, db):
        row = original_lookup(token, db)
        ready.wait(timeout=10)
        return row
    monkeypatch.setattr(flow['routes'], 'resident_survey', both_read_pending)
    def save(kind):
        with TestClient(flow['app']) as client:
            if kind == 'final':
                return client.post(flow['path'] + '/submit', json={'answers': FINAL})
            return client.put(flow['path'] + '/draft', json={'answers': {'issue_resolution': 'resolved'}})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(save, ['final', 'draft']))
    assert all(response.status_code == 200 for response in responses)
    with flow['sessions']() as db:
        row = db.query(SurveyInstance).one()
        assert row.status == 'submitted'
        assert row.answers == FINAL
        assert row.draft_answers == {}


def test_concurrent_partial_drafts_merge_disjoint_fields_from_stale_reads(postgres_flow, monkeypatch):
    flow = postgres_flow
    original_lookup = flow['routes'].resident_survey
    ready = Barrier(2)
    def both_read_empty_draft(token, db):
        row = original_lookup(token, db)
        assert row.draft_answers == {}
        # Force both independent request sessions to hold the same stale JSON.
        ready.wait(timeout=10)
        return row
    monkeypatch.setattr(flow['routes'], 'resident_survey', both_read_empty_draft)
    partials = [{'maintenance_overall': 2}, {'issue_resolution': 'unresolved'}]
    def save(answers):
        with TestClient(flow['app']) as client:
            return client.put(flow['path'] + '/draft', json={'answers': answers})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(save, partials))
    assert all(response.status_code == 200 for response in responses)
    with flow['sessions']() as db:
        row = db.query(SurveyInstance).one()
        assert row.status == 'draft'
        assert row.submitted_at is None
        assert row.answers == {}
        assert row.draft_answers == {'maintenance_overall': 2, 'issue_resolution': 'unresolved'}


def test_concurrent_same_event_creates_one_occurrence_and_invitation(postgres_flow):
    from src.api.routes.surveys import MaintenanceCompletedEvent
    from src.services.surveys import ingest_simulated_event
    flow = postgres_flow
    ready = Barrier(2)
    event = MaintenanceCompletedEvent.model_validate(fictional_event(flow['community'].id,
        event_id='synthetic-race-event', occurrence_id='synthetic-race-occurrence', ticket_id='SYNTH-M-RACE'))
    def ingest(_):
        with flow['sessions']() as db:
            ready.wait(timeout=10)
            row = ingest_simulated_event(db, event)
            return row.public_id, row.token
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(ingest, range(2)))
    assert results[0] == results[1]
    with flow['sessions']() as db:
        # One initial fixture occurrence, one raced occurrence.
        assert db.query(SurveyInstance).count() == 2
        assert db.query(MaintenanceOccurrence).count() == 2
        assert db.query(SurveyInvitation).count() == 2
