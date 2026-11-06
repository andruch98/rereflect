"""Pin the local Docker daemon and make the private env file authoritative."""
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def docker_env():
    env = dict(os.environ)
    for key in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'):
        env.pop(key, None)
    # Compose normally lets inherited shell values override --env-file. Strip
    # only variables actually interpolated in this project's trusted config;
    # preserve proxy settings, Docker auth config and unrelated SDK bindings.
    for key in re.findall(r'\$\{([A-Za-z_][A-Za-z0-9_]*)', (ROOT/'compose.yml').read_text()):
        env.pop(key, None)
    return env


def compose_command():
    envfile = os.environ.get('BOOMSAY_ENV_FILE', '/etc/boomsay/boomsay.env')
    return ['docker', '--host=unix:///var/run/docker.sock', 'compose', '--project-name',
            'boomsay-cloud', '--env-file', envfile, '--file', str(ROOT/'compose.yml')]
