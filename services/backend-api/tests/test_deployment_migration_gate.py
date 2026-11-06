"""The external deployment migration gate is opt-in; ordinary startup is unchanged."""
from unittest.mock import Mock

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize('flag,expected_calls', [(None, 1), ('false', 1), ('1', 1), ('true', 0), ('TRUE', 0)])
async def test_deployment_migration_gate(monkeypatch, flag, expected_calls):
    from src.api import main

    # Skip unrelated seed jobs after the migration decision. Nothing contacts
    # a database, queue, model or provider during this lifecycle unit check.
    monkeypatch.setenv('APARTMENT_EXPERIMENT_ORG_ID', '1')
    if flag is None:
        monkeypatch.delenv('BOOMSAY_SKIP_STARTUP_MIGRATIONS', raising=False)
    else:
        monkeypatch.setenv('BOOMSAY_SKIP_STARTUP_MIGRATIONS', flag)
    migrate = Mock()
    monkeypatch.setattr(main, 'run_migrations', migrate)

    async with main.lifespan(main.app):
        pass

    assert migrate.call_count == expected_calls
