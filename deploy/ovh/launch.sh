#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

HERE=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ENV_FILE=${BOOMSAY_ENV_FILE:-/etc/boomsay/boomsay.env}
compose() {
  BOOMSAY_ENV_FILE="$ENV_FILE" python3 "$HERE/compose.py" "$@"
}

[[ $(uname -s) == Linux ]] || { echo 'Run this launcher on the prepared Linux VPS.' >&2; exit 1; }
command -v docker >/dev/null || { echo 'Docker must be installed on the VPS first.' >&2; exit 1; }
python3 "$HERE/validate-env.py" "$ENV_FILE"
compose config --quiet

case ${1:-status} in
  check)
    echo 'Compose configuration validated. Containers have not been started.'
    ;;
  build)
    # Sequential builds avoid several native/Next builds competing for4GB.
    # A successful build does not establish runtime memory fit.
    compose build backend
    compose build worker
    compose build frontend
    ;;
  start)
    compose up -d --wait --wait-timeout 180 postgres redis
    # No API or worker rollout until the migration succeeds. Existing services
    # are not stopped; take a backup before an upgrade (see host backup steps).
    compose run --rm --no-deps migrate
    compose run --rm --no-deps initialize
    compose up -d --wait --wait-timeout 300 backend worker frontend caddy
    echo 'Containers reported healthy. Complete TLS, login, workflow and RAM checks before declaring the deployment tested.'
    ;;
  prepare-surveys)
    # Revalidate the isolated fictional community, preserving its password.
    compose run --rm --no-deps initialize
    install -d -m 0700 /var/lib/boomsay
    links=$(mktemp /var/lib/boomsay/resident-links.XXXXXX)
    trap 'rm -f -- "${links:-}"' EXIT
    for event in move_in_completed maintenance_completed lease_month_3 lease_month_6 lease_month_9 lease_renewed move_out_completed; do
      compose exec -T backend python -m src.survey_lifecycle_demo --community-id 1 --event "$event" --test-id cloud-demo >> "$links"
    done
    chmod 0600 "$links"
    mv -- "$links" /var/lib/boomsay/resident-links.txt
    trap - EXIT
    echo 'Seven pending fictional survey links saved privately in /var/lib/boomsay/resident-links.txt. No answers submitted or emails sent.'
    ;;
  status)
    compose ps
    ;;
  stop)
    compose stop
    echo 'Containers stopped; persistent volumes retained.'
    ;;
  *)
    echo 'Usage: launch.sh {check|build|start|prepare-surveys|status|stop}' >&2
    exit 2
    ;;
esac
