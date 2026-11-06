"""Bounded non-root host-script checks; never contacts Docker or a server.

Root-only entry points are checked unchanged. To exercise backup sequencing on
an unprivileged workstation, an isolated copy changes ONLY fixed server paths,
the EUID refusal and expected file-owner UID. Docker/age/git are explicit fake
commands. These checks do not validate encryption, pg_dump format or restore.
"""
from pathlib import Path
import json
import os
import subprocess
import tempfile


def main():
    source = Path(__file__).resolve().parent
    results = []
    for name in ('prepare-host.sh', 'backup.sh', 'restore-check.sh'):
        checked = subprocess.run(['bash', '-n', str(source / name)], capture_output=True, text=True)
        assert checked.returncode == 0, checked.stderr
        results.append({'case': 'shell syntax: ' + name, 'passed': True})
        if os.geteuid() != 0:
            refused = subprocess.run(['bash', str(source / name)], capture_output=True, text=True)
            assert refused.returncode != 0 and 'sudo' in refused.stderr
            results.append({'case': 'unchanged non-root refusal: ' + name, 'passed': True, 'output': refused.stderr.strip()})
    with tempfile.TemporaryDirectory(prefix='boomsay-backup-verification-') as raw:
        root = Path(raw)
        app, etc, backups, fakebin = [root / name for name in ('app', 'etc', 'backups', 'bin')]
        for path in (app / 'deploy/ovh', etc, backups, fakebin):
            path.mkdir(parents=True)
        (app / 'deploy/ovh/compose.yml').write_text('services: {}\n')
        # Transport-only stand-in. Real compose.py validation/socket isolation
        # are tested by the deployment preparation's own verification suite.
        (app / 'deploy/ovh/compose.py').write_text("import os,sys\nos.execvp('docker',['docker','--host=unix:///var/run/docker.sock','compose']+sys.argv[1:])\n")
        env_file = etc / 'boomsay.env'
        env_file.write_text('POSTGRES_PASSWORD=fictional-never-used\nLLM_ENCRYPTION_KEY=fictional-capture-only\n')
        env_file.chmod(0o600)
        recipient = etc / 'backup-recipient.txt'
        recipient.write_text('age1fictionalpublicrecipient\n')
        recipient.chmod(0o600)
        script = (source / 'backup.sh').read_text()
        assert script.count("[[ $EUID -eq 0 ]] || fail 'Run with sudo on the VPS.'") == 1
        script = script.replace("[[ $EUID -eq 0 ]] || fail 'Run with sudo on the VPS.'", '# EUID refusal tested above; fixture copy only.')
        for before, after in (
            ('app=/opt/boomsay/current', 'app=' + str(app)),
            ('env_file=/etc/boomsay/boomsay.env', 'env_file=' + str(env_file)),
            ('recipient_file=/etc/boomsay/backup-recipient.txt', 'recipient_file=' + str(recipient)),
            ('backup_dir=/var/backups/boomsay', 'backup_dir=' + str(backups)),
        ):
            assert script.count(before) == 1
            script = script.replace(before, after)
        script = script.replace('== 0 &&', '== ' + str(os.geteuid()) + ' &&')
        test_script = root / 'fixture-backup.sh'
        test_script.write_text(script)
        commands = {
            'docker': '''#!/usr/bin/env python3
import os, sys
if 'pg_dump' in sys.argv:
    if os.getenv('FAIL_DUMP'): sys.exit(5)
    if not os.getenv('EMPTY_DUMP'): sys.stdout.buffer.write(b'FICTIONAL DUMP ONLY')
elif 'pg_restore' in sys.argv:
    assert sys.stdin.buffer.read() == b'FICTIONAL DUMP ONLY'
else: sys.exit(6)
''',
            'age': '''#!/usr/bin/env python3
import io, os, pathlib, sys, tarfile
data=sys.stdin.buffer.read()
with tarfile.open(fileobj=io.BytesIO(data)) as archive:
    assert archive.extractfile('./database.dump').read()==b'FICTIONAL DUMP ONLY'
    assert b'fictional-capture-only' in archive.extractfile('./boomsay.env').read()
if os.getenv('FAIL_ENCRYPT'): sys.exit(7)
pathlib.Path(sys.argv[sys.argv.index('--output')+1]).write_bytes(b'MOCK-ENCRYPTION-NOT-AGE:'+data)
''',
            'git': '#!/usr/bin/env bash\nprintf "0000000000000000000000000000000000000000\\n"\n',
        }
        for name, contents in commands.items():
            command = fakebin / name
            command.write_text(contents)
            command.chmod(0o700)
        process_env = {**os.environ, 'PATH': str(fakebin) + ':' + os.environ['PATH']}

        def run(extra=None):
            return subprocess.run(['bash', str(test_script)], env={**process_env, **(extra or {})}, capture_output=True, text=True)

        for _ in range(8):
            done = run()
            assert done.returncode == 0, done.stderr
        archives = sorted(backups.glob('boomsay-*.tar.age'))
        assert len(archives) == 7 and len(list(backups.glob('*.sha256'))) == 7
        for checksum in backups.glob('*.sha256'):
            assert checksum.read_text().split()[1] == checksum.name.removesuffix('.sha256')
        assert not list(backups.glob('.staging.*')) and not list(backups.glob('*.partial'))
        results.append({'case': 'mock backup succeeds, includes fictional dump/config, keeps seven archives/checksums', 'passed': True})
        preserved = {p.name: p.read_bytes() for p in backups.glob('boomsay-*')}
        for failure in ('FAIL_DUMP', 'EMPTY_DUMP', 'FAIL_ENCRYPT'):
            done = run({failure: '1'})
            assert done.returncode != 0
            assert {p.name: p.read_bytes() for p in backups.glob('boomsay-*')} == preserved
            assert not list(backups.glob('.staging.*')) and not list(backups.glob('*.partial'))
            results.append({'case': failure + ' preserves existing archives and removes partial/staging files', 'passed': True, 'exit_code': done.returncode})
        env_file.chmod(0o644)
        denied = run()
        assert denied.returncode != 0 and 'mode600' in denied.stderr
        results.append({'case': 'insecure environment-file mode rejected', 'passed': True, 'output': denied.stderr.strip()})
        env_file.chmod(0o600)
        recipient.write_text('AGE-SECRET-KEY-NEVER-A-REAL-KEY\n')
        denied = run()
        assert denied.returncode != 0 and 'public recipient' in denied.stderr
        results.append({'case': 'private-identity-shaped value rejected as recipient', 'passed': True, 'output': denied.stderr.strip()})
    print(json.dumps({'mode': 'non-root guards plus isolated mock-boundary backup sequencing', 'real_server_operations': 0, 'real_docker_calls': 0, 'real_encryption_checks': 0, 'real_restore_checks': 0, 'results': results}, indent=2))


if __name__ == '__main__':
    main()
