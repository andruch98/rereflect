"""Replace preview application source only; never read or change AI credentials."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tarfile
import tempfile


BACKUP = 'backup-before-genius-improvements'
MUTATED_FILES = ('rereflect-app-source.tar.gz', 'checksums.json', 'SOURCE.txt')
MANIFEST_REQUIRED = {
    'rereflect-app-source.tar.gz', 'private/saved-ai-records.json', 'restore.py',
    'preview-requirements.txt', 'Dockerfile.api', 'Dockerfile.web',
    'preview-nginx.conf', 'verify-local.py',
}
MANIFEST_ALLOWED = MANIFEST_REQUIRED | {'start-local.sh', 'stop-local.sh', '.dockerignore'}
HASH = re.compile(r'[a-f0-9]{64}')
COMMIT = re.compile(r'[a-f0-9]{40}')
# Both shipped starters run the normal Alembic migration before starting the
# updated API. Keep startup and credentials untouched; reject unknown starters.
STARTUP_HASHES = {
    '63cd57fe7b41cf9b4ca6d951313db60a6d28e485a3b8e4dfbcc0b9bd65c4b9ba',
    '5a2745e71ede215fa5cfdf8b081829b5c7ae65e0a423a1f078c0d754d491ec10',
}
LOCAL_LAYOUT_COMMIT = 'bf6236c84291d633435a1b73719d7b645942a715'
LOCAL_LAYOUT_ARCHIVE_HASH = 'aedf86696d06521dfe89a9aec55c49940596f933bf0d23dcb17f02ab81007300'
APP_MARKERS = (
    'services/frontend-web/components/reviews/AskGenius.tsx',
    'services/backend-api/src/services/ask_genius.py',
    'services/backend-api/src/services/ask_genius_instructions.txt',
    'services/backend-api/src/services/ask_genius_periods.py',
    'services/backend-api/alembic/versions/d0c6241e9f32_add_ask_genius_default_period.py',
)


class UpdateError(Exception):
    """A safe, credential-free message for Terminal."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def regular(root: Path, name: str) -> Path:
    path = root / name
    if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root):
        raise UpdateError('A required preview path is a symbolic link. Nothing changed.')
    if not path.is_file():
        raise UpdateError('A required preview file is missing. Nothing changed.')
    return path


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix='.genius-update-', dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def safe_members(archive: tarfile.TarFile) -> None:
    seen: set[str] = set()
    for member in archive.getmembers():
        path = Path(member.name)
        normalized = path.as_posix()
        if (path.is_absolute() or '..' in path.parts or normalized in ('', '.')
                or normalized in seen or not (member.isfile() or member.isdir())):
            raise UpdateError('The update archive contains an unsafe entry. Nothing changed.')
        seen.add(normalized)


