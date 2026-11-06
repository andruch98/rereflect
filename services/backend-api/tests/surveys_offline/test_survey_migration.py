"""The additive survey migration preserves reviews/chats and matches ORM schema."""
import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from src.models.agent_settings import CommunityAgentSettings
from src.models.review_reply import ReviewReply
from src.models.survey import SurveyResident, SurveyUnit, MaintenanceOccurrence, SurveyInstance, SurveyInvitation, SurveyEmailOptOut


def test_survey_schema_upgrade_roundtrip_and_existing_records():
    root = Path(__file__).parents[2]
    config = Config()
    config.set_main_option('script_location', str(root / 'alembic'))
    script = ScriptDirectory.from_config(config)
    migration = script.get_revision('f2e8463ab154').module
    lifecycle = script.get_revision('a3c927b6d801').module
    settings = script.get_revision('b46200d17e11').module
    replies = script.get_revision('9b14ce392ac1').module
    manager_workflows = script.get_revision('46eeba18d492').module
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE organizations (id INTEGER PRIMARY KEY, name TEXT)'))
        connection.execute(text("INSERT INTO organizations VALUES (1, 'Existing community')"))
        connection.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE feedback_items (id INTEGER PRIMARY KEY, text TEXT, apartment_analysis JSON)'))
        connection.execute(text("INSERT INTO feedback_items VALUES (10, 'Original review', :analysis)"),
                           {'analysis': '{"saved":true}'})
        connection.execute(text('CREATE TABLE conversations (id INTEGER PRIMARY KEY, title TEXT)'))
        connection.execute(text("INSERT INTO conversations VALUES (20, 'Existing private chat')"))
        with Operations.context(MigrationContext.configure(connection)):
            for revision in (migration, lifecycle, settings, replies, manager_workflows):
                revision.upgrade()
            inspector = inspect(connection)
            for model in (SurveyResident, SurveyUnit, MaintenanceOccurrence, SurveyInstance, SurveyInvitation, SurveyEmailOptOut,
                          CommunityAgentSettings, ReviewReply):
                actual = {column['name']: column for column in inspector.get_columns(model.__tablename__)}
                assert set(actual) == set(model.__table__.columns.keys())
                for column in model.__table__.columns:
                    assert actual[column.name]['nullable'] == column.nullable
            assert connection.execute(text('SELECT * FROM organizations')).one() == (1, 'Existing community')
            assert connection.execute(text('SELECT * FROM feedback_items')).one() == (10, 'Original review', '{"saved":true}')
            assert connection.execute(text('SELECT * FROM conversations')).one() == (20, 'Existing private chat')
            assert inspector.get_unique_constraints('survey_invitations')[0]['column_names'] == ['survey_id']
            for revision in (manager_workflows, replies, settings, lifecycle, migration):
                revision.downgrade()
            assert not (set(inspect(connection).get_table_names()) & {
                'survey_residents', 'survey_units', 'maintenance_occurrences', 'survey_instances', 'survey_invitations', 'survey_email_opt_outs'})
            migration.upgrade()
    engine.dispose()
    assert script.get_heads() == [manager_workflows.revision]
    assert (manager_workflows.down_revision, replies.down_revision, settings.down_revision) == (
        replies.revision, settings.revision, lifecycle.revision)
    assert lifecycle.down_revision == migration.revision
    assert script.get_revision(migration.revision).down_revision == 'e1d7352fa043'


