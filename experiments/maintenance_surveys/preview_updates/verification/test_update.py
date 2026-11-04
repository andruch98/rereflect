"""Source-only updater checks using a synthetic preview; no external calls."""
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('survey_updater', HERE / 'update-preview.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)
BASE = '59dfd9122b20d0098eceedf8e1d1296e86b6f0a3'
TARGET = 'f' * 40
START = b'#!/bin/sh\n# Synthetic startup; never executed\n'


class UpdateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='survey-update-test-')
        self.addCleanup(temp.cleanup)
        self.root, self.bundle = Path(temp.name) / 'preview', Path(temp.name) / 'bundle'
        self.root.mkdir()
        self.bundle.mkdir()
        for name in updater.MANIFEST_REQUIRED | {'SOURCE.txt', 'configure.py', 'start-local.sh'}:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic public skeleton\n')
        (self.root / 'start-local.sh').write_bytes(START)
        (self.root / 'configure.py').write_text('# boomsay-dashboard-preview-local\n')
        (self.root / 'SOURCE.txt').write_text(f'Application: andruch98/rereflect\nCommit: {BASE}\n')
        (self.root / 'checksums.json').write_text(json.dumps({
            name: updater.digest((self.root / name).read_bytes())
            for name in updater.MANIFEST_REQUIRED | {'start-local.sh'}
        }))
        for name in ('runtime.env', 'login.txt', 'local-login.json', 'database-sentinel'):
            (self.root / 'private' / name).write_text('fictional private sentinel: ' + name)
        (self.root / 'compose.json').write_text('{"existing":"network and volume unchanged"}')
        (self.root / 'app').mkdir()
        (self.root / 'app/old-source').write_text('old source preserved')
        # Validate the protocol independently of unavailable shipped skeleton bytes.
        self.start_patch = patch.object(updater, 'STARTUP_HASHES', {updater.digest(START)})
        self.start_patch.start()
        self.addCleanup(self.start_patch.stop)
        self.archive()

    def archive(self, omit=None, unsafe=None):
        with tarfile.open(self.bundle / 'rereflect-app-source.tar.gz', 'w:gz') as archive:
            for name in updater.APP_MARKERS:
                if name == omit:
                    continue
                data = b'synthetic committed source\n'
                entry = tarfile.TarInfo(name)
                entry.size = len(data)
                archive.addfile(entry, io.BytesIO(data))
            if unsafe:
                archive.addfile(unsafe)
        data = (self.bundle / 'rereflect-app-source.tar.gz').read_bytes()
        (self.bundle / 'update.json').write_text(json.dumps({
            'commit': TARGET, 'bases': [BASE], 'sha256': updater.digest(data),
        }))

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file() and not path.is_symlink()}

    def test_source_update_preserves_private_state_configuration_and_prior_backups(self):
        (self.root / 'backup-before-survey-email-test-update').mkdir()
        (self.root / 'backup-before-survey-email-test-update/keep').write_text('previous email update backup')
        (self.root / 'backup-before-maintenance-survey-update').mkdir()
        (self.root / 'backup-before-maintenance-survey-update/keep').write_text('first survey update backup')
        (self.root / 'backup-before-genius-context-update').mkdir()
        (self.root / 'backup-before-genius-context-update/keep').write_text('previous backup')
        before = self.snapshot()
        self.assertTrue(updater.update(self.root, self.bundle))
        for name, data in before.items():
            if name.startswith(('private/', 'backup-before-genius-', 'backup-before-maintenance-survey-update/', 'backup-before-survey-email-test-update/')) or name in (
                'configure.py', 'compose.json', 'start-local.sh',
            ):
                self.assertEqual((self.root / name).read_bytes(), data)
        self.assertEqual((self.root / updater.BACKUP / 'app/old-source').read_bytes(), before['app/old-source'])
        self.assertFalse((self.root / updater.BACKUP / 'private').exists())
        self.assertIn(TARGET, (self.root / 'SOURCE.txt').read_text())
        self.assertTrue(all((self.root / 'app' / name).is_file() for name in updater.APP_MARKERS))

    def test_repeat_update_is_exact_noop(self):
        updater.update(self.root, self.bundle)
        before = self.snapshot()
        self.assertFalse(updater.update(self.root, self.bundle))
        self.assertEqual(self.snapshot(), before)

    def test_published_email_release_with_blank_lines_preserves_private_state(self):
        installed = '4cea583fa5f0b98d50c7ad97bf54c84aca31dccf'
        (self.root / 'SOURCE.txt').write_text(
            f'Application: andruch98/rereflect\n\nBranch: feat/survey-email-preview\n\nCommit: {installed}\n')
        meta_path = self.bundle / 'update.json'
        meta = json.loads(meta_path.read_text())
        meta['bases'].append(installed)
        meta_path.write_text(json.dumps(meta))
        before = self.snapshot()
        self.assertTrue(updater.update(self.root, self.bundle))
        for name, data in before.items():
            if name.startswith('private/') or name in ('compose.json', 'configure.py', 'start-local.sh'):
                self.assertEqual((self.root / name).read_bytes(), data)

    def test_unknown_startup_or_source_is_rejected_before_mutation(self):
        for kind in ('startup', 'commit'):
            with self.subTest(kind=kind):
                name = 'start-local.sh' if kind == 'startup' else 'SOURCE.txt'
                original = (self.root / name).read_bytes()
                (self.root / name).write_bytes(b'unknown installation')
                before = self.snapshot()
                with self.assertRaises(updater.UpdateError):
                    updater.update(self.root, self.bundle)
                self.assertEqual(self.snapshot(), before)
                (self.root / name).write_bytes(original)

    def test_bad_archive_and_preview_checksums_are_rejected(self):
        for path in (self.bundle / 'rereflect-app-source.tar.gz', self.root / 'Dockerfile.api'):
            original = path.read_bytes()
            path.write_bytes(original + b'changed')
            before = self.snapshot()
            with self.assertRaises(updater.UpdateError):
                updater.update(self.root, self.bundle)
            self.assertEqual(self.snapshot(), before)
            path.write_bytes(original)

    def test_credentials_are_never_read_and_cannot_join_manifest(self):
        original = Path.read_bytes
        def guarded(path):
            if path.name in ('runtime.env', 'login.txt', 'local-login.json'):
                raise AssertionError('private credentials were read')
            return original(path)
        with patch.object(Path, 'read_bytes', guarded):
            self.assertTrue(updater.update(self.root, self.bundle))
        checksums = json.loads((self.root / 'checksums.json').read_text())
        checksums['private/runtime.env'] = '0' * 64
        (self.root / 'checksums.json').write_text(json.dumps(checksums))
        with patch.object(Path, 'read_bytes', guarded), self.assertRaises(updater.UpdateError):
            updater.update(self.root, self.bundle)

    def test_required_survey_migration_and_runtime_are_checked(self):
        for name in updater.APP_MARKERS:
            if 'survey' not in name.lower():
                continue
            with self.subTest(marker=name):
                self.archive(omit=name)
                before = self.snapshot()
                with self.assertRaises(updater.UpdateError):
                    updater.update(self.root, self.bundle)
                self.assertEqual(self.snapshot(), before)

    def test_traversal_absolute_and_symlink_entries_are_rejected(self):
        for name, kind in (('../escape', tarfile.REGTYPE), ('/escape', tarfile.REGTYPE), ('link', tarfile.SYMTYPE)):
            member = tarfile.TarInfo(name)
            member.type, member.linkname = kind, '/tmp/escape'
            self.archive(unsafe=member)
            before = self.snapshot()
            with self.assertRaises(updater.UpdateError):
                updater.update(self.root, self.bundle)
            self.assertEqual(self.snapshot(), before)

    def test_unfinished_backup_is_preserved(self):
        (self.root / updater.BACKUP).mkdir()
        (self.root / updater.BACKUP / 'keep').write_text('keep backup')
        before = self.snapshot()
        with self.assertRaises(updater.UpdateError):
            updater.update(self.root, self.bundle)
        self.assertEqual(self.snapshot(), before)

    def test_failed_metadata_write_restores_original_source(self):
        original = updater.atomic_write
        failed = False
        def write(path, data, mode):
            nonlocal failed
            if path.name == 'checksums.json' and not failed:
                failed = True
                raise OSError('synthetic file failure')
            return original(path, data, mode)
        before = self.snapshot()
        with patch.object(updater, 'atomic_write', write), self.assertRaises(OSError):
            updater.update(self.root, self.bundle)
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
