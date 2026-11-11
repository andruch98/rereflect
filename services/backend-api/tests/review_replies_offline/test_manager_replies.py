"""Manager walk-through on fictional data. Uses real HTTP routing, auth, persistence and zero network."""
import os
import asyncio
from types import SimpleNamespace

os.environ.setdefault('JWT_SECRET', 'fictional-review-test-secret-at-least-32-chars')
os.environ.setdefault('DATABASE_URL', 'sqlite://')

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.auth import create_access_token
from src.api.routes import agent_settings, feedback, review_replies
from src.database.session import get_db
from src.models import Base, FeedbackItem, FeedbackWorkflowEvent, Organization, ReviewReply, User
from src.models.agent_settings import CommunityAgentSettings
from src.services import review_replies as service, review_reply_writer as writer
from src.services.agent_settings import review_defaults


@pytest.fixture
def flow(tmp_path, monkeypatch):
    monkeypatch.setenv('BOOMSAY_REVIEW_PREVIEW', 'true')
    monkeypatch.setenv('BOOMSAY_PREVIEW_ORGANIZATION_ID', '1')
    monkeypatch.delenv('ASK_GENIUS_ENABLED', raising=False)
    engine = create_engine(f'sqlite:///{tmp_path}/reviews.sqlite3', connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr('src.database.session.SessionLocal', sessions)
    with sessions() as db:
        org = Organization(id=1, name='Fictional Lake House')
        db.add_all([org, Organization(id=2, name='Other community'),
            User(id=1, organization_id=1, role='owner', email='manager@example.test'),
            User(id=2, organization_id=2, role='owner', email='other@example.test'),
            FeedbackItem(id=1, organization_id=1, source='apartment_review_ai', star_rating=4,
                         text='It was a great move but the stairwell feels unsafe.',
                         source_metadata={'author_name': 'Alex', 'private_email': 'private@example.test'}),
            FeedbackItem(id=2, organization_id=1, source='apartment_review_fallback', star_rating=5, text='Great move!'),
            FeedbackItem(id=3, organization_id=2, source='apartment_review_ai', star_rating=5, text='Other community.'),
            FeedbackItem(id=4, organization_id=1, source='slack', text='Private support request.')])
        db.commit()
        settings = review_defaults(org).model_dump()
    app = FastAPI()
    app.include_router(review_replies.router)
    app.include_router(agent_settings.router)
    app.include_router(feedback.router)
    def provide_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = provide_db
    cli = TestClient(app)
    cli.headers.update({'Authorization': 'Bearer ' + create_access_token({'user_id': 1, 'organization_id': 1, 'role': 'owner'})})
    yield SimpleNamespace(cli=cli, db=sessions, values=settings)
    engine.dispose()


ROOT = '/api/v1/review-replies'
SETTINGS = '/api/v1/agent-settings/reviews'


def confirm(flow, **changes):
    r = flow.cli.put(SETTINGS, json={'version': 0, 'values': dict(flow.values, **changes)})
    assert r.status_code == 200, r.text
    return r


def test_onboard_preview_hold_edit_approve_filter(flow):
    cli = flow.cli
    assert cli.get(f'{ROOT}/1').json()['settings_confirmed'] is False
    assert cli.post(f'{ROOT}/1/draft').status_code == 409
    values = dict(flow.values, mode='automatic', public_phone='555-0100')
    p = cli.post(ROOT + '/preview', json=values)
    assert p.status_code == 200, p.text
    first, second = p.json()['examples']
    assert p.json()['publishing_connected'] is False
    assert (first['status'], second['status']) == ('approved', 'pending_approval')
    assert 'safety' in second['reason']
    assert second['text'] == (
        'Thank you for bringing this concern to our attention. '
        'Please visit our office or call so we can arrange a maintenance '
        'to come and fix the broken lock asap.\n\n' + values['signature'])
    assert first['generation_method'] == 'example'
    assert cli.get(f'{ROOT}/1').json()['status'] == 'not_drafted'
    confirm(flow, mode='automatic', public_phone='555-0100')
    result = cli.post(f'{ROOT}/1/draft').json()
    assert result['text'].startswith('Alex,') and 'private@example.test' not in result['text']
    assert result['status'] == 'pending_approval' and result['generation_method'] == 'example'
    assert cli.post(f'{ROOT}/1/draft').json()['version'] == result['version']
    auto = cli.post(f'{ROOT}/2/draft').json()
    assert auto['status'] == 'approved' and auto['approved_by'] == 'BoomSay' and auto['published_at'] is None
    edited = cli.put(f'{ROOT}/1', json={'version': 1, 'text': 'Thank you for raising the stairwell concern.'}).json()
    assert edited['version'] == 2 and edited['status'] == 'pending_approval'
    assert cli.post(f'{ROOT}/1/approve', json={'version': 1}).status_code == 409
    final = cli.post(f'{ROOT}/1/approve', json={'version': 2, 'text': 'Please reach our team about the stairwell.'}).json()
    assert final['approved_by'] == 'manager@example.test' and final['published_at'] is None
    assert final['approved_at'].endswith(('Z', '+00:00'))
    assert cli.get(SETTINGS.rsplit('/', 1)[0]).json()['reviews']['values'] == values
    listing = cli.get('/api/v1/feedback/', params={'response_status': 'approved', 'page_size': 1})
    assert listing.status_code == 200, listing.text
    assert listing.json()['total'] == 2 and len(listing.json()['items']) == 1
    assert listing.json()['items'][0]['response_status'] == 'approved'
    assert cli.get('/api/v1/feedback/', params={'response_status': 'published'}).json()['total'] == 0
    with flow.db() as db:
        assert db.query(FeedbackWorkflowEvent).filter_by(feedback_id=1).count() == 3


def test_community_scope_and_empty_edit(flow):
    for review_id in (3, 4):
        assert flow.cli.get(f'{ROOT}/{review_id}').status_code == 404
        assert flow.cli.post(f'{ROOT}/{review_id}/draft').status_code == 404
        assert flow.cli.post(f'{ROOT}/{review_id}/approve', json={'version': 1}).status_code == 404
    assert flow.cli.put(f'{ROOT}/1', json={'text': '  ', 'version': 1}).status_code == 422


def test_saved_draft_identifies_settings_changes_without_rewriting_it(flow):
    first = confirm(flow, public_phone='555-0100').json()
    draft = flow.cli.post(f'{ROOT}/1/draft').json()
    assert draft['uses_previous_settings'] is False
    assert '555-0100' in draft['text']
    change = flow.cli.put(SETTINGS, json={
        'version': first['version'], 'values': {**first['values'], 'public_phone': '555-0199'}})
    assert change.status_code == 200, change.text
    original = flow.cli.get(f'{ROOT}/1').json()
    assert original['text'] == draft['text']
    assert original['status'] == 'pending_approval'
    assert original['uses_previous_settings'] is True
    assert flow.cli.get(f'{ROOT}/2').json()['uses_previous_settings'] is False


def test_settings_changed_during_generation_never_auto_approve_old_draft(flow, monkeypatch):
    confirm(flow, mode='automatic')

    async def slow_writer(*args):
        with flow.db() as other_session:
            row = other_session.get(CommunityAgentSettings, (1, 'reviews'))
            row.settings = {**row.settings, 'mode': 'approval'}
            row.version += 1
            other_session.commit()
        return 'Thanks for your review.', 'example', None

    monkeypatch.setattr(service, 'write_reply', slow_writer)
    reply = flow.cli.post(f'{ROOT}/2/draft').json()
    assert reply['uses_previous_settings']
    assert reply['status'] == 'pending_approval'
    assert reply['approved_by'] is None and reply['approved_at'] is None


@pytest.mark.parametrize('role', ['member', 'unsupported-role'])
def test_nonmanagers_read_but_cannot_change_the_property_reply(flow, role):
    confirm(flow)
    pending = flow.cli.post(f'{ROOT}/1/draft').json()
    with flow.db() as db:
        db.add(User(id=3, organization_id=1, role=role, email='read-only@example.test'))
        db.commit()
    # Authorization follows the saved membership, even if an old token claims a prior role.
    flow.cli.headers['Authorization'] = 'Bearer ' + create_access_token(
        {'user_id': 3, 'organization_id': 1, 'role': 'owner'})
    assert flow.cli.get(f'{ROOT}/1').json() == pending
    assert flow.cli.post(f'{ROOT}/preview', json=flow.values).status_code == 403
    assert flow.cli.post(f'{ROOT}/2/draft').status_code == 403
    assert flow.cli.put(f'{ROOT}/1', json={'version': 1, 'text': 'Unapproved change'}).status_code == 403
    assert flow.cli.post(f'{ROOT}/1/approve', json={'version': 1}).status_code == 403
    with flow.db() as db:
        reply = db.get(ReviewReply, 1)
        assert (reply.status, reply.text, reply.version) == ('pending_approval', pending['text'], pending['version'])
        assert db.get(ReviewReply, 2) is None
        assert db.query(FeedbackWorkflowEvent).filter_by(feedback_id=1).count() == 1


def test_opt_in_new_review_only_failure_and_retry(flow, monkeypatch):
    asyncio.run(service.draft_new_reviews(1, [1]))
    with flow.db() as db:
        assert db.query(ReviewReply).count() == 0
    confirm(flow)
    async def offline(*args):
        raise OSError('private wrong address')
    with monkeypatch.context() as patch:
        patch.setattr(service, 'write_reply', offline)
        asyncio.run(service.draft_new_reviews(1, [1]))
    assert flow.cli.get(f'{ROOT}/1').json()['status'] == 'failed'
    assert 'private' not in flow.cli.get(f'{ROOT}/1').text
    assert flow.cli.post(f'{ROOT}/1/draft').json()['status'] == 'pending_approval'
    with flow.db() as db:
        assert db.query(ReviewReply).count() == 1


def test_false_contact_never_appears_in_generated_reply(flow, monkeypatch):
    confirm(flow)
    monkeypatch.setenv('ASK_GENIUS_ENABLED', 'true')
    monkeypatch.setenv('ASK_GENIUS_PROVIDER', 'openai')
    monkeypatch.setenv('ASK_GENIUS_MODEL', 'fictional-model')
    monkeypatch.setenv('ASK_GENIUS_API_KEY', 'fictional-never-used')
    seen = []
    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=self)
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def create(self, **kwargs):
            seen.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(
                content='Please email someone@wrong.test.', refusal=None))], usage=None)
    monkeypatch.setattr(writer.openai, 'AsyncOpenAI', FakeClient)
    result = flow.cli.post(f'{ROOT}/1/draft').json()
    assert len(seen) == 1 and result['status'] == 'failed' and result['text'] == ''
    assert 'private@example.test' not in str(seen) and 'Other community' not in str(seen)


