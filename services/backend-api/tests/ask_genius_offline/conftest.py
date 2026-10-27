"""Isolated real API/auth/storage tests; model responses are always simulated.

Run: pytest --confcutdir=tests/ask_genius_offline tests/ask_genius_offline
This avoids importing unrelated application integrations and startup workers.
"""
import json
import os
from datetime import date
from uuid import uuid4

os.environ.setdefault('JWT_SECRET', 'ask-genius-offline-test-not-for-production')
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['CACHE_ENABLED'] = 'false'

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.auth import create_access_token
from src.api.routes import ask_genius as routes
from src.database.session import get_db
from src.models.base import Base
from src.models.feedback import FeedbackItem
from src.models.organization import Organization
from src.models.user import User
from src.services import ask_genius as service
from src.services import ask_genius_periods as periods


def headers_for(user):
    return {'Authorization': 'Bearer ' + create_access_token({'user_id': user.id, 'organization_id': user.organization_id})}


def saved(sentiment, topic, quote):
    return {'final_result': {'method': 'ai_model', 'sentiment': sentiment, 'topics': [
        {'name': topic, 'sentiment': sentiment, 'quotations': [{'text': quote, 'sentiment': sentiment}]}]}}


@pytest.fixture
def flow(monkeypatch):
    monkeypatch.setenv('BOOMSAY_REVIEW_PREVIEW', 'true')
    monkeypatch.setenv('ASK_GENIUS_ENABLED', 'true')
    monkeypatch.setenv('ASK_GENIUS_PROVIDER', 'openai')
    monkeypatch.setenv('ASK_GENIUS_MODEL', 'simulated-model')
    monkeypatch.setenv('ASK_GENIUS_API_KEY', 'synthetic-never-sent')
    monkeypatch.setattr(periods, 'community_today', lambda: date(2026, 10, 27))
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    org = Organization(name='Lake House test', plan='enterprise')
    db.add(org); db.flush()
    user = User(email='manager@example.invalid', password_hash='unused', organization_id=org.id, role='member')
    other_user = User(email='other@example.invalid', password_hash='unused', organization_id=org.id, role='member')
    db.add_all([user, other_user]); db.commit()
    monkeypatch.setenv('BOOMSAY_PREVIEW_ORGANIZATION_ID', str(org.id))
    rows = [
        FeedbackItem(organization_id=org.id, source='apartment_review_ai', review_date=date(2026,10,27), text='Helpful staff. Repairs took two weeks.', star_rating=2, apartment_analysis=saved('negative','Maintenance','Repairs took two weeks.')),
        FeedbackItem(organization_id=org.id, source='apartment_review_ai', review_date=date(2026,10,1), text='Friendly leasing team.', star_rating=5, apartment_analysis=saved('positive','Staff','Friendly leasing team.')),
        FeedbackItem(organization_id=org.id, source='apartment_review_ai', review_date=date(2026,9,30), text='Parking was crowded.', star_rating=2, apartment_analysis=saved('negative','Parking','Parking was crowded.')),
        FeedbackItem(organization_id=org.id, source='apartment_review_ai', review_date=None, text='Billing was unclear.', star_rating=1, apartment_analysis=saved('negative','Billing','Billing was unclear.')),
        FeedbackItem(organization_id=org.id, source='apartment_review_ai', review_date=date(2026,7,1), text='', star_rating=4, apartment_analysis={'final_result': {'method':'ai_model','sentiment':'positive','topics':[]}}),
    ]
    db.add_all(rows); db.commit()
    calls = []
    model = {'answer': 'Maintenance delays appeared in the selected reviews.', 'evidence': []}
    async def generate(messages, config):
        calls.append(messages)
        if model.get('exception'):
            raise model['exception']
        content = model.get('raw', json.dumps(model))
        return service.AnswerResult(content, {'simulated': True, 'content': content}, 100, 30, model.get('finish_reason','stop'))
    monkeypatch.setattr(service, 'generate_answer', generate)
    app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        def ask(question='What are the main complaints?', **extra):
            headers = extra.pop('headers', headers_for(user))
            return client.post('/api/v1/ask-genius/questions', headers=headers, json={
                'question': question, 'request_id': str(uuid4()), **extra})
        yield {'db':db,'user':user,'other_user':other_user,'org':org,'rows':rows,'client':client,
               'headers':headers_for(user),'ask':ask,'model':model,'calls':calls}
    db.close(); engine.dispose()
