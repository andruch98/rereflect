"""Exercise packaging against a disposable Git repository, never real data."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile


HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('survey_builder', HERE / 'build-update.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
spec = importlib.util.spec_from_file_location('survey_updater_for_build', HERE / 'update-preview.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class BuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='survey-package-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'repo'
        self.root.mkdir()
        self.output = self.root.parent / 'update.zip'
        self.repo_patch = patch.object(builder, 'REPOSITORY', self.root)
        self.repo_patch.start()
        self.addCleanup(self.repo_patch.stop)
        for name in builder.SOURCE_PATHS:
            path = self.root / name
            if name.startswith(('packages/', 'services/')):
                path = path / 'fixture.txt'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('committed public source\n')
        for name in updater.APP_MARKERS:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('committed public source\n')
        for name in builder.HANDOFF_FILES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('committed public handoff\n')
        scripts = self.root / 'experiments/maintenance_surveys/preview_updates'
        scripts.mkdir(parents=True, exist_ok=True)
        for name in ('build-update.py', 'update-preview.py', 'README.txt'):
            (scripts / name).write_bytes((HERE / name).read_bytes())
        self.git('init', '-q')
        self.git('add', '.')
        self.commit = self.commit_fixture()

    def git(self, *arguments):
        return subprocess.check_output(['git', *arguments], cwd=self.root, text=True).strip()

    def commit_fixture(self):
        self.git('-c', 'user.name=Offline fixture', '-c', 'user.email=offline@example.invalid',
                 'commit', '-qm', 'Synthetic packaging fixture')
        return self.git('rev-parse', 'HEAD')

    def test_exact_commit_excludes_uncommitted_source_and_private_files(self):
        marker = updater.APP_MARKERS[0]
        (self.root / marker).write_text('UNCOMMITTED_SOURCE_MUST_NOT_SHIP')
        (self.root / 'private').mkdir()
        (self.root / 'private/runtime.env').write_text('SYNTHETIC_SECRET_MUST_NOT_SHIP')
        (self.root / 'services/backend-api/.env').write_text('SYNTHETIC_SECRET_MUST_NOT_SHIP')
        with patch('builtins.print'):
            builder.build(self.commit, self.output)
        with zipfile.ZipFile(self.output) as bundle:
            names = bundle.namelist()
            self.assertEqual(len(names), 4 + len(builder.HANDOFF_FILES))
            prefix = builder.BUNDLE_NAME + '/'
            for source, destination in builder.HANDOFF_FILES.items():
                expected = subprocess.check_output(['git', 'show', self.commit + ':' + source], cwd=self.root)
                self.assertEqual(bundle.read(prefix + destination), expected)
            self.assertIn(prefix + 'handoff/README.md', names)
            self.assertIn(prefix + 'handoff/preview_updates/README.txt', names)
            self.assertIn(prefix + 'handoff/preview_updates/PACKAGING.md', names)
            archive_bytes = bundle.read(prefix + 'rereflect-app-source.tar.gz')
            meta = json.loads(bundle.read(prefix + 'update.json'))
            self.assertEqual(meta['commit'], self.commit)
            self.assertEqual(meta['sha256'], updater.digest(archive_bytes))
            self.assertIn('5b39b14ff540b2d2de57f90fe8390b7040d2d16f', meta['bases'])
            self.assertIn('bf6236c84291d633435a1b73719d7b645942a715', meta['bases'])
            self.assertIn('724ca86b0de00c59ade1c8c54fac17ec9bacbc71', meta['bases'])
            self.assertIn('5bba1ce0c502c074d481a4b2228091ec5873c72d', meta['bases'])
            self.assertIn('b28bf174078fcb94438fb5f806321cc49a99c7f4', meta['bases'])
            self.assertIn('59dfd9122b20d0098eceedf8e1d1296e86b6f0a3', meta['bases'])
            with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode='r:gz') as archive:
                self.assertEqual(archive.extractfile(marker).read(), b'committed public source\n')
                self.assertFalse(any('.env' in name or name.startswith('private/') for name in archive.getnames()))

    def test_handoff_and_fixtures_use_committed_bytes_and_optional_manifest_requires_commit(self):
        for source in builder.HANDOFF_FILES:
            (self.root / source).write_text('UNCOMMITTED_HANDOFF_MUST_NOT_SHIP')
        optional = next(iter(builder.OPTIONAL_HANDOFF_FILES))
        (self.root / optional).write_text('UNCOMMITTED_MANIFEST_MUST_NOT_SHIP')
        with patch('builtins.print'):
            builder.build(self.commit, self.output)
        with zipfile.ZipFile(self.output) as bundle:
            prefix = builder.BUNDLE_NAME + '/'
            for source, destination in builder.HANDOFF_FILES.items():
                expected = subprocess.check_output(['git', 'show', self.commit + ':' + source], cwd=self.root)
                self.assertEqual(bundle.read(prefix + destination), expected)
            self.assertTrue(all(prefix + destination not in bundle.namelist()
                                for destination in builder.OPTIONAL_HANDOFF_FILES.values()))
        self.output.unlink()
        (self.root / optional).write_text('committed changed paths\n')
        self.git('add', optional)
        commit = self.commit_fixture()
        (self.root / optional).write_text('UNCOMMITTED_MANIFEST_MUST_NOT_SHIP')
        with patch('builtins.print'):
            builder.build(commit, self.output)
        with zipfile.ZipFile(self.output) as bundle:
            self.assertEqual(bundle.read(prefix + builder.OPTIONAL_HANDOFF_FILES[optional]),
                             b'committed changed paths\n')

    def test_missing_committed_handoff_document_or_fixture_is_rejected(self):
        for source in builder.HANDOFF_FILES:
            if source.endswith('preview_updates/README.txt'):
                continue  # The stricter updater-script identity check covers this file first.
            with self.subTest(source=source):
                self.git('rm', '-q', source)
                commit = self.commit_fixture()
                with self.assertRaisesRegex(ValueError, 'lacks required handoff file'):
                    builder.build(commit, self.output)
                self.assertFalse(self.output.exists())
                self.git('checkout', self.commit, '--', source)
                self.commit_fixture()

    def test_existing_output_and_invalid_commit_are_rejected(self):
        self.output.write_bytes(b'preserve previous artifact')
        with self.assertRaises(ValueError):
            builder.build(self.commit, self.output)
        self.assertEqual(self.output.read_bytes(), b'preserve previous artifact')
        with self.assertRaises(ValueError):
            builder.build('HEAD', self.root.parent / 'different.zip')

    def test_uncommitted_updater_difference_is_rejected(self):
        readme = self.root / 'experiments/maintenance_surveys/preview_updates/README.txt'
        readme.write_text('different committed updater instructions')
        self.git('add', str(readme.relative_to(self.root)))
        changed_commit = self.commit_fixture()
        with self.assertRaisesRegex(ValueError, 'must match'):
            builder.build(changed_commit, self.output)
        self.assertFalse(self.output.exists())

    def test_missing_migration_in_committed_archive_is_rejected(self):
        migration = 'services/backend-api/alembic/versions/d0c6241e9f32_add_ask_genius_default_period.py'
        self.git('rm', '-q', migration)
        changed_commit = self.commit_fixture()
        with self.assertRaisesRegex(ValueError, 'lacks required'):
            builder.build(changed_commit, self.output)
        self.assertFalse(self.output.exists())

    def test_missing_chat_migration_or_share_runtime_is_rejected(self):
        for marker in (
            'services/backend-api/alembic/versions/e1d7352fa043_add_ask_genius_chat_controls.py',
            'services/backend-api/src/models/ask_genius_share.py',
            'services/backend-api/src/services/ask_genius_sharing.py',
            'services/backend-api/alembic/versions/f2e8463ab154_add_maintenance_surveys.py',
            'services/backend-api/src/services/survey_delivery.py',
            'services/backend-api/src/survey_demo.py',
        ):
            with self.subTest(marker=marker):
                self.git('rm', '-q', marker)
                changed_commit = self.commit_fixture()
                with self.assertRaisesRegex(ValueError, 'lacks required'):
                    builder.build(changed_commit, self.output)
                self.assertFalse(self.output.exists())
                self.git('checkout', self.commit, '--', marker)
                self.commit_fixture()


if __name__ == '__main__':
    unittest.main(verbosity=2)