def test_approved_auto_resets_on_manual_edit_and_never_posts(flow):
    confirm(flow, mode='automatic')
    generated = flow.cli.post(f'{ROOT}/2/draft').json()
    edited = flow.cli.put(f'{ROOT}/2', json={'text': 'Revised by the manager.', 'version': generated['version']}).json()
    assert edited['status'] == 'pending_approval'
    assert edited['approved_at'] is None and edited['approved_by'] is None and edited['published_at'] is None
    assert flow.cli.get('/api/v1/feedback/2').json()['response_status'] == 'pending_approval'
    assert flow.cli.post(f'{ROOT}/2/publish').status_code == 404


def test_import_integration_drafts_only_new_apartment_reviews(flow, monkeypatch):
    monkeypatch.setenv('CACHE_ENABLED', 'false')
    monkeypatch.setattr('src.background.queue_analyze_feedback', lambda *args: None)
    monkeypatch.setattr('src.background.queue_analyze_batch', lambda *args: None)
    monkeypatch.setattr('src.services.cache_service.cache_invalidate', lambda *args: None)
    monkeypatch.setattr('src.services.webhook_dispatcher.dispatch_webhook_event', lambda **kwargs: None)
    confirm(flow, mode='automatic')
    added = flow.cli.post('/api/v1/feedback/', json={'text':'I had a smooth move.', 'source':'apartment_review_ai', 'star_rating':5})
    assert added.status_code == 201, added.text
    assert flow.cli.get(f"{ROOT}/{added.json()['id']}").json()['approved_by'] == 'BoomSay'
    csv_data = 'text,source\nThere is a safety concern,apartment_review_fallback\nPrivate support ticket,slack\n'
    upload = flow.cli.post('/api/v1/feedback/import-csv', files={'file': ('feedback.csv', csv_data, 'text/csv')})
    assert upload.status_code == 200, upload.text
    assert upload.json()['imported_count'] == 2
    with flow.db() as db:
        assert db.query(ReviewReply).count() == 2
        assert db.query(ReviewReply).filter_by(status='pending_approval').count() == 1
    assert flow.cli.get(f'{ROOT}/1').json()['status'] == 'not_drafted'


def test_public_contact_matches_common_formatting_and_blocks_invented_local_number():
    contact = SimpleNamespace(public_email='team@example.test', public_phone='+1 (303) 555-1234 ext. 123')
    writer.confirmed_contacts('Call (303) 555-1234 ext 123 or email TEAM@EXAMPLE.TEST.', contact)
    writer.confirmed_contacts('Our team is at 303.555.1234.', contact)
    for text in ['Call 555-1234.', 'Call 303-555-1234 ext. 999.', 'Call 303-555-1235.']:
        with pytest.raises(writer.ReviewWriterError, match='unconfirmed public phone'):
            writer.confirmed_contacts(text, contact)


def test_high_rating_does_not_hide_an_unlatched_door(flow):
    settings = writer.ReviewSettings.model_validate(dict(flow.values, mode='automatic'))
    status, reason = writer.approval_policy(settings, "Great staff, but the side door doesn't latch.", 5)
    assert status == 'pending_approval' and 'safety' in reason
