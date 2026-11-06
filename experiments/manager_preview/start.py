"""Start or stop an isolated copy of the working BoomSay preview on a Mac."""
import argparse
import base64
import fcntl
import json
import os
from pathlib import Path
import secrets
import select
import socket
import subprocess
import sys
import time
from urllib import error, request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = Path.home() / 'Library' / 'Application Support' / 'BoomSay' / 'manager-preview-v1'
SOURCE = 'boomsay-dashboard-preview-local'
PROJECT = 'boomsay-manager-preview-v1'
SOURCE_DB = 'rereflect_dashboard_preview'
DATABASE = 'boomsay_manager_copy'
DB_USER = 'boomsay_preview'
MANAGER = 'dashboard-preview@example.com'
COMMUNITY = 'Lake House Apartments'
OWNER = 'io.boomsay.manager-preview'
PORT = 53114
URL = f'http://127.0.0.1:{PORT}'
COUNTS = """(SELECT count(*) FROM survey_instances WHERE submitted_at IS NOT NULL),
            (SELECT count(*) FROM feedback_items)"""
MANAGER_FILTER = f"""u.email = '{MANAGER}' AND o.name = '{COMMUNITY}'
    AND NOT u.is_deactivated AND NOT u.is_system_admin AND u.password_hash IS NOT NULL
    AND u.role IN ('member','admin','owner')"""
COMPOSE = ['docker', 'compose', '--project-name', PROJECT, '--project-directory', str(STATE),
           '--env-file', '/dev/null', '-f', str(STATE / 'compose.json')]


class PreviewError(Exception):
    pass


def command(args, *, input_text=None, stdin=None, stdout=subprocess.PIPE):
    """Keep credentials, records, and SQL error context out of terminal output."""
    result = subprocess.run(args, input=input_text.encode() if input_text is not None else None,
                            stdin=stdin, stdout=stdout, stderr=subprocess.PIPE)
    if result.returncode:
        raise PreviewError(f'{args[0]} failed during the step shown above (exit {result.returncode}).')
    return (result.stdout or b'').decode().strip()


def write_private(path, data):
    temp = path.with_suffix(path.suffix + '.part')
    temp.write_text(json.dumps(data, indent=2))
    temp.replace(path)


def inspect(container, template):
    return command(['docker', 'inspect', '--format', template, container])


def verify_local():
    endpoint = command(['docker', 'context', 'inspect', command(['docker', 'context', 'show']),
                        '--format', '{{.Endpoints.docker.Host}}'])
    if not endpoint.startswith('unix://') or not os.getenv('DOCKER_HOST', 'unix://').startswith('unix://'):
        raise PreviewError('Select the local Docker Desktop context and rerun.')
    command(['docker', 'info', '--format', '{{.ServerVersion}}'])
    command(['docker', 'compose', 'version'])


def source_container(service):
    name = f'{SOURCE}-{service}-1'
    if inspect(name, '{{index .Config.Labels "com.docker.compose.project"}}') != SOURCE or (
        inspect(name, '{{index .Config.Labels "com.docker.compose.service"}}') != service
    ):
        raise PreviewError('The expected original local preview container was not found.')
    return name


def load_config():
    path = STATE / 'preview.json'
    if path.exists():
        return json.loads(path.read_text())
    images = {}
    for service in ['postgres', 'redis', 'api', 'web', 'gateway']:
        container = source_container(service)
        image = inspect(container, '{{.Config.Image}}')
        pinned = inspect(container, '{{.Image}}')
        if command(['docker', 'image', 'inspect', '--format', '{{.Id}}', image]) != pinned:
            raise PreviewError(f'The local {service} image tag no longer matches the original preview container.')
        images[service] = {
            'image': image, 'platform': command(['docker', 'image', 'inspect', '--format', '{{.Os}}/{{.Architecture}}', image]),
        }
    config = {'owner': secrets.token_hex(16), 'password': secrets.token_urlsafe(24), 'jwt': secrets.token_hex(32),
              'encryption': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(), 'images': images}
    write_private(path, config)
    return config


