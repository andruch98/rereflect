"""Offline setup checks. Fixtures contain synthetic credentials, never live keys."""
import contextlib
import copy
import getpass
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

BUNDLE = Path(__file__).resolve().parents[1]
BASELINE = Path(os.environ['BOOMSAY_SETUP_BASELINE']).resolve()
spec = importlib.util.spec_from_file_location('setup_openai', BUNDLE / 'setup-openai.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
FAKE_KEY = 'sk-synthetic-setup-test-only-000000000000'


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='boomsay-setup-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'boomsay-dashboard-preview'
        self.root.mkdir()
        # Copy the actual delivered public skeleton, including its original hidden
        # Docker build exclusion. Never read/copy an existing runtime or login.
        for source in BASELINE.iterdir():
            if source.is_file():
                shutil.copy2(source, self.root / source.name)
        private = self.root / 'private'
        private.mkdir()
        shutil.copy2(BASELINE / 'private/saved-ai-records.json', private / 'saved-ai-records.json')
        (private / 'login.txt').write_bytes(b'SYNTHETIC TEST LOGIN ONLY\n')
        (private / 'local-login.json').write_text(json.dumps({'email': 'synthetic@example.invalid', 'password': 'synthetic-login'}))
        (private / 'blocked-ledger.sqlite').write_bytes(b'SYNTHETIC BLOCKED LEDGER FIXTURE')
        self.env = {
            'DATABASE_URL': 'postgresql://apartment_preview:synthetic-database-password@postgres:5432/rereflect_dashboard_preview',
            'JWT_SECRET': 'synthetic-jwt-preserve', 'LLM_ENCRYPTION_KEY': 'synthetic-encryption-preserve',
            'BOOMSAY_REVIEW_PREVIEW': 'true', 'BOOMSAY_PREVIEW_ORGANIZATION_ID': '1',
            'APARTMENT_EXPERIMENT_ORG_ID': '1', 'APARTMENT_EXPERIMENT_LEDGER': '/private/blocked-ledger.sqlite',
            'APARTMENT_EXPERIMENT_MANIFEST': '/private/not-authorized.json',
            'OPENAI_API_KEY': '', 'ANTHROPIC_API_KEY': '', 'GOOGLE_API_KEY': '',
            'GEMINI_API_KEY': '', 'RESEND_API_KEY': '', 'SENTRY_DSN': '',
            'CUSTOM_PRESERVE': 'unchanged-value',
        }
        (private / 'runtime.env').write_text('# Preserve this comment\n' + ''.join(f'{k}={v}\n' for k, v in self.env.items()))
        compose = json.loads((BUNDLE / 'expected-compose.json').read_text())
        compose['services']['postgres']['environment']['POSTGRES_PASSWORD'] = 'synthetic-database-password'
        (self.root / 'compose.json').write_text(json.dumps(compose, indent=2) + '\n')
        (self.root / 'app').mkdir()
        (self.root / 'app/old-source-marker.txt').write_text('original app')

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file()}

    def install(self):
        setup.apply_setup(self.root, setup.validate(self.root), FAKE_KEY)

    def test_upgrade_preserves_private_data_and_isolates_network(self):
        old_private = {p.name: p.read_bytes() for p in (self.root / 'private').iterdir()}
        self.install()
        env = setup.read_env((self.root / 'private/runtime.env').read_bytes())
        for name, value in self.env.items():
            self.assertEqual(env[name], value)
        self.assertEqual(env['ASK_GENIUS_MODEL'], 'gpt-4.1-mini')
        self.assertEqual(env['ASK_GENIUS_PROVIDER'], 'openai')
        self.assertEqual(env['ASK_GENIUS_API_KEY'], FAKE_KEY)
        self.assertEqual(env['ASK_GENIUS_ENABLED'], 'true')
        for name, value in old_private.items():
            if name != 'runtime.env':
                self.assertEqual((self.root / 'private' / name).read_bytes(), value)
        compose = json.loads((self.root / 'compose.json').read_text())
        self.assertEqual(set(compose['services']), {'api', 'postgres', 'redis', 'web', 'gateway'})
        self.assertEqual(compose['services']['api']['networks'], ['private', 'ask_genius_outbound'])
        for name in ('postgres', 'redis', 'web'):
            self.assertEqual(compose['services'][name]['networks'], ['private'])
        self.assertEqual(compose['services']['gateway']['networks'], ['private', 'entry'])
        self.assertEqual(compose['networks']['private'], {'internal': True})
        self.assertNotIn('ports', compose['services']['api'])
        self.assertEqual(stat.S_IMODE((self.root / 'private/runtime.env').stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.root / 'private').stat().st_mode), 0o700)
        self.assertFalse((self.root / 'backup-before-openai-setup/private').exists())
        self.assertTrue((self.root / 'app/services/backend-api/src/services/ask_genius.py').is_file())
        self.assertEqual((self.root / '.dockerignore').read_bytes(), setup.DOCKERIGNORE)

    def test_repeat_is_idempotent_and_reuses_only_dedicated_key(self):
        self.install()
        before = self.snapshot()
        with patch.object(sys.stdin, 'isatty', return_value=True), patch.object(getpass, 'getpass', return_value=''):
            key = setup.ask_key(setup.validate(self.root)['existing_key'])
        setup.apply_setup(self.root, setup.validate(self.root), key)
        self.assertEqual(self.snapshot(), before)

    def test_previously_installed_source_drift_rejected(self):
        self.install()
        source = self.root / 'app/services/backend-api/src/services/ask_genius.py'
        source.write_text('modified source')
        with self.assertRaises(setup.SetupError):
            setup.validate(self.root)

    def test_previously_installed_extra_executable_source_rejected(self):
        self.install()
        source = self.root / 'app/services/backend-api/sitecustomize.py'
        source.write_text('raise RuntimeError("unexpected extra source")')
        with self.assertRaises(setup.SetupError):
            setup.validate(self.root)

    def test_checksum_tampering_rejected(self):
        (self.root / 'Dockerfile.api').write_text('FROM untrusted')
        with self.assertRaises(setup.SetupError):
            setup.validate(self.root)

    def test_unknown_compose_and_worker_rejected(self):
        for mutation in ('worker', 'network', 'port', 'override'):
            with self.subTest(mutation=mutation):
                path = self.root / 'compose.json'; original = path.read_bytes()
                compose = json.loads(original)
                if mutation == 'worker': compose['services']['worker'] = {'image': 'anything'}
                if mutation == 'network': compose['networks']['private']['internal'] = False
                if mutation == 'port': compose['services']['api']['ports'] = ['8000:8000']
                if mutation == 'override': compose['services']['api']['environment'] = {'ASK_GENIUS_API_KEY': 'wrong'}
                path.write_text(json.dumps(compose))
                with self.assertRaises(setup.SetupError): setup.validate(self.root)
                path.write_bytes(original)

    def test_symlink_private_or_env_rejected(self):
        env = self.root / 'private/runtime.env'
        replacement = self.root / 'synthetic-env-copy'; replacement.write_bytes(env.read_bytes())
        env.unlink();env.symlink_to(replacement)
        with self.assertRaises(setup.SetupError): setup.validate(self.root)

    def test_other_project_key_and_database_rejected(self):
        path = self.root / 'private/runtime.env'; original = path.read_bytes()
        for changed in (original.replace(b'OPENAI_API_KEY=\n', b'OPENAI_API_KEY=unrelated\n'),
                        original.replace(b'@postgres:', b'@remote-host:'),
                        original.replace(b'APARTMENT_EXPERIMENT_ORG_ID=1', b'APARTMENT_EXPERIMENT_ORG_ID=2')):
            path.write_bytes(changed)
            with self.assertRaises(setup.SetupError): setup.validate(self.root)
        path.write_bytes(original)

    def test_invalid_key_preserves_everything(self):
        state = setup.validate(self.root); before = self.snapshot()
        for key in ('', 'short', FAKE_KEY + '\nOPENAI_API_KEY=bad', FAKE_KEY + '$VAR', FAKE_KEY + ' '):
            with self.assertRaises(setup.SetupError): setup.apply_setup(self.root, state, key)
        self.assertEqual(self.snapshot(), before)

    def test_canceled_hidden_input_preserves_everything(self):
        before = self.snapshot()
        for error in (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
            with patch.object(sys.stdin, 'isatty', return_value=True), patch.object(getpass, 'getpass', side_effect=error):
                with self.assertRaises(setup.SetupError): setup.ask_key('')
        self.assertEqual(self.snapshot(), before)

    def test_noninteractive_never_prompts(self):
        with patch.object(sys.stdin, 'isatty', return_value=False), patch.object(getpass, 'getpass') as prompt:
            with self.assertRaises(setup.SetupError): setup.ask_key('')
            prompt.assert_not_called()

    def test_write_failure_rolls_back_app_and_config(self):
        before = self.snapshot(); original = setup.atomic_write
        def fail_once(path, data, mode=0o600):
            if path.name == 'runtime.env' and b'ASK_GENIUS_ENABLED=true' in data:
                raise OSError('synthetic disk failure')
            return original(path, data, mode)
        with patch.object(setup, 'atomic_write', side_effect=fail_once):
            with self.assertRaises(OSError): self.install()
        self.assertEqual(self.snapshot(), before)

    def test_success_output_does_not_expose_key_or_other_credentials(self):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['setup-openai.py', str(self.root)]), patch.object(setup, 'ask_key', return_value=FAKE_KEY), contextlib.redirect_stdout(output):
            self.assertEqual(setup.main(), 0)
        self.assertNotIn(FAKE_KEY, output.getvalue())
        self.assertNotIn('synthetic-database-password', output.getvalue())

    def test_startup_pins_project_even_with_polluted_environment(self):
        self.install()
        script = (self.root / 'start-local.sh').read_text()
        self.assertNotIn('docker compose -f compose.json', script)
        self.assertEqual(script.count('docker compose -p boomsay-dashboard-preview-local -f compose.json'), 5)
        subprocess.run(['bash', '-n', str(self.root / 'start-local.sh')], check=True)
        fake_bin = Path(self.temporary.name) / 'bin'; fake_bin.mkdir()
        docker = fake_bin / 'docker'
        docker.write_text('''#!/bin/bash
case "$1 $2" in
  "context show") echo default ;;
  "context inspect") echo unix:///synthetic/docker.sock ;;
  "compose version") exit 0 ;;
  "compose "*) printf '%s\\n' "$*" >> "$SYNTHETIC_DOCKER_LOG" ;;
esac
''')
        python = fake_bin / 'python3';python.write_text('#!/bin/bash\nexit 0\n')
        docker.chmod(0o700);python.chmod(0o700)
        log = Path(self.temporary.name) / 'docker-calls.txt'
        environment = {**os.environ, 'PATH': str(fake_bin) + ':' + os.environ['PATH'],
                       'COMPOSE_PROJECT_NAME': 'wrong-project', 'SYNTHETIC_DOCKER_LOG': str(log)}
        environment.pop('DOCKER_HOST', None)
        for name in ('start-local.sh', 'stop-local.sh'):
            subprocess.run(['bash', str(self.root / name)], env=environment, check=True, capture_output=True)
        calls = log.read_text().splitlines()
        self.assertEqual(len(calls), 6)
        self.assertTrue(all(call.startswith('compose -p boomsay-dashboard-preview-local -f compose.json ') for call in calls))

    def test_unknown_original_dockerignore_is_not_overwritten(self):
        path = self.root / '.dockerignore'; path.write_text('!private/**\n')
        before = self.snapshot()
        with self.assertRaises(setup.SetupError): setup.validate(self.root)
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
