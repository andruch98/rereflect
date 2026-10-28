"""Package an exact committed application tree, never a local preview or .env."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import zipfile


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
SOURCE_PATHS = (
    'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml', 'packages/ui',
    'services/frontend-web', 'services/backend-api', 'services/analysis-engine',
    'LICENSE', 'NOTICE',
)
SUPPORTED_BASES = (
    '051d06fa9d5e81108c3ea01366e2b24f2ec86a48',
    '7519b93674d40f87e9915ae458ac503cd69e1d2d',
    'e19eb96cf0a19802d9bcc569c643845e36417032',
    '66e7ec4c61a147eced6eed05be45207725253ba6',
    '4c117094a132b3f395140026336b25ee220ca862',
    '5b39b14ff540b2d2de57f90fe8390b7040d2d16f',
    'bf6236c84291d633435a1b73719d7b645942a715',
    '724ca86b0de00c59ade1c8c54fac17ec9bacbc71',
    '5bba1ce0c502c074d481a4b2228091ec5873c72d',
)
BUNDLE_NAME = 'boomsay-genius-review-links-update'


def build(commit: str, output: Path, verification_log: Path | None = None) -> None:
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Pass the exact final 40-character application commit.')
    subprocess.run(['git', 'cat-file', '-e', commit + '^{commit}'], cwd=REPOSITORY, check=True)
    if output.exists():
        raise ValueError('The output already exists; choose a new path to preserve it.')
    for name in ('build-update.py', 'update-preview.py', 'README.txt'):
        committed = subprocess.check_output(
            ['git', 'show', commit + ':experiments/ask_genius/preview_updates/' + name], cwd=REPOSITORY)
        if committed != (HERE / name).read_bytes():
            raise ValueError('The updater scripts must match the selected commit before packaging.')
    spec = importlib.util.spec_from_file_location('genius_updater', HERE / 'update-preview.py')
    updater = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(updater)
    with tempfile.TemporaryDirectory(prefix='boomsay-genius-package-') as staging:
        root = Path(staging) / BUNDLE_NAME
        root.mkdir()
        archive = root / 'rereflect-app-source.tar.gz'
        subprocess.run(['git', 'archive', '--format=tar.gz', '--output', str(archive),
                        commit, *SOURCE_PATHS], cwd=REPOSITORY, check=True)
        with tarfile.open(archive) as source:
            updater.safe_members(source)
            names = {member.name for member in source.getmembers() if member.isfile()}
            if not set(updater.APP_MARKERS) <= names:
                raise ValueError('The selected commit lacks required Ask Genius files.')
        meta = {'commit': commit, 'bases': list(SUPPORTED_BASES),
                'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
        (root / 'update.json').write_text(json.dumps(meta, indent=2) + '\n')
        for name in ('update-preview.py', 'README.txt'):
            (root / name).write_bytes((HERE / name).read_bytes())
        if verification_log:
            (root / 'verification').mkdir()
            (root / 'verification/offline-checks.txt').write_bytes(verification_log.read_bytes())
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(root.rglob('*')):
                if path.is_file():
                    bundle.write(path, str(path.relative_to(root.parent)))
    print(str(output))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verification-log', type=Path)
    args = parser.parse_args()
    build(args.commit, args.output, args.verification_log)


if __name__ == '__main__':
    main()
