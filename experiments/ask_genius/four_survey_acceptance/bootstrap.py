"""Load the checksum-verified PR source in a temporary directory, never over the app."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import runpy
import sys
import tempfile
from zipfile import ZipFile


def unpack(job, destination):
    archive = base64.b64decode(job['archive'], validate=True)
    if hashlib.sha256(archive).hexdigest() != job['sha256']:
        raise ValueError('Source package checksum mismatch')
    with ZipFile(io.BytesIO(archive)) as bundle:
        for entry in bundle.infolist():
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or '..' in path.parts or entry.file_size > 5_000_000:
                raise ValueError('Unexpected source package member')
            target = destination.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(entry))


if __name__ == '__main__':
    try:
        job = json.load(sys.stdin)
        with tempfile.TemporaryDirectory(prefix='boomsay-pr12-test-') as directory:
            root = Path(directory)
            unpack(job, root)
            # Disable any inherited SQL logging. Keep the configured provider/model/key.
            os.environ['SQL_ECHO'] = 'false'
            os.environ['CACHE_ENABLED'] = 'false'
            sys.path.insert(0, str(root))
            runpy.run_path(str(root / 'runner.py'), run_name='__main__')
    except Exception as exc:
        print(json.dumps({'kind': 'preflight_failure', 'reason': type(exc).__name__ +
                          ': could not load the PR12 diagnostic; no requests sent.'}), flush=True)
        raise SystemExit(1)
