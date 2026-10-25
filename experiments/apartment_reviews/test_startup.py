"""Verify isolated full-API startup cannot run unrelated seed/embedding jobs."""
import os
from pathlib import Path
import subprocess
import sys


def test_full_api_experiment_startup_skips_seed_jobs():
    root=Path(__file__).resolve().parents[2]
    env=dict(os.environ, PYTHONPATH=str(root/'services/backend-api'),
             JWT_SECRET='fictional-test-startup-secret', APARTMENT_EXPERIMENT_ORG_ID='42',
             OPENAI_API_KEY='', SENTRY_DSN='')
    code='''
import asyncio
from unittest.mock import Mock
from src.api import main
main.run_migrations=Mock()
main.seed_admin_user=Mock(side_effect=AssertionError('unexpected admin seed'))
main.seed_system_templates=Mock(side_effect=AssertionError('unexpected template seed'))
main.seed_copilot_system_templates=Mock(side_effect=AssertionError('unexpected embeddings'))
async def check():
    async with main.lifespan(main.app):
        main.run_migrations.assert_called_once()
        main.seed_admin_user.assert_not_called()
        main.seed_system_templates.assert_not_called()
        main.seed_copilot_system_templates.assert_not_called()
asyncio.run(check())
'''
    subprocess.run([sys.executable,'-c',code],env=env,check=True,capture_output=True,text=True,timeout=30)
