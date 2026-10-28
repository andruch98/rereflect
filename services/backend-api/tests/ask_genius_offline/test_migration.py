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


def test_chat_controls_upgrade_preserves_existing_chats_and_has_one_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    root = Path(__file__).parents[2]
    path = root / 'alembic/versions/e1d7352fa043_add_ask_genius_chat_controls.py'
    spec = importlib.util.spec_from_file_location('genius_chat_controls_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE organizations (id INTEGER PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE conversations (id INTEGER PRIMARY KEY, title TEXT)'))
        connection.execute(text("INSERT INTO conversations VALUES (1, 'Existing private chat')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert connection.execute(text('SELECT id, title, is_pinned FROM conversations')).one() == (
                1, 'Existing private chat', 0)
            columns = {c['name']: c for c in inspect(connection).get_columns('conversations')}
            assert columns['is_pinned']['nullable'] is False
            assert 'ask_genius_shares' in inspect(connection).get_table_names()
            indexes = inspect(connection).get_indexes('ask_genius_shares')
            assert any(i['column_names'] == ['token_hash'] and i['unique'] for i in indexes)
            migration.downgrade()
            assert 'ask_genius_shares' not in inspect(connection).get_table_names()
            assert connection.execute(text('SELECT * FROM conversations')).one() == (1, 'Existing private chat')
    engine.dispose()
    config = Config()
    config.set_main_option('script_location', str(root / 'alembic'))
    assert ScriptDirectory.from_config(config).get_heads() == [migration.revision]