def check_ownership(owner):
    """Only ever use this launcher's containers and the volume it initialized."""
    containers = command(['docker', 'ps', '-aq', '--filter', f'label=com.docker.compose.project={PROJECT}']).splitlines()
    for container in containers:
        if inspect(container, '{{index .Config.Labels "' + OWNER + '"}}') != owner:
            raise PreviewError('A different preview owns this Compose project. Nothing was changed.')
    volume = PROJECT + '_data'
    names = command(['docker', 'volume', 'ls', '-q', '--filter', f'name={volume}']).splitlines()
    if volume in names and command(['docker', 'volume', 'inspect', '--format',
                                    '{{index .Labels "' + OWNER + '"}}', volume]) != owner:
        raise PreviewError('A different preview owns the database volume. Nothing was changed.')


def check_port():
    gateway = command(['docker', 'ps', '-q', '--filter', f'label=com.docker.compose.project={PROJECT}',
                       '--filter', 'label=com.docker.compose.service=gateway'])
    if gateway:
        return
    with socket.socket() as test_socket:
        try:
            test_socket.bind(('127.0.0.1', PORT))
        except OSError:
            raise PreviewError(f'Port {PORT} is already in use on this Mac. No other app was stopped.') from None


def bind(source, target):
    if not source.exists():
        raise PreviewError(f'The preview ZIP is missing {source.name}. Extract the entire folder and rerun.')
    return {'type': 'bind', 'source': str(source), 'target': target, 'read_only': True,
            'bind': {'create_host_path': False}}


def compose_document(config, organization_id):
    api = ROOT / 'services' / 'backend-api'
    web = ROOT / 'services' / 'frontend-web'
    labels = {OWNER: config['owner']}
    backend_env = {
        'DATABASE_URL': f"postgresql://{DB_USER}:{config['password']}@postgres:5432/{DATABASE}",
        'JWT_SECRET': config['jwt'], 'LLM_ENCRYPTION_KEY': config['encryption'],
        'BOOMSAY_REVIEW_PREVIEW': 'true', 'BOOMSAY_PREVIEW_ORGANIZATION_ID': str(organization_id),
        'APARTMENT_EXPERIMENT_ORG_ID': str(organization_id), 'BOOMSAY_SURVEY_SIMULATION': 'true',
        'ASK_GENIUS_ENABLED': 'false', 'RESEND_API_KEY': '', 'SURVEY_PUBLIC_BASE_URL': URL,
        'APP_URL': URL, 'CORS_ORIGINS': URL, 'REDIS_HOST': 'redis', 'REDIS_PORT': '6379',
    }
    services = {name: dict(image, pull_policy='never', labels=labels, networks=['private'])
                for name, image in config['images'].items()}
    services['postgres'].update({
        'environment': {'POSTGRES_PASSWORD': config['password'], 'POSTGRES_USER': DB_USER, 'POSTGRES_DB': DATABASE},
        'volumes': ['data:/var/lib/postgresql/data'], 'healthcheck': {
            'test': ['CMD', 'pg_isready', '-U', DB_USER, '-d', DATABASE], 'interval': '2s', 'timeout': '3s', 'retries': 45,
        },
    })
    services['api'].update({
        'environment': backend_env, 'working_dir': '/app',
        'volumes': [bind(api / item, f'/app/{item}') for item in ('src', 'alembic', 'alembic.ini')],
        'command': ['python', '-m', 'uvicorn', 'src.api.main:app', '--host', '0.0.0.0', '--port', '8000', '--no-access-log'],
    })
    web_items = ('app', 'components', 'contexts', 'hooks', 'lib', 'public', 'middleware.ts', 'next.config.ts',
                 'instrumentation.ts', 'instrumentation-client.ts', 'postcss.config.js', 'tailwind.config.ts')
    services['web'].update({
        'working_dir': '/app/services/frontend-web',
        'volumes': [bind(web / item, f'/app/services/frontend-web/{item}') for item in web_items]
                   + [bind(ROOT / 'packages/ui/src', '/app/packages/ui/src')],
        'environment': {'NEXT_PUBLIC_BOOMSAY_REVIEW_PREVIEW': 'true', 'NEXT_PUBLIC_API_URL': URL,
                        'NEXT_TELEMETRY_DISABLED': '1', 'NEXT_PUBLIC_GOOGLE_CLIENT_ID': '',
                        'NEXT_PUBLIC_MIXPANEL_TOKEN': '', 'NEXT_PUBLIC_SENTRY_DSN': ''},
        'command': ['node', 'node_modules/next/dist/bin/next', 'dev', '--webpack', '--hostname', '0.0.0.0', '--port', '3000'],
    })
    services['gateway'].update({
        'depends_on': ['api', 'web'],
        'ports': [f'127.0.0.1:{PORT}:3000'], 'networks': ['private', 'entry'],
        'volumes': [bind(HERE / 'gateway.conf', '/etc/nginx/nginx.conf')],
    })
    return {'name': PROJECT, 'services': services, 'networks': {'private': {'internal': True}, 'entry': {}},
            'volumes': {'data': {'labels': labels}}}


