#!/usr/bin/env bash
# Database/configuration recovery archive. The age private key stays off-server.
set -euo pipefail
umask 077
fail() { printf '%s\n' "$*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail 'Run with sudo on the VPS.'
app=/opt/boomsay/current
env_file=/etc/boomsay/boomsay.env
recipient_file=/etc/boomsay/backup-recipient.txt
backup_dir=/var/backups/boomsay
[[ -f $env_file && ! -L $env_file && -f $recipient_file && ! -L $recipient_file ]] || fail 'Missing protected environment or public backup recipient.'
[[ $(stat -c %u "$env_file") == 0 && $(stat -c %a "$env_file") == 600 ]] || fail 'Environment must be root-owned mode600.'
[[ $(stat -c %u "$recipient_file") == 0 && $(stat -c %a "$recipient_file") == 600 ]] || fail 'Public recipient file must be root-owned mode600.'
recipient=$(cat "$recipient_file")
[[ $recipient =~ ^age1[0-9a-z]+$ ]] || fail 'Expected one age public recipient; never place a private identity on this server.'
command -v age >/dev/null || fail 'Install age from Ubuntu packages.'
[[ -f $app/deploy/ovh/compose.yml ]] || fail 'Current release is missing.'
if [[ ${1:-} == install-timer && $# -eq 1 ]]; then
  # Do not enable a schedule until one real dump/encryption has succeeded.
  bash "$0"
  cat >/etc/systemd/system/boomsay-backup.service <<'EOF'
[Unit]
Description=BoomSay encrypted database and configuration backup
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
User=root
UMask=0077
ExecStart=/usr/bin/bash /opt/boomsay/current/deploy/ovh/host/backup.sh
TimeoutStartSec=20min
Nice=10
IOSchedulingClass=idle
StandardOutput=journal
StandardError=journal
EOF
  cat >/etc/systemd/system/boomsay-backup.timer <<'EOF'
[Unit]
Description=Daily BoomSay encrypted backup

[Timer]
OnCalendar=*-*-* 04:15:00 UTC
RandomizedDelaySec=15m
Persistent=true
Unit=boomsay-backup.service

[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload
  systemctl enable --now boomsay-backup.timer
  printf '%s\n' 'Daily timer enabled. Check journalctl -u boomsay-backup.service for failures; no email alert is configured.'
  exit
fi
[[ $# -eq 0 ]] || fail 'Usage: backup.sh [install-timer]'
install -d -m 0700 "$backup_dir"
exec 9>"$backup_dir/.backup.lock"
flock -n 9 || fail 'A backup is already running.'
stage=$(mktemp -d "$backup_dir/.staging.XXXXXXXX")
temporary=
cleanup() { rm -rf -- "$stage"; [[ -z $temporary ]] || rm -f -- "$temporary"; }
trap cleanup EXIT
compose=(env BOOMSAY_ENV_FILE="$env_file" python3 "$app/deploy/ovh/compose.py")
"${compose[@]}" exec -T postgres pg_dump --username=boomsay --dbname=boomsay --format=custom --no-owner --no-acl >"$stage/database.dump"
[[ -s $stage/database.dump ]] || fail 'Database dump is empty.'
# Archive listing checks format only; a separate restore drill must still run.
"${compose[@]}" exec -T postgres pg_restore --list <"$stage/database.dump" >/dev/null
install -m 0600 "$env_file" "$stage/boomsay.env"
git -C "$app" rev-parse HEAD >"$stage/source-commit.txt"
date -u +%FT%TZ >"$stage/created-at.txt"
cat >"$stage/scope.txt" <<'EOF'
Consistent PostgreSQL dump plus environment/encryption keys and source commit.
Redis queues, worker scheduler files, and TLS certificate volumes are excluded.
Restore application records and reconcile queued jobs before allowing deliveries.
EOF
name="boomsay-$(date -u +%Y%m%dT%H%M%S)-$RANDOM.tar.age"
temporary="$backup_dir/.$name.partial"
tar -C "$stage" -cf - . | age --recipient "$recipient" --output "$temporary"
[[ -s $temporary ]] || fail 'Encrypted archive is empty.'
mv -- "$temporary" "$backup_dir/$name"
temporary=
(cd "$backup_dir" && sha256sum -- "$name") >"$backup_dir/$name.sha256"
# Prune only this script's older archives after a new valid dump was encrypted.
python3 - "$backup_dir" <<'PY'
from pathlib import Path
import re, sys
root = Path(sys.argv[1])
files = sorted(p for p in root.iterdir() if p.is_file() and not p.is_symlink() and re.fullmatch(r'boomsay-\d{8}T\d{6}-\d+\.tar\.age', p.name))
for path in files[:-7]:
    path.unlink()
    path.with_name(path.name + '.sha256').unlink(missing_ok=True)
PY
printf 'Encrypted backup saved: %s\n' "$backup_dir/$name"
printf '%s\n' 'This archive is still on the VPS. Off-server copy and actual restore remain separate checks.'
