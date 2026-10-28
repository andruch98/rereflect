"""Execute the real startup telemetry block without unrelated integration imports."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize('preview,dsn,enabled', [
    ('true', 'https://synthetic.invalid/1', False),
    ('TRUE', 'https://synthetic.invalid/1', False),
    ('false', 'https://synthetic.invalid/1', True),
    ('false', '', False),
])
def test_preview_does_not_export_shared_chat_urls(monkeypatch, preview, dsn, enabled):
    import os
    monkeypatch.setenv('BOOMSAY_REVIEW_PREVIEW', preview)
    monkeypatch.setenv('SENTRY_DSN', dsn)
    main = Path(__file__).resolve().parents[2] / 'src/api/main.py'
    nodes = ast.parse(main.read_text()).body
    block = [node for node in nodes if (
        isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in
                                             {'_sentry_dsn', '_sentry_initialized'} for target in node.targets)
    ) or (isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == '_sentry_initialized')]
    assert len(block) == 3
    init = Mock()
    namespace = {'os': os, 'sentry_sdk': SimpleNamespace(init=init)}
    exec(compile(ast.Module(body=block, type_ignores=[]), str(main), 'exec'), namespace)
    assert namespace['_sentry_initialized'] is enabled
    assert init.call_count == int(enabled)
    if enabled:
        assert init.call_args.kwargs['dsn'] == dsn
        assert init.call_args.kwargs['send_default_pii'] is False