def snapshot():
    """Counts and dump share one read-only source snapshot, even if new responses arrive."""
    meta = STATE / 'snapshot.json'
    dump = STATE / 'source.dump'
    if meta.exists() and dump.exists():
        return json.loads(meta.read_text())
    src = source_container('postgres')
    user = command(['docker', 'exec', src, 'sh', '-c', 'printf %s "${POSTGRES_USER:-postgres}"'])
    args = ['docker', 'exec', '-i', src, 'psql', '-XAtq', '-v', 'ON_ERROR_STOP=1', '-F', '|', '-U', user, '-d', SOURCE_DB]
    sql = f"""BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
\\o /dev/stdout
SELECT pg_export_snapshot(), {COUNTS}, u.organization_id FROM users u
JOIN organizations o ON o.id = u.organization_id WHERE {MANAGER_FILTER};
\\qecho snapshot_done
\\o
"""
    with subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as session:
        try:
            session.stdin.write(sql.encode())
            session.stdin.flush()
            readable, _, _ = select.select([session.stdout], [], [], 60)
            if not readable:
                raise PreviewError('The original database did not return a snapshot within one minute.')
            line = session.stdout.readline().decode().strip().split('|')
            if len(line) != 4 or not all(v.isdigit() for v in line[1:]) or (
                session.stdout.readline().strip() != b'snapshot_done'
            ):
                raise PreviewError('The expected active Lake House preview manager and source database could not be verified.')
            snapshot_id, surveys, reviews, org = line
            temp = dump.with_suffix('.part')
            with temp.open('wb') as output:
                command(['docker', 'exec', src, 'pg_dump', '-Fc', '--no-owner', '--no-acl', '--snapshot', snapshot_id,
                         '-U', user, '-d', SOURCE_DB], stdout=output)
            temp.replace(dump)
            metadata = {'surveys': int(surveys), 'reviews': int(reviews), 'organization': int(org)}
            write_private(meta, metadata)
        finally:
            session.stdin.close()  # closes the read-only source snapshot
    return metadata


def sql(statement):
    return command(COMPOSE + ['exec', '-T', 'postgres', 'psql', '-XAtq', '-v', 'ON_ERROR_STOP=1',
                              '-U', DB_USER, '-d', DATABASE], input_text=statement)


