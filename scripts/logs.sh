#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/common.sh"

tail_count="${1:-200}"
if [[ ! "$tail_count" =~ ^[0-9]+$ ]] || (( tail_count < 1 || tail_count > 5000 )); then
  printf 'Usage: %s [tail-lines:1-5000]\n' "$0" >&2
  exit 2
fi

redact_logs() {
  local db_password admin_password
  db_password="$(get_env_value DB_PASSWORD)"
  admin_password="$(get_env_value ADMIN_PASSWORD)"
  sed \
    -e "s#${db_password//\#/\\#}#[REDACTED]#g" \
    -e "s#${admin_password//\#/\\#}#[REDACTED]#g" \
    -E -e 's/(api[_-]?key|authorization)(["'"'"'=: ]+)[^[:space:]]+/\1\2[REDACTED]/Ig'
}

write_stage services
battery_compose ps 2>&1 | redact_logs
write_stage health
docker ps --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" --format 'table {{.Names}}\t{{.Status}}' 2>&1 | redact_logs
write_stage logs
battery_compose logs --no-color --tail "$tail_count" 2>&1 | redact_logs
