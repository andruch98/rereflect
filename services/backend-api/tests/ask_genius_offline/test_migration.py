"""The additive migration preserves an existing user and defaults to no period."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_preference_column_upgrade_preserves_existing_user_and_downgrade():
    path = Path(__file__).parents[2] / 'alembic/versions/d0c6241e9f32_add_ask_genius_default_period.py'
    spec = importlib.util.spec_from_file_location('genius_preference_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL)'))
        connection.execute(text("INSERT INTO users VALUES (1, 'existing@example.invalid')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            columns = {column['name']: column for column in inspect(connection).get_columns('users')}
            assert columns['ask_genius_default_period']['nullable']
            assert connection.execute(text('SELECT id, email, ask_genius_default_period FROM users')).one() == (
                1, 'existing@example.invalid', None)
            migration.downgrade()
            assert set(column['name'] for column in inspect(connection).get_columns('users')) == {'id', 'email'}
            assert connection.execute(text('SELECT id, email FROM users')).one() == (1, 'existing@example.invalid')
    engine.dispose()