def test_lifecycle_upgrade_preserves_maintenance_links_drafts_and_final_responses():
    """Upgrade an old schema containing real-shaped saved records, not an empty DB."""
    from datetime import datetime, timezone
    import pytest
    root = Path(__file__).parents[2]
    migrations = []
    for name in ['f2e8463ab154_add_maintenance_surveys', 'a3c927b6d801_expand_survey_lifecycle']:
        spec = importlib.util.spec_from_file_location(name, root / 'alembic/versions' / (name + '.py'))
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migrations.append(migration)
    engine = create_engine('sqlite://')
    now = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        connection.execute(text('CREATE TABLE organizations (id INTEGER PRIMARY KEY)'))
        connection.execute(text('INSERT INTO organizations VALUES (1)'))
        migrations[0].upgrade()
        connection.execute(SurveyResident.__table__.insert().values(id=1, organization_id=1, resident_id='legacy-resident', name='Fictional Resident', email='legacy@example.invalid'))
        connection.execute(SurveyUnit.__table__.insert().values(id=1, organization_id=1, unit_id='legacy-unit', number='201'))
        occurrence = dict(organization_id=1, event_type='maintenance_completed', ticket_id='legacy-ticket', request_description='original request',
            completed_at=now, resident_record_id=1, unit_record_id=1, resident_id='legacy-resident', resident_name='Fictional Resident',
            resident_email='legacy@example.invalid', unit_id='legacy-unit', unit_number='201', employee_id='legacy-tech', employee_name='Fictional Tech')
        for index, status in [(1, 'submitted'), (2, 'pending')]:
            connection.execute(MaintenanceOccurrence.__table__.insert().values(**occurrence, id=index, event_id=f'legacy-event-{index}', occurrence_id=f'legacy-occurrence-{index}'))
            connection.execute(SurveyInstance.__table__.insert().values(id=index, public_id=f'legacy-public-{index}', organization_id=1, occurrence_id=index,
                token=f'original-private-link-{index}', questionnaire_snapshot={'id': 'maintenance_v1', 'version': 1, 'questions': [{'id': 'maintenance_comment', 'text': 'Original question'}]},
                context_snapshot={'ticket_completed_at': now.isoformat(), 'ticket_id': 'legacy-ticket'},
                answers={'maintenance_comment': 'Original submitted answer'} if status == 'submitted' else {},
                draft_answers={'maintenance_comment': 'Original unsent draft'} if status == 'pending' else {},
                status=status, submitted_at=now if status == 'submitted' else None))
            connection.execute(SurveyInvitation.__table__.insert().values(id=index, organization_id=1, survey_id=index, status='simulated', recipient='legacy@example.invalid',
                subject='Original invitation', html='<p>Original</p>', text='Original', survey_url=f'http://localhost/survey/original-private-link-{index}'))
        tables = ['survey_residents', 'survey_units', 'maintenance_occurrences', 'survey_instances', 'survey_invitations']
        # Preserve values for every historical column when later upgrades append new ones.
        columns = {table: ', '.join(col['name'] for col in inspect(connection).get_columns(table)) for table in tables}
        before = {table: connection.execute(text(f'SELECT {columns[table]} FROM {table} ORDER BY id')).all() for table in tables}
        migrations[1].upgrade()
        assert {table: connection.execute(text(f'SELECT * FROM {table} ORDER BY id')).all() for table in tables} == before
        config = Config()
        config.set_main_option('script_location', str(root / 'alembic'))
        script = ScriptDirectory.from_config(config)
        connection.execute(text('CREATE TABLE feedback_items (id INTEGER PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        for feature_revision in ('b46200d17e11', '9b14ce392ac1', '46eeba18d492'):
            script.get_revision(feature_revision).module.upgrade()
        assert {table: connection.execute(text(f'SELECT {columns[table]} FROM {table} ORDER BY id')).all()
                for table in tables} == before
        assert connection.execute(text('SELECT reviewed_at,reviewed_by FROM survey_instances')).all() == [(None, None)] * 2
        assert connection.execute(text('SELECT s.token, m.ticket_id FROM survey_instances s JOIN maintenance_occurrences m ON m.id=s.occurrence_id ORDER BY s.id')).all() == [
            ('original-private-link-1', 'legacy-ticket'), ('original-private-link-2', 'legacy-ticket')]
        constraints = {tuple(item['column_names']) for item in inspect(connection).get_unique_constraints('maintenance_occurrences')}
        assert {('organization_id', 'event_id'), ('organization_id', 'occurrence_id')} <= constraints
        lifecycle = {**occurrence, 'ticket_id': None, 'request_description': None, 'event_type': 'move_in_completed', 'employee_id': None, 'employee_name': None}
        connection.execute(MaintenanceOccurrence.__table__.insert().values(**lifecycle, id=3, event_id='new-event', occurrence_id='new-occurrence'))
        with pytest.raises(RuntimeError, match='preserve their data'):
            migrations[1].downgrade()
        assert connection.execute(text('SELECT COUNT(*) FROM maintenance_occurrences')).scalar_one() == 3
        assert connection.execute(text('SELECT token FROM survey_instances ORDER BY id')).scalars().all() == ['original-private-link-1', 'original-private-link-2']
    engine.dispose()
