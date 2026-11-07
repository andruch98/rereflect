#!/usr/bin/env python3
"""Project-scoped Compose wrapper; stdin remains available for pg_restore etc."""
import os
import runpy
import sys

from compose_runtime import ROOT, compose_command, docker_env


if __name__ == '__main__':
    validator = runpy.run_path(str(ROOT/'validate-env.py'))
    try:
        validator['validate'](validator['read_env'](os.environ.get('BOOMSAY_ENV_FILE', '/etc/boomsay/boomsay.env')))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
    command = compose_command()+sys.argv[1:]
    os.execvpe(command[0], command, docker_env())
