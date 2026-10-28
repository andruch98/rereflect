"""Configure only the known local BoomSay preview. Never sends a model request."""
from __future__ import annotations

import copy
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile
import tempfile
from urllib.parse import urlsplit
import warnings


BUNDLE = Path(__file__).resolve().parent
CONFIG_KEYS = {
    'ASK_GENIUS_ENABLED': 'true',
    'ASK_GENIUS_PROVIDER': 'openai',
    'ASK_GENIUS_MODEL': 'gpt-4.1-mini',
    'ASK_GENIUS_BASE_URL': '',
}
ENV_KEY = re.compile(r'^([A-Z][A-Z0-9_]*)=(.*)$')
KEY_VALUE = re.compile(r'[A-Za-z0-9_-]{20,512}')
DOCKERIGNORE = (BUNDLE / 'preview.dockerignore').read_bytes()


class SetupError(Exception):
    """A safe, secret-free message suitable for Terminal."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise SetupError('A required preview file is missing or is a symbolic link. Nothing changed.')


def read_env(data: bytes) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in data.decode('utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = ENV_KEY.fullmatch(line)
        if not match or match[1] in values:
            raise SetupError('The preview environment is not in the expected format. Nothing changed.')
        value = match[2]
        if value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        values[match[1]] = value
    return values


def updated_env(old: bytes, key: str) -> bytes:
    changes = {**CONFIG_KEYS, 'ASK_GENIUS_API_KEY': key}
    lines = old.decode('utf-8').splitlines(keepends=True)
    kept = [line for line in lines if not ((m := ENV_KEY.fullmatch(line.rstrip('\r\n'))) and m[1] in changes)]
    text = ''.join(kept)
    if text and not text.endswith('\n'):
        text += '\n'
    # The restricted key alphabet excludes dotenv expansion, quotes and newlines.
    return (text + ''.join(f'{name}={value}\n' for name, value in changes.items())).encode()


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    fd, name = tempfile.mkstemp(prefix='.ask-genius-', dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def safe_members(tar: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = tar.getmembers()
    seen: set[str] = set()
    for member in members:
        path = Path(member.name)
        if (path.is_absolute() or '..' in path.parts or member.name in seen
                or not (member.isfile() or member.isdir())):
            raise SetupError('The archive contains an unsafe entry. Nothing changed.')
        seen.add(member.name)
    return members


def validate(root: Path) -> dict:
    private = root / 'private'
    if private.is_symlink() or not private.is_dir():
        raise SetupError('Use your existing boomsay-dashboard-preview folder. Nothing changed.')
    required = ('SOURCE.txt', 'checksums.json', 'configure.py', 'start-local.sh',
                'compose.json', 'private/runtime.env', 'private/login.txt',
                'private/local-login.json', 'private/blocked-ledger.sqlite')
    for name in required:
        regular(root / name)
    if (root / 'app').is_symlink():
        raise SetupError('The preview app must not be a symbolic link. Nothing changed.')
    meta = json.loads((BUNDLE / 'update.json').read_text())
    trusted = json.loads((BUNDLE / 'trusted-preview.json').read_text())
    source = (root / 'SOURCE.txt').read_text()
    commits = re.findall(r'^Commit: ([a-f0-9]{40})$', source, re.MULTILINE)
    if ('Application: andruch98/rereflect\n' not in source or len(commits) != 1
            or commits[0] not in [*meta['bases'], meta['commit']]):
        raise SetupError('This is not a supported BoomSay preview version. Nothing changed.')
    for name, allowed in trusted['files'].items():
        regular(root / name)
        if digest((root / name).read_bytes()) not in allowed:
            raise SetupError('A preview setup file differs from the supported version. Nothing changed.')
    checksums = json.loads((root / 'checksums.json').read_text())
    required_manifest = set(trusted['manifest_names'])
    if not required_manifest <= set(checksums) or set(checksums) - required_manifest - {'start-local.sh', 'stop-local.sh', '.dockerignore'}:
        raise SetupError('The preview checksum manifest is not recognized. Nothing changed.')
    for name, expected in checksums.items():
        regular(root / name)
        if digest((root / name).read_bytes()) != expected:
            raise SetupError('Preview file integrity verification failed. Nothing changed.')
    archive = BUNDLE / 'rereflect-app-source.tar.gz'
    if digest(archive.read_bytes()) != meta['sha256']:
        raise SetupError('The update archive failed verification. Nothing changed.')
    with tarfile.open(archive) as tar:
        members = safe_members(tar)
        if commits[0] == meta['commit'] and (root / 'app').is_dir():
            archived_files = {member.name for member in members if member.isfile()}
            for extra in (root / 'app').rglob('*'):
                relative = extra.relative_to(root / 'app')
                if extra.is_symlink():
                    raise SetupError('The installed app contains a symbolic link. Nothing changed.')
                if any(part in {'.git', 'node_modules', '.next', '__pycache__'} for part in relative.parts):
                    continue
                if extra.name == '.DS_Store' or extra.suffix == '.pyc':
                    continue
                if extra.is_file() and relative.as_posix() not in archived_files:
                    raise SetupError('The installed app has files outside its source archive. Nothing changed.')
            for member in members:
                path = root / 'app' / member.name
                if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root):
                    raise SetupError('The installed app contains a symbolic link. Nothing changed.')
                if member.isfile():
                    if not path.is_file() or digest(path.read_bytes()) != digest(tar.extractfile(member).read()):
                        raise SetupError('The installed app differs from its source archive. Nothing changed.')
    if (root / '.dockerignore').exists() or (root / '.dockerignore').is_symlink():
        regular(root / '.dockerignore')
        if digest((root / '.dockerignore').read_bytes()) not in trusted['dockerignore_hashes']:
            raise SetupError('An unrecognized Docker build exclusion file exists. Nothing changed.')
    env_bytes = (private / 'runtime.env').read_bytes()
    env = read_env(env_bytes)
    for name, expected in {
        'BOOMSAY_REVIEW_PREVIEW': 'true', 'BOOMSAY_PREVIEW_ORGANIZATION_ID': '1',
        'APARTMENT_EXPERIMENT_ORG_ID': '1',
        'APARTMENT_EXPERIMENT_LEDGER': '/private/blocked-ledger.sqlite',
        'APARTMENT_EXPERIMENT_MANIFEST': '/private/not-authorized.json',
        'OPENAI_API_KEY': '', 'ANTHROPIC_API_KEY': '', 'GOOGLE_API_KEY': '',
        'GEMINI_API_KEY': '', 'RESEND_API_KEY': '', 'SENTRY_DSN': '',
    }.items():
        if env.get(name) != expected:
            raise SetupError('The isolated preview safety settings differ. Nothing changed.')
    # Parse locally to confirm the DB is the existing private preview; never connect.
    database = urlsplit(env.get('DATABASE_URL', ''))
    if (database.scheme != 'postgresql' or database.hostname != 'postgres'
            or database.port != 5432 or database.path != '/rereflect_dashboard_preview'
            or database.username != 'apartment_preview'):
        raise SetupError('The preview database configuration differs. Nothing changed.')
    compose_bytes = (root / 'compose.json').read_bytes()
    compose = json.loads(compose_bytes)
    expected_compose = json.loads((BUNDLE / 'expected-compose.json').read_text())
    expected_compose['services']['postgres']['environment']['POSTGRES_PASSWORD'] = database.password
    enabled_compose = copy.deepcopy(expected_compose)
    enabled_compose['services']['api']['networks'].append('ask_genius_outbound')
    enabled_compose['networks']['ask_genius_outbound'] = {}
    if compose != expected_compose and compose != enabled_compose:
        raise SetupError('The preview Docker layout differs from the supported version. Nothing changed.')
    if not database.password:
        raise SetupError('The preview database credential is missing. Nothing changed.')
    existing_key = env.get('ASK_GENIUS_API_KEY', '')
    if existing_key and not KEY_VALUE.fullmatch(existing_key):
        raise SetupError('The existing Ask Genius key has an unsupported format. Nothing changed.')
    return {'meta': meta, 'checksums': checksums, 'source_commit': commits[0],
            'env_bytes': env_bytes, 'existing_key': existing_key,
            'compose_bytes': compose_bytes, 'new_compose': enabled_compose}


def ask_key(existing: str) -> str:
    if not sys.stdin.isatty():
        raise SetupError('Run this from an interactive Terminal. Hidden key entry is required; nothing changed.')
    prompt = 'OpenAI API key (hidden; Enter keeps the existing Ask Genius key): ' if existing else 'OpenAI API key (hidden): '
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            entered = getpass.getpass(prompt)
        except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
            raise SetupError('Setup canceled before changes. The key was not saved.') from None
    key = entered or existing
    if not KEY_VALUE.fullmatch(key):
        raise SetupError('Key format not accepted. No changes were made; copy the API key again without spaces.')
    return key


def apply_setup(root: Path, state: dict, key: str) -> None:
    if not KEY_VALUE.fullmatch(key):
        raise SetupError('Key format not accepted. Nothing changed.')
    meta = state['meta']
    source_changed = state['source_commit'] != meta['commit'] or not (root / 'app').is_dir()
    backup = root / 'backup-before-openai-setup'
    if source_changed and backup.exists():
        raise SetupError('An earlier update backup exists. Keep it and ask for help before retrying; nothing changed.')
    # Recheck for changes since the prompt before preparing the atomic replacements.
    fresh = validate(root)
    if (fresh['env_bytes'] != state['env_bytes'] or fresh['compose_bytes'] != state['compose_bytes']
            or fresh['source_commit'] != state['source_commit'] or fresh['checksums'] != state['checksums']):
        raise SetupError('Preview configuration changed during setup. Nothing changed.')
    old_start = (root / 'start-local.sh').read_bytes()
    new_start = old_start.replace(b'No AI keys or workers are needed.', b'No analysis workers are started.')
    new_start = new_start.replace(b'docker compose -f compose.json',
                                 b'docker compose -p boomsay-dashboard-preview-local -f compose.json')
    new_stop = (root / 'stop-local.sh').read_bytes().replace(
        b'docker compose -f compose.json', b'docker compose -p boomsay-dashboard-preview-local -f compose.json')
    manifest = dict(state['checksums'])
    manifest.update({'rereflect-app-source.tar.gz': meta['sha256'],
                     'start-local.sh': digest(new_start), 'stop-local.sh': digest(new_stop),
                     '.dockerignore': digest(DOCKERIGNORE)})
    changes = {
        '.dockerignore': DOCKERIGNORE,
        'start-local.sh': new_start,
        'stop-local.sh': new_stop,
        'compose.json': (json.dumps(state['new_compose'], indent=2) + '\n').encode(),
        'private/runtime.env': updated_env(state['env_bytes'], key),
        'checksums.json': (json.dumps(manifest, indent=2) + '\n').encode(),
    }
    if source_changed:
        changes['rereflect-app-source.tar.gz'] = (BUNDLE / 'rereflect-app-source.tar.gz').read_bytes()
        changes['SOURCE.txt'] = ('Application: andruch98/rereflect\nBranch: feat/boomsay-ask-genius\n'
                                f"Commit: {meta['commit']}\nSaved records unchanged. Ask Genius uses explicit OpenAI gpt-4.1-mini setup.\n").encode()
    originals = {name: (root / name).read_bytes() if (root / name).exists() else None for name in changes}
    os.chmod(root / 'private', 0o700)
    with tempfile.TemporaryDirectory(prefix='.ask-genius-staging-', dir=root) as staging:
        unpacked = Path(staging) / 'app'
        if source_changed:
            unpacked.mkdir()
            with tarfile.open(BUNDLE / 'rereflect-app-source.tar.gz') as tar:
                safe_members(tar)
                tar.extractall(unpacked)
            if not (unpacked / 'services/backend-api/src/services/ask_genius.py').is_file():
                raise SetupError('The archive is missing Ask Genius. Nothing changed.')
        swapped = False
        written: list[str] = []
        try:
            if source_changed:
                backup.mkdir(mode=0o700)
                for name in ('SOURCE.txt', 'checksums.json', 'rereflect-app-source.tar.gz'):
                    shutil.copy2(root / name, backup / name)
                if (root / 'app').exists():
                    (root / 'app').rename(backup / 'app')
                unpacked.rename(root / 'app')
                swapped = True
            # Write network before enabled environment; containers change only on restart.
            for name, data in changes.items():
                if originals[name] != data:
                    atomic_write(root / name, data)
                    written.append(name)
            os.chmod(root / 'private/runtime.env', 0o600)
            os.chmod(root / 'compose.json', 0o600)
        except BaseException:
            for name in reversed(written):
                if originals[name] is None:
                    (root / name).unlink(missing_ok=True)
                else:
                    atomic_write(root / name, originals[name])
            if source_changed and backup.exists():
                if swapped and (root / 'app').exists():
                    shutil.rmtree(root / 'app')
                if (backup / 'app').exists():
                    (backup / 'app').rename(root / 'app')
                shutil.rmtree(backup)
            raise


def main() -> int:
    os.umask(0o077)
    root = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) == 2 else Path.cwd().resolve()
    try:
        state = validate(root)
        key = ask_key(state['existing_key'])
        apply_setup(root, state, key)
    except SetupError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError):
        # Do not print raw exceptions: file/config exceptions may contain private values.
        print('Setup could not complete. Keep the preview folder and its backup; no model call was made.', file=sys.stderr)
        return 1
    print('Saved the separate Ask Genius key privately and selected OpenAI gpt-4.1-mini.')
    print('Only the API gains outbound connectivity; database, Redis and web remain on the internal network.')
    print('Existing login, saved reviews, database volume and blocked analysis ledger are preserved.')
    print('No model request was made. Key validity and live answers still need verification.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
