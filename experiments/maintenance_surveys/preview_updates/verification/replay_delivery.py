"""Replay a delivered ZIP on synthetic previews; never start Docker or touch Mac data."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
from unittest.mock import patch
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip', type=Path)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[4]
    with tempfile.TemporaryDirectory(prefix='survey-delivery-replay-') as directory:
        root = Path(directory)
        with zipfile.ZipFile(args.zip) as archive:
            # Only extract our locally built, inspected delivery into a fresh directory.
            assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in archive.namelist())
            archive.extractall(root)
        bundle = root / 'boomsay-survey-continuity-update'
        spec = importlib.util.spec_from_file_location('delivered_updater', bundle / 'update-preview.py')
        updater = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(updater)
        meta = json.loads((bundle / 'update.json').read_text())
        archive_bytes = (bundle / 'rereflect-app-source.tar.gz').read_bytes()
        assert hashlib.sha256(archive_bytes).hexdigest() == meta['sha256']
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode='r:gz') as archive:
            files = [entry for entry in archive.getmembers() if entry.isfile()]
            for entry in files:
                expected = subprocess.check_output(['git', 'show', meta['commit'] + ':' + entry.name], cwd=repository)
                assert archive.extractfile(entry).read() == expected, entry.name
        print(f'PASS: {len(files)} packaged source files match commit {meta["commit"]}.')
        print('PASS: archive checksum matches delivery manifest.')
        start = b'#!/bin/sh\n# Synthetic startup: never executed.\n'
        for base in ('59dfd9122b20d0098eceedf8e1d1296e86b6f0a3', 'ccb53d4122a76ffd6045d2bf188d20dfdb712d2d'):
            preview = root / base
            preview.mkdir()
            for name in updater.MANIFEST_REQUIRED:
                path = preview / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fictional baseline sentinel\n')
            (preview / 'start-local.sh').write_bytes(start)
            (preview / 'SOURCE.txt').write_text(f'Application: andruch98/rereflect\nCommit: {base}\n')
            (preview / 'configure.py').write_text('# boomsay-dashboard-preview-local\n')
            (preview / 'compose.json').write_text('{"existing":"synthetic volume and network"}')
            for name in ('runtime.env', 'login.txt', 'database-sentinel', 'saved-chats-sentinel'):
                (preview / 'private' / name).write_text('fictional private state: ' + name)
            (preview / 'app').mkdir()
            (preview / 'app/original.txt').write_text('old source')
            (preview / 'backup-before-maintenance-survey-update').mkdir()
            (preview / 'backup-before-maintenance-survey-update/original.txt').write_text('prior backup')
            (preview / 'checksums.json').write_text(json.dumps({
                name: updater.digest((preview / name).read_bytes()) for name in updater.MANIFEST_REQUIRED | {'start-local.sh'}
            }))
            def snapshot():
                return {str(p.relative_to(preview)): p.read_bytes() for p in preview.rglob('*') if p.is_file()}
            before = snapshot()
            with patch.object(updater, 'STARTUP_HASHES', {updater.digest(start)}):
                assert updater.update(preview, bundle) is True
                after = snapshot()
                for name, value in before.items():
                    if name.startswith(('private/', 'backup-before-maintenance-survey-update/')) or name in ('compose.json', 'configure.py', 'start-local.sh'):
                        assert after[name] == value, name
                assert after[updater.BACKUP + '/app/original.txt'] == b'old source'
                assert updater.update(preview, bundle) is False
                assert after == snapshot()
            print(f'PASS: synthetic {base[:8]} update preserves private/configuration/backup sentinels; repeat is a no-op.')
        print('LIMIT: startup hash substituted only in memory for synthetic fixture; no real Mac/Docker/database startup tested.')


if __name__ == '__main__':
    main()
