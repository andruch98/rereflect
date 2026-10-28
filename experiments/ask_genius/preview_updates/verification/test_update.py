"""Offline updater checks with synthetic credentials; no Docker/provider calls."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch


BUNDLE = Path(__file__).resolve().parents[1]
BASELINE = Path(os.environ['BOOMSAY_LAYOUT_BASELINE']).resolve()
spec = importlib.util.spec_from_file_location('layout_update', BUNDLE / 'update-preview.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)
BASES = [
    '7519b93674d40f87e9915ae458ac503cd69e1d2d',
    '051d06fa9d5e81108c3ea01366e2b24f2ec86a48',
    'e19eb96cf0a19802d9bcc569c643845e36417032',
    '66e7ec4c61a147eced6eed05be45207725253ba6',
    '4c117094a132b3f395140026336b25ee220ca862',
    '5b39b14ff540b2d2de57f90fe8390b7040d2d16f',
    '724ca86b0de00c59ade1c8c54fac17ec9bacbc71',
    '5bba1ce0c502c074d481a4b2228091ec5873c72d',
]
TARGET = 'f' * 40  # Synthetic target; never distributed as a real application commit.


class UpdateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='genius-layout-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'preview'
        self.bundle = Path(temporary.name) / 'update'
        self.root.mkdir()
        self.bundle.mkdir()
        # Copy only the known public skeleton, never a live runtime or login file.
        for name in updater.MANIFEST_REQUIRED - {'private/saved-ai-records.json'} | {
            'SOURCE.txt', 'checksums.json', 'configure.py', 'start-local.sh', 'stop-local.sh', '.dockerignore',
        }:
            shutil.copy2(BASELINE / name, self.root / name)
        private = self.root / 'private'
        private.mkdir()
        (private / 'saved-ai-records.json').write_text('{"records": "synthetic review fixture"}\n')
        (private / 'runtime.env').write_text('# Synthetic only\nASK_GENIUS_API_KEY=sk-not-real-preserve-me\nASK_GENIUS_MODEL=gpt-4.1-mini\nCUSTOM=unchanged\n')
        (private / 'login.txt').write_text('Synthetic login; preserve exactly\n')
        (private / 'local-login.json').write_text('{"password":"synthetic-only"}\n')
        (private / 'blocked-ledger.sqlite').write_bytes(b'synthetic stopped ledger')
        (private / 'database-sentinel').write_bytes(b'synthetic saved database marker')
        (self.root / 'compose.json').write_text('{"name":"synthetic-existing-network-config"}\n')
        (self.root / 'app').mkdir()
        (self.root / 'app/old-source.txt').write_text('original source retained in backup')
        checksums = json.loads((self.root / 'checksums.json').read_text())
        checksums['private/saved-ai-records.json'] = updater.digest((private / 'saved-ai-records.json').read_bytes())
        (self.root / 'checksums.json').write_text(json.dumps(checksums))
        self.make_archive()

    def make_archive(self, extra=None, omit=None):
        with tarfile.open(self.bundle / 'rereflect-app-source.tar.gz', 'w:gz') as archive:
            for name in updater.APP_MARKERS:
                if name == omit:
                    continue
                data = b'synthetic new application source\n'
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            if extra:
                archive.addfile(extra)
        data = (self.bundle / 'rereflect-app-source.tar.gz').read_bytes()
        (self.bundle / 'update.json').write_text(json.dumps({'commit': TARGET, 'bases': BASES, 'sha256': updater.digest(data)}))

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file() and not path.is_symlink()}

    def install(self):
        return updater.update(self.root, self.bundle)

    def test_update_preserves_private_configuration_and_backup(self):
        old = self.snapshot()
        self.assertTrue(self.install())
        for name, data in old.items():
            if name.startswith('private/') or name in ('compose.json', 'start-local.sh', 'stop-local.sh', 'configure.py', '.dockerignore'):
                self.assertEqual((self.root / name).read_bytes(), data)
        self.assertEqual((self.root / updater.BACKUP / 'app/old-source.txt').read_bytes(), old['app/old-source.txt'])
        self.assertFalse((self.root / updater.BACKUP / 'private').exists())
        self.assertIn('Commit: ' + TARGET, (self.root / 'SOURCE.txt').read_text())
        for marker in updater.APP_MARKERS:
            self.assertTrue((self.root / 'app' / marker).is_file())

    def test_all_supported_source_versions_update(self):
        original = (self.root / 'SOURCE.txt').read_text()
        for base in BASES:
            with self.subTest(base=base):
                (self.root / 'SOURCE.txt').write_text(original.replace(BASES[0], base))
                self.assertTrue(self.install())
                shutil.rmtree(self.root / 'app')
                (self.root / updater.BACKUP / 'app').rename(self.root / 'app')
                for name in updater.MUTATED_FILES:
                    shutil.copy2(self.root / updater.BACKUP / name, self.root / name)
                shutil.rmtree(self.root / updater.BACKUP)

    def test_repeat_is_an_exact_noop(self):
        self.install()
        before = self.snapshot()
        self.assertFalse(self.install())
        self.assertEqual(self.snapshot(), before)

    def test_local_layout_commit_requires_verified_archive(self):
        (self.root / 'SOURCE.txt').write_text((self.root / 'SOURCE.txt').read_text().replace(BASES[0], updater.LOCAL_LAYOUT_COMMIT))
        meta = json.loads((self.bundle / 'update.json').read_text())
        meta['bases'].append(updater.LOCAL_LAYOUT_COMMIT)
        (self.bundle / 'update.json').write_text(json.dumps(meta))
        with self.assertRaisesRegex(updater.UpdateError, 'does not match its verified release'):
            self.install()
        with patch.object(updater, 'LOCAL_LAYOUT_ARCHIVE_HASH', updater.digest((self.root / 'rereflect-app-source.tar.gz').read_bytes())):
            self.assertTrue(self.install())

    def test_source_substring_or_duplicate_commit_is_not_accepted(self):
        original = (self.root / 'SOURCE.txt').read_text()
        for source in (original.replace('Commit: ', 'Comment: '), original + '\nCommit: ' + BASES[0] + '\n'):
            (self.root / 'SOURCE.txt').write_text(source)
            with self.assertRaises(updater.UpdateError):
                self.install()

    def test_private_credentials_cannot_be_added_to_manifest(self):
        path = self.root / 'checksums.json'
        checksums = json.loads(path.read_text())
        checksums['private/runtime.env'] = '0' * 64
        path.write_text(json.dumps(checksums))
        original_read = Path.read_bytes
        def read_without_credentials(path):
            if path.name in {'runtime.env', 'login.txt', 'local-login.json'}:
                raise AssertionError('Updater attempted to read credentials')
            return original_read(path)
        with patch.object(Path, 'read_bytes', read_without_credentials):
            with self.assertRaises(updater.UpdateError):
                self.install()

    def test_bad_archive_or_preview_checksum_is_rejected(self):
        archive = self.bundle / 'rereflect-app-source.tar.gz'
        original = archive.read_bytes()
        archive.write_bytes(original + b'changed')
        with self.assertRaises(updater.UpdateError): self.install()
        archive.write_bytes(original)
        (self.root / 'Dockerfile.api').write_text('changed')
        before = self.snapshot()
        with self.assertRaises(updater.UpdateError): self.install()
        self.assertEqual(self.snapshot(), before)

    def test_unsafe_tar_entries_are_rejected_before_mutation(self):
        for name, kind in (('../escape', tarfile.REGTYPE), ('/escape', tarfile.REGTYPE), ('link', tarfile.SYMTYPE)):
            member = tarfile.TarInfo(name)
            member.type = kind
            member.linkname = '/tmp/escape'
            self.make_archive(member)
            before = self.snapshot()
            with self.assertRaises(updater.UpdateError): self.install()
            self.assertEqual(self.snapshot(), before)

    def test_symlink_mutation_paths_are_rejected(self):
        for name in (*updater.MUTATED_FILES, 'app'):
            with self.subTest(name=name):
                path = self.root / name
                moved = self.root / (name + '-original')
                path.rename(moved)
                path.symlink_to(moved)
                with self.assertRaises(updater.UpdateError): self.install()
                path.unlink()
                moved.rename(path)

    def test_existing_backup_is_preserved(self):
        backup = self.root / updater.BACKUP
        backup.mkdir()
        (backup / 'keep').write_text('preserve')
        before = self.snapshot()
        with self.assertRaises(updater.UpdateError): self.install()
        self.assertEqual(self.snapshot(), before)

    def test_existing_layout_backup_is_preserved_and_does_not_block_update(self):
        backup = self.root / 'backup-before-genius-layout'
        backup.mkdir()
        (backup / 'keep').write_text('previous layout source backup')
        self.assertTrue(self.install())
        self.assertEqual((backup / 'keep').read_text(), 'previous layout source backup')
        self.assertTrue((self.root / updater.BACKUP / 'app/old-source.txt').is_file())

    def test_installed_improvements_update_preserves_all_previous_backups(self):
        source_path = self.root / 'SOURCE.txt'
        original_source = source_path.read_text()
        source_path.write_text(original_source.replace(BASES[0], '5bba1ce0c502c074d481a4b2228091ec5873c72d'))
        for name in ('backup-before-genius-layout', 'backup-before-genius-improvements'):
            backup = self.root / name
            backup.mkdir()
            (backup / 'keep').write_text('earlier source backup: ' + name)
        before = self.snapshot()
        self.assertTrue(self.install())
        for name, data in before.items():
            if name.startswith(('backup-before-genius-layout/', 'backup-before-genius-improvements/', 'private/')):
                self.assertEqual((self.root / name).read_bytes(), data)
        self.assertEqual((self.root / updater.BACKUP / 'SOURCE.txt').read_bytes(), before['SOURCE.txt'])
        installed = self.snapshot()
        self.assertFalse(self.install())
        self.assertEqual(self.snapshot(), installed)

    def test_unrecognized_startup_cannot_skip_schema_migration(self):
        startup = self.root / 'start-local.sh'
        startup.write_text(startup.read_text().replace('python -m alembic upgrade head', 'true'))
        before = self.snapshot()
        with self.assertRaisesRegex(updater.UpdateError, 'startup script'):
            self.install()
        self.assertEqual(self.snapshot(), before)

    def test_configured_openai_startup_preserved(self):
        startup = self.root / 'start-local.sh'
        changed = startup.read_bytes().replace(b'No AI keys or workers are needed.', b'No analysis workers are started.')
        changed = changed.replace(b'docker compose -f compose.json', b'docker compose -p boomsay-dashboard-preview-local -f compose.json')
        self.assertIn(updater.digest(changed), updater.STARTUP_HASHES)
        startup.write_bytes(changed)
        checksums = json.loads((self.root / 'checksums.json').read_text())
        checksums['start-local.sh'] = updater.digest(changed)
        (self.root / 'checksums.json').write_text(json.dumps(checksums))
        self.assertTrue(self.install())
        self.assertEqual(startup.read_bytes(), changed)
        self.assertIn(b'python -m alembic upgrade head', startup.read_bytes())

    def test_incomplete_source_missing_preference_migration_is_rejected(self):
        migration = 'services/backend-api/alembic/versions/d0c6241e9f32_add_ask_genius_default_period.py'
        self.make_archive(omit=migration)
        before = self.snapshot()
        with self.assertRaisesRegex(updater.UpdateError, 'missing application files'):
            self.install()
        self.assertEqual(self.snapshot(), before)

    def test_incomplete_chat_update_is_rejected_before_mutation(self):
        for marker in (
            'services/backend-api/alembic/versions/e1d7352fa043_add_ask_genius_chat_controls.py',
            'services/backend-api/src/models/ask_genius_share.py',
            'services/backend-api/src/services/ask_genius_sharing.py',
        ):
            with self.subTest(marker=marker):
                self.make_archive(omit=marker)
                before = self.snapshot()
                with self.assertRaisesRegex(updater.UpdateError, 'missing application files'):
                    self.install()
                self.assertEqual(self.snapshot(), before)

    def test_write_failure_restores_app_metadata_and_private_files(self):
        before = self.snapshot()
        original_write = updater.atomic_write
        failed = False
        def fail_once(path, data, mode):
            nonlocal failed
            if path.name == 'checksums.json' and not failed:
                failed = True
                raise OSError('synthetic write failure')
            return original_write(path, data, mode)
        with patch.object(updater, 'atomic_write', fail_once):
            with self.assertRaises(OSError): self.install()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / updater.BACKUP).exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
