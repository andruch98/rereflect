#!/bin/bash
set -euo pipefail
umask 077
bundle="$(cd -- "$(dirname -- "$0")" && pwd -P)"
preview_root="$(cd -- "${1:-$PWD}" && pwd -P)"
command -v python3 >/dev/null || { echo 'Python 3 is required.'; exit 1; }
command -v docker >/dev/null || { echo 'Start Docker Desktop and retry.'; exit 1; }
if [ -n "${DOCKER_HOST:-}" ]; then
  case "$DOCKER_HOST" in unix://*) ;; *) echo 'Use a local Docker Desktop context; nothing changed.'; exit 1 ;; esac
fi
preview_context="$(docker context show)"
preview_endpoint="$(docker context inspect "$preview_context" --format '{{.Endpoints.docker.Host}}')"
case "$preview_endpoint" in unix://*) ;; *) echo 'Use a local Docker Desktop context; nothing changed.'; exit 1 ;; esac
docker info >/dev/null
docker compose version >/dev/null
# Refuse unexpected containers in this project, rather than changing other services.
preview_containers="$(docker ps -aq --filter label=com.docker.compose.project=boomsay-dashboard-preview-local)"
while IFS= read -r preview_container; do
  [ -n "$preview_container" ] || continue
  preview_dir="$(docker inspect "$preview_container" --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}')"
  preview_service="$(docker inspect "$preview_container" --format '{{index .Config.Labels "com.docker.compose.service"}}')"
  if [ "$preview_dir" != "$preview_root" ]; then
    echo 'This preview project belongs to a different folder. Nothing changed.'; exit 1
  fi
  case "$preview_service" in postgres|redis|api|web|gateway) ;; *) echo 'An unexpected service exists in this preview project. Nothing changed.'; exit 1 ;; esac
done <<< "$preview_containers"
python3 "$bundle/setup-openai.py" "$preview_root"
cd -- "$preview_root"
bash start-local.sh
python3 "$bundle/verify-openai.py" "$preview_root"
echo 'Ask Genius is configured for OpenAI gpt-4.1-mini. Open http://127.0.0.1:53004/ask-genius.'
echo 'No model request was made by this installer. Submitting a question makes a paid API request.'
echo 'OpenAI key validity, connectivity and answer quality have not yet been verified.'