def update(root: Path, bundle: Path) -> bool:
    meta = json.loads(regular(bundle, 'update.json').read_text())
    if (not isinstance(meta, dict) or not COMMIT.fullmatch(meta.get('commit', ''))
            or not HASH.fullmatch(meta.get('sha256', ''))
            or not isinstance(meta.get('bases'), list)
            or not all(isinstance(base, str) and COMMIT.fullmatch(base) for base in meta['bases'])):
        raise UpdateError('The update manifest is invalid. Nothing changed.')
    archive_bytes = regular(bundle, 'rereflect-app-source.tar.gz').read_bytes()
    if digest(archive_bytes) != meta['sha256']:
        raise UpdateError('The update archive failed verification. Nothing changed.')
    for name in (*MUTATED_FILES, 'start-local.sh', 'configure.py'):
        regular(root, name)
    if digest((root / 'start-local.sh').read_bytes()) not in STARTUP_HASHES:
        raise UpdateError('The preview startup script is not recognized. Its database-upgrade step must be checked before updating. Nothing changed.')
    app = root / 'app'
    if app.is_symlink() or (app.exists() and not app.is_dir()):
        raise UpdateError('The preview application path is not a regular directory. Nothing changed.')
    source = (root / 'SOURCE.txt').read_text()
    source_lines = source.splitlines()
    applications = [line for line in source_lines if line.startswith('Application:')]
    commits = [line for line in source_lines if line.startswith('Commit:')]
    if (applications != ['Application: andruch98/rereflect'] or len(commits) != 1
            or not re.fullmatch(r'Commit: [a-f0-9]{40}', commits[0])
            or commits[0][8:] not in [*meta['bases'], meta['commit']]
            or 'boomsay-dashboard-preview-local' not in (root / 'configure.py').read_text()):
        raise UpdateError('This is not a supported BoomSay preview version. Nothing changed.')
    if commits[0][8:] == LOCAL_LAYOUT_COMMIT and digest((root / 'rereflect-app-source.tar.gz').read_bytes()) != LOCAL_LAYOUT_ARCHIVE_HASH:
        raise UpdateError('The local layout application archive does not match its verified release. Nothing changed.')
    checksums = json.loads((root / 'checksums.json').read_text())
    if (not isinstance(checksums, dict) or not MANIFEST_REQUIRED <= set(checksums)
            or not set(checksums) <= MANIFEST_ALLOWED):
        raise UpdateError('The preview checksum manifest is not recognized. Nothing changed.')
    # The explicit name allowlist cannot include runtime.env, login files or other credentials.
    for name, expected in checksums.items():
        if not isinstance(expected, str) or not HASH.fullmatch(expected):
            raise UpdateError('The preview checksum manifest is invalid. Nothing changed.')
        if digest(regular(root, name).read_bytes()) != expected:
            raise UpdateError('Existing preview files differ from their manifest. Nothing changed.')
    if commits[0][8:] == meta['commit']:
        if not app.is_dir() or not all((app / name).is_file() for name in APP_MARKERS):
            raise UpdateError('This update is recorded but application files are missing. Keep the backup and ask for help.')
        return False
    backup = root / BACKUP
    if backup.exists() or backup.is_symlink():
        raise UpdateError('An Ask Genius improvement backup already exists. Keep it and ask for help before retrying.')
    originals = {name: (root / name).read_bytes() for name in MUTATED_FILES}
    modes = {name: stat.S_IMODE((root / name).stat().st_mode) for name in MUTATED_FILES}
    with tempfile.TemporaryDirectory(prefix='.genius-improvements-', dir=root) as staging:
        unpacked = Path(staging) / 'app'
        unpacked.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode='r:gz') as archive:
            safe_members(archive)
            archive.extractall(unpacked)
        if not all((unpacked / name).is_file() for name in APP_MARKERS):
            raise UpdateError('The update archive is missing application files. Nothing changed.')
        for name in MUTATED_FILES:
            if regular(root, name).read_bytes() != originals[name]:
                raise UpdateError('The preview changed during preparation. Nothing changed.')
        updated_checksums = {**checksums, 'rereflect-app-source.tar.gz': meta['sha256']}
        replacements = {
            'rereflect-app-source.tar.gz': archive_bytes,
            'checksums.json': (json.dumps(updated_checksums, indent=2) + '\n').encode(),
            'SOURCE.txt': ('Application: andruch98/rereflect\nBranch: feat/boomsay-ask-genius\n'
                           f"Commit: {meta['commit']}\nAsk Genius updated; private data and AI setup unchanged. Startup applies the additive preference migration.\n").encode(),
        }
        moved_old = installed_new = created_backup = False
        written: list[str] = []
        try:
            backup.mkdir(mode=0o700)
            created_backup = True
            for name in MUTATED_FILES:
                shutil.copy2(root / name, backup / name)
            if app.exists():
                app.rename(backup / 'app')
                moved_old = True
            unpacked.rename(app)
            installed_new = True
            for name, data in replacements.items():
                atomic_write(root / name, data, modes[name])
                written.append(name)
        except BaseException:
            # If rollback itself fails, retain the source backup for manual recovery.
            for name in reversed(written):
                atomic_write(root / name, originals[name], modes[name])
            if installed_new and app.exists():
                shutil.rmtree(app)
            if moved_old:
                (backup / 'app').rename(app)
            if created_backup:
                shutil.rmtree(backup)
            raise
    return True


def main() -> int:
    os.umask(0o077)
    bundle = Path(__file__).resolve().parent
    root = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) == 2 else Path.cwd().resolve()
    try:
        changed = update(root, bundle)
    except UpdateError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError):
        print('The update could not complete. Keep your preview and any backup; no AI request was made.', file=sys.stderr)
        return 1
    print('Application updated; existing data, login and AI setup were preserved.' if changed else 'This Ask Genius update is already installed.')
    print('Now run: bash start-local.sh')
    print('Startup rebuilds the app and adds the saved-period preference field through its existing database migration step.')
    print('Then open http://127.0.0.1:53004/ask-genius with your existing login.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
