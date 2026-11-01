"""The demo bootstrap cannot repurpose or reset an existing application database."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.base import Base
from src.models.organization import Organization
from src.models.user import User
from src.models.survey import SurveyInstance
from src.survey_demo import initialize_demo, demo_community, DEMO_EMAIL, DEMO_NAME


def test_demo_init_requires_explicit_mode_even_on_empty_storage(monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    monkeypatch.delenv('BOOMSAY_SURVEY_DEMO', raising=False)
    with sessionmaker(bind=engine)() as db:
        with pytest.raises(ValueError, match='BOOMSAY_SURVEY_DEMO'):
            initialize_demo(db, password='synthetic-password-123')
        assert db.query(Organization).count() == 0
        assert db.query(User).count() == 0
    engine.dispose()


def test_demo_init_retains_existing_credentials_and_creates_no_completed_fixture(monkeypatch):
    from src.api import auth
    # Hashing is separately covered by auth; this test pins preservation/no resets.
    calls = []
    def synthetic_hash(password):
        calls.append(password)
        return 'synthetic-hash-for-isolated-test'
    monkeypatch.setattr(auth, 'hash_password', synthetic_hash)
    monkeypatch.setenv('BOOMSAY_SURVEY_DEMO', 'true')
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        result = initialize_demo(db, password='synthetic-password-123')
        assert result == {'community_id': 1, 'manager_email': DEMO_EMAIL, 'created': True,
            'message': 'Created fictional demo community and manager; no survey exists yet.'}
        assert db.query(Organization).one().name == DEMO_NAME
        assert db.query(Organization).one().ai_analysis_enabled is False
        user = db.query(User).one()
        assert user.password_hash == 'synthetic-hash-for-isolated-test'
        assert user.role == 'owner'
        assert user.weekly_digest_enabled is False
        assert user.daily_digest_enabled is False
        assert db.query(SurveyInstance).count() == 0
        repeat = initialize_demo(db, password='must-not-change-an-existing-password')
        assert repeat['created'] is False
        assert demo_community(db).id == 1
        assert db.query(User).one().password_hash == 'synthetic-hash-for-isolated-test'
        assert calls == ['synthetic-password-123']
    engine.dispose()


def test_demo_init_refuses_existing_community_before_any_change(survey_flow, monkeypatch):
    monkeypatch.setenv('BOOMSAY_SURVEY_DEMO', 'true')
    with survey_flow['sessions']() as db:
        before_communities = [(row.id, row.name, row.ai_analysis_enabled) for row in db.query(Organization).order_by(Organization.id)]
        before_users = [(row.id, row.email, row.password_hash) for row in db.query(User).order_by(User.id)]
        with pytest.raises(ValueError, match='not the isolated fictional survey database'):
            initialize_demo(db, password='synthetic-password-123')
        assert [(row.id, row.name, row.ai_analysis_enabled) for row in db.query(Organization).order_by(Organization.id)] == before_communities
        assert [(row.id, row.email, row.password_hash) for row in db.query(User).order_by(User.id)] == before_users
        assert db.query(SurveyInstance).count() == 0
