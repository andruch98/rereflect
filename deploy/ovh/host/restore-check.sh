#!/usr/bin/env bash
# Check a trusted decrypted dump in a new database; never replace application DB.
set -euo pipefail
umask 077
fail() { printf '%s\n' "$*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail 'Run with sudo on the VPS.'
[[ $# -eq 1 && -f $1 && ! -L $1 ]] || fail 'Usage: restore-check.sh /protected/path/database.dump'
dump=$1
[[ $(stat -c %u "$dump") == 0 && $(stat -c %a "$dump") == 600 ]] || fail 'Use a root-owned mode600 dump from a trusted backup.'
app=/opt/boomsay/current
compose=(env BOOMSAY_ENV_FILE=/etc/boomsay/boomsay.env python3 "$app/deploy/ovh/compose.py")
database="boomsay_restorecheck_$(cat /proc/sys/kernel/random/uuid | tr -d '-')"
"${compose[@]}" exec -T postgres pg_restore --list <"$dump" >/dev/null
"${compose[@]}" exec -T postgres createdb --username=boomsay --template=template0 "$database"
printf 'Isolated verification database: %s\n' "$database"
printf '%s\n' 'The verification database is retained on success or failure; the application database is untouched.'
"${compose[@]}" exec -T postgres pg_restore --username=boomsay --dbname="$database" --no-owner --no-acl --exit-on-error <"$dump"
"${compose[@]}" exec -T postgres psql --username=boomsay --dbname="$database" --no-psqlrc --set=ON_ERROR_STOP=1 --command="SELECT count(*) AS restored_user_tables FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';"
checks=$(mktemp -d /tmp/boomsay-restore-counts.XXXXXXXX)
trap 'rm -rf -- "$checks"' EXIT
query="SELECT 'organizations', count(*) FROM organizations UNION ALL SELECT 'users', count(*) FROM users UNION ALL SELECT 'feedback_items', count(*) FROM feedback_items UNION ALL SELECT 'maintenance_occurrences', count(*) FROM maintenance_occurrences UNION ALL SELECT 'survey_instances', count(*) FROM survey_instances UNION ALL SELECT 'survey_invitations', count(*) FROM survey_invitations UNION ALL SELECT 'conversations', count(*) FROM conversations UNION ALL SELECT 'conversation_messages', count(*) FROM conversation_messages ORDER BY 1;"
"${compose[@]}" exec -T postgres psql --username=boomsay --dbname=boomsay --no-psqlrc --set=ON_ERROR_STOP=1 --tuples-only --no-align --command="$query" >"$checks/current.txt"
"${compose[@]}" exec -T postgres psql --username=boomsay --dbname="$database" --no-psqlrc --set=ON_ERROR_STOP=1 --tuples-only --no-align --command="$query" >"$checks/restored.txt"
printf '%s\n' 'Restored aggregate table counts:'
cat "$checks/restored.txt"
if diff -u "$checks/current.txt" "$checks/restored.txt"; then
  printf '%s\n' 'Current and restored table counts agree. This does not independently prove record contents.'
else
  result=$?
  [[ $result -eq 1 ]] || exit "$result"
  printf '%s\n' 'Counts differ. The live database may have changed since the backup; investigate with writes paused before accepting recovery.'
  exit 1
fi
printf '%s\n' 'Restore completed. Review known survey answers/chats before accepting recovery. This script does not drop the verification database.'
