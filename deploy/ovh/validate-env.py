#!/usr/bin/env python3
"""Validate only names/formats; never print secret values or source a shell file."""
import base64
import os
from pathlib import Path
import re
import stat
import sys


def read_env(path):
    path = Path(path)
    mode = path.stat()
    if not stat.S_ISREG(mode.st_mode) or mode.st_mode & 0o077:
        raise ValueError('Environment file must be a regular file with mode0600 or0400')
    values = {}
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key):
            raise ValueError(f'Invalid environment syntax at line{number}')
        if key in values:
            raise ValueError(f'Duplicate environment key {key}')
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f'Unclosed quote for {key}')
            value = value[1:-1]
        if any(c in value for c in ('\n', '\r', '\x00', '$', '`')):
            raise ValueError(f'Unsupported special characters in {key}')
        values[key] = value
    return values


def validate(values):
    host = values.get('APP_HOST', '')
    if (not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', host)
            or host.endswith(('.example', '.invalid', '.localhost'))
            or host in {'boomsay.com', 'www.boomsay.com', 'livedinit.com', 'www.livedinit.com'}):
        raise ValueError('APP_HOST must be a dedicated, real application hostname')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', values.get('TLS_EMAIL', '')):
        raise ValueError('Configure TLS_EMAIL for certificate expiry notices')
    for key in ('POSTGRES_PASSWORD', 'REDIS_PASSWORD', 'JWT_SECRET',
                'INTERNAL_API_SECRET', 'SURVEY_DEMO_PASSWORD'):
        if not re.fullmatch(r'[a-fA-F0-9]{32,}', values.get(key, '')):
            raise ValueError(f'{key} must be an independent random hexadecimal string of at least32 characters')
    secrets = [values[k] for k in ('POSTGRES_PASSWORD', 'REDIS_PASSWORD', 'JWT_SECRET',
                                  'INTERNAL_API_SECRET', 'SURVEY_DEMO_PASSWORD')]
    if len(set(secrets)) != len(secrets):
        raise ValueError('Generate a different secret for every required field')
    try:
        key = base64.urlsafe_b64decode(values.get('LLM_ENCRYPTION_KEY', '').encode())
    except Exception:
        key = b''
    if len(key) != 32:
        raise ValueError('LLM_ENCRYPTION_KEY must be a valid32-byte Fernet key')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}', values.get('RELEASE_TAG', 'local')):
        raise ValueError('Invalid RELEASE_TAG')
    if values.get('ASK_GENIUS_ENABLED', 'false') not in {'false', 'true'}:
        raise ValueError('ASK_GENIUS_ENABLED must be true or false')
    if values.get('ASK_GENIUS_ENABLED') == 'true':
        for key in ('ASK_GENIUS_PROVIDER', 'ASK_GENIUS_MODEL', 'ASK_GENIUS_API_KEY'):
            if not values.get(key):
                raise ValueError(f'{key} is required when narrative AI is enabled')


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2:
            raise ValueError('Usage: validate-env.py /etc/boomsay/boomsay.env')
        validate(read_env(sys.argv[1]))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    print('Environment format validated; no secret values displayed.')