def prepare_database(config, metadata):
    marker = config['owner']
    if sql("SELECT coalesce(obj_description(oid,'pg_database'),'') FROM pg_database WHERE datname=current_database();") == marker:
        return
    tables = int(sql("SELECT count(*) FROM pg_tables WHERE schemaname='public';"))
    if not tables:
        print('Restoring the Mac snapshot into the separate preview database…', flush=True)
        with (STATE / 'source.dump').open('rb') as dump:
            command(COMPOSE + ['exec', '-T', 'postgres', 'pg_restore', '-1', '--no-owner', '--no-acl', '--exit-on-error',
                               '-U', DB_USER, '-d', DATABASE], stdin=dump)
    counts = sql('SELECT ' + COUNTS + ';')
    if counts != f"{metadata['surveys']}|{metadata['reviews']}":
        raise PreviewError('The restored counts differ from the source snapshot. No data will be overwritten.')
    org = metadata['organization']
    if sql(f'SELECT u.organization_id FROM users u JOIN organizations o ON o.id=u.organization_id WHERE {MANAGER_FILTER};') != str(org):
        raise PreviewError('The cloned manager account belongs to a different community. Setup stopped.')
    # Keep old resident links within the copy, including links displayed in historical invitation text.
    sql(f"""BEGIN;
UPDATE users u SET role = 'admin' FROM organizations o WHERE o.id=u.organization_id
 AND u.organization_id={org} AND {MANAGER_FILTER} AND u.role='member';
UPDATE survey_invitations i SET survey_url = '{URL}/survey/' || s.token,
 text = replace(i.text, i.survey_url, '{URL}/survey/' || s.token),
 html = replace(i.html, i.survey_url, '{URL}/survey/' || s.token)
 FROM survey_instances s WHERE s.id=i.survey_id AND i.organization_id={org} AND length(i.survey_url)>0;
COMMENT ON DATABASE {DATABASE} IS '{marker}';
COMMIT;""")
    print(f"Verified the copy: {metadata['surveys']} submitted surveys and {metadata['reviews']} feedback records.", flush=True)


def wait_for_web():
    local = request.build_opener(request.ProxyHandler({}))
    for path in ('/health', '/login', '/agent-settings'):
        deadline = time.monotonic() + 180
        while True:
            try:
                with local.open(URL + path, timeout=20) as response:
                    if response.status == 200:
                        break
            except (error.URLError, TimeoutError):
                pass
            if time.monotonic() >= deadline:
                raise PreviewError('The local app has not passed its health check. Rerun the start command to resume.')
            time.sleep(2)
    try:
        with local.open(URL + '/api/v1/agent-settings', timeout=10):
            raise PreviewError('The cloned settings route should require a signed-in manager.')
    except error.HTTPError as exc:
        if exc.code not in (401, 403) or exc.headers.get_content_type() != 'application/json':
            raise PreviewError('The website could not reach the protected settings API.') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=('start', 'stop'), default='start')
    action = parser.parse_args().action
    os.umask(0o077)
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (STATE / 'setup.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise PreviewError('Another start or stop is already running.') from None
        print('Checking local Docker Desktop…', flush=True)
        verify_local()
        if action == 'stop' and not (STATE / 'preview.json').exists():
            print('The manager preview is already stopped.')
            return
        config = load_config()
        check_ownership(config['owner'])
        if action == 'stop':
            if (STATE / 'compose.json').exists():
                command(COMPOSE + ['stop'])
            print('Manager preview stopped. Your test edits are saved.')
            return
        check_port()
        if (STATE / 'snapshot.json').exists():
            metadata = json.loads((STATE / 'snapshot.json').read_text())
        else:
            print('Copying your working preview with a read-only snapshot…', flush=True)
            metadata = snapshot()
        write_private(STATE / 'compose.json', compose_document(config, metadata['organization']))
        print('Starting the separate preview database…', flush=True)
        command(COMPOSE + ['up', '-d', '--wait', '--wait-timeout', '120', 'postgres', 'redis'])
        prepare_database(config, metadata)
        print('Applying this branch’s database updates to the copy…', flush=True)
        command(COMPOSE + ['run', '--rm', '--no-deps', '-T', 'api', 'python', '-m', 'alembic', 'upgrade', 'head'])
        print('Starting the local website and checking its login route…', flush=True)
        command(COMPOSE + ['up', '-d', 'api', 'web', 'gateway'])
        wait_for_web()
        print('Open ' + URL + '/agent-settings')
        print('Sign in with your existing Mac preview email and password.')
        print('Review drafts use local examples. Survey invitations and reminders are simulated.')


if __name__ == '__main__':
    try:
        main()
    except (PreviewError, OSError, ValueError) as exc:
        print(f'Setup stopped: {exc}', file=sys.stderr)
        sys.exit(1)
