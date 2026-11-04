#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  move_in_completed|maintenance_completed|lease_month_3|lease_month_6|lease_month_9|lease_renewed|move_out_completed) ;;
  *) echo "Choose one of the seven documented survey types." >&2; exit 2 ;;
esac
helper_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$HOME/Downloads/boomsay-dashboard-preview"
exec python3 "$helper_dir/survey-email-test.py" send --test-id "lifecycle-review-$1" --event-type "$1"
