#!/usr/bin/env python3
"""Observe real VPS/container memory without reading env values or resident data.

Run idle and while a documented, representative application workload is active.
This does not generate that workload or prove AI accuracy/deployment correctness.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time

from compose_runtime import compose_command, docker_env

SERVICES = ('postgres', 'redis', 'backend', 'worker', 'frontend', 'caddy')
MIB = 1024 * 1024


def run(args, timeout=30):
    result = subprocess.run(args, env=docker_env(), capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        # Docker diagnostics can include private environment values. Keep this
        # observer's record limited to command category and exit status.
        raise RuntimeError(f'{args[0]} command failed with exit status{result.returncode}; inspect private host logs')
    return result.stdout


def meminfo():
    rows = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        rows[key] = int(value.strip().split()[0]) * 1024
    return {key: rows[key] for key in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree')}


def memory_bytes(value):
    number, unit = value.strip().split(' ', 1) if ' ' in value.strip() else ('', '')
    if not number:
        import re
        match = re.fullmatch(r'([0-9.]+)([A-Za-z]+)', value.strip())
        if not match:
            raise ValueError('Unrecognized docker stats memory format')
        number, unit = match.groups()
    factors = {'B': 1, 'KiB': 1024, 'MiB': MIB, 'GiB': 1024*MIB,
               'kB': 1000, 'MB': 1000**2, 'GB': 1000**3}
    return round(float(number) * factors[unit])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--phase', choices=('idle', 'active'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 30 <= args.seconds <= 1800:
        parser.error('Observation window must be between30 and1800 seconds')
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parent
    envfile = os.environ.get('BOOMSAY_ENV_FILE', '/etc/boomsay/boomsay.env')
    run(['python3', str(root/'validate-env.py'), envfile])
    docker = ['docker', '--host=unix:///var/run/docker.sock']
    compose = compose_command()
    ids = {service: run(compose+['ps', '-q', service]).strip() for service in SERVICES}
    if any(not value or '\n' in value for value in ids.values()):
        raise RuntimeError('Expected exactly one running container for every application component')
    samples = []
    deadline = time.monotonic() + args.seconds
    while True:
        sample = {'time': datetime.now(timezone.utc).isoformat(), 'host': meminfo(), 'containers': {}}
        for service, container in ids.items():
            fields = run(docker+['inspect', '--format',
                '{{.State.Status}}|{{.State.OOMKilled}}|{{.RestartCount}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}', container]).strip().split('|')
            stats = json.loads(run(docker+['stats', '--no-stream', '--format', '{{json .}}', container]))
            sample['containers'][service] = {
                'status': fields[0], 'oom_killed': fields[1] == 'true',
                'restart_count': int(fields[2]), 'health': fields[3],
                'memory_bytes': memory_bytes(stats['MemUsage'].split('/')[0]),
                'cpu_percent': stats['CPUPerc'], 'pids': stats['PIDs'],
            }
        samples.append(sample)
        with (args.output/'samples.jsonl').open('a') as stream:
            stream.write(json.dumps(sample)+'\n')
        if time.monotonic() >= deadline:
            break
        time.sleep(min(5, max(0, deadline-time.monotonic())))
    peaks = {}
    for service, container in ids.items():
        # cgroup v2 peak/events include between-sample peaks within this cgroup.
        raw = run(docker+['exec', container, 'sh', '-c',
            'if [ -r /sys/fs/cgroup/memory.peak ] && [ -r /sys/fs/cgroup/memory.events ]; then cat /sys/fs/cgroup/memory.peak; cat /sys/fs/cgroup/memory.events; else echo unavailable; fi'])
        lines = raw.splitlines()
        peaks[service] = {'memory_peak_bytes': int(lines[0]) if lines and lines[0].isdigit() else None,
                          'events': dict(line.split() for line in lines[1:] if len(line.split()) == 2)}
    total = samples[0]['host']['MemTotal']
    checks = {
        'host_is_approximately_4gb': 3400*MIB <= total <= 4300*MIB,
        'at_least_768mib_available_throughout': min(s['host']['MemAvailable'] for s in samples) >= 768*MIB,
        'swap_growth_under_64mib': max(s['host']['SwapTotal']-s['host']['SwapFree'] for s in samples)
            - (samples[0]['host']['SwapTotal']-samples[0]['host']['SwapFree']) < 64*MIB,
        'swap_used_under_64mib_throughout': max(s['host']['SwapTotal']-s['host']['SwapFree'] for s in samples) < 64*MIB,
        'all_components_running_and_healthy': all(c['status'] == 'running' and c['health'] == 'healthy'
            for s in samples for c in s['containers'].values()),
        'no_restart_or_oom': all(not c['oom_killed'] and c['restart_count'] == 0
            for s in samples for c in s['containers'].values()),
        'cgroup_peak_evidence_available': all(p['memory_peak_bytes'] is not None for p in peaks.values()),
        'no_cgroup_oom_events': all(int(p['events'].get('oom', 0)) == 0 and int(p['events'].get('oom_kill', 0)) == 0
            for p in peaks.values()),
    }
    report = {'phase': args.phase, 'window_requested_seconds': args.seconds, 'samples': len(samples),
              'checks': checks, 'resource_window_passed': all(checks.values()),
              'minimum_host_available_mib': round(min(s['host']['MemAvailable'] for s in samples)/MIB, 1),
              'maximum_sampled_container_sum_mib': round(max(sum(c['memory_bytes'] for c in s['containers'].values()) for s in samples)/MIB, 1),
              'container_peaks': peaks,
              'full_application_fit_verified': False,
              'limitations': ['The phase label does not prove a workload occurred. Retain separate executed workflow evidence.',
                             'Require both idle and representative active windows plus deployment/workflow/backup-restore results.',
                             'No resident data, credentials, model requests, model usage or costs were captured.',
                             'A passing observation window alone is not a full-app4GB sizing verdict.']}
    (args.output/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return 0 if report['resource_window_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
