"""The additive survey migration preserves reviews/chats and matches ORM schema."""
import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from src.models.survey import SurveyResident, SurveyUnit, MaintenanceOccurrence, SurveyInstance, SurveyInvitation, SurveyEmailOptOut


def test_survey_schema_upgrade_roundtrip_and_existing_records():
    root = Path(__file__).parents[2]
    path = root / 'alembic/versions/f2e8463ab154_add_maintenance_surveys.py'
    spec = importlib.util.spec_from_file_location('maintenance_survey_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE organizations (id INTEGER PRIMARY KEY, name TEXT)'))
        connection.execute(text("INSERT INTO organizations VALUES (1, 'Existing community')"))
        connection.execute(text('CREATE TABLE feedback_items (id INTEGER PRIMARY KEY, text TEXT, apartment_analysis JSON)'))
        connection.execute(text("INSERT INTO feedback_items VALUES (10, 'Original review', :analysis)"),
                           {'analysis': '{"saved":true}'})
        connection.execute(text('CREATE TABLE conversations (id INTEGER PRIMARY KEY, title TEXT)'))
        connection.execute(text("INSERT INTO conversations VALUES (20, 'Existing private chat')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            inspector = inspect(connection)
            for model in (SurveyResident, SurveyUnit, MaintenanceOccurrence, SurveyInstance, SurveyInvitation, SurveyEmailOptOut):
                actual = {column['name']: column for column in inspector.get_columns(model.__tablename__)}
                assert set(actual) == set(model.__table__.columns.keys())
                for column in model.__table__.columns:
                    assert actual[column.name]['nullable'] == column.nullable
            assert connection.execute(text('SELECT * FROM organizations')).one() == (1, 'Existing community')
            assert connection.execute(text('SELECT * FROM feedback_items')).one() == (10, 'Original review', '{"saved":true}')
            assert connection.execute(text('SELECT * FROM conversations')).one() == (20, 'Existing private chat')
            assert inspector.get_unique_constraints('survey_invitations')[0]['column_names'] == ['survey_id']
            migration.downgrade()
            assert not (set(inspect(connection).get_table_names()) & {
                'survey_residents', 'survey_units', 'maintenance_occurrences', 'survey_instances', 'survey_invitations', 'survey_email_opt_outs'})
            migration.upgrade()
    engine.dispose()
    config = Config()
    config.set_main_option('script_location', str(root / 'alembic'))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == [migration.revision]
    assert script.get_revision(migration.revision).down_revision == 'e1d7352fa043'
