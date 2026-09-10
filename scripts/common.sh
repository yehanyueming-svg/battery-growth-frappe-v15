#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPOSITORY_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
ENVIRONMENT_FILE="$REPOSITORY_ROOT/.env"
if [[ ! -f "$ENVIRONMENT_FILE" ]]; then
  ENVIRONMENT_FILE="$REPOSITORY_ROOT/.env.example"
fi
COMPOSE_PROJECT="battery-growth"
COMPOSE_FILES=(
  "$REPOSITORY_ROOT/deploy/frappe_docker/compose.yaml"
  "$REPOSITORY_ROOT/deploy/frappe_docker/overrides/compose.mariadb.yaml"
  "$REPOSITORY_ROOT/deploy/compose.override.yaml"
)
EXPECTED_VOLUMES=(battery-growth-db battery-growth-sites battery-growth-logs)

write_stage() {
  printf '\n[%s]\n' "$1"
}
get_env_value() {
  local name="$1"
  local default_value="${2:-}"
  local value
  value="$(awk -F= -v key="$name" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' "$ENVIRONMENT_FILE" | tr -d '\r')"
  printf '%s' "${value:-$default_value}"
}

initialize_environment() {
  local target="$REPOSITORY_ROOT/.env"
  if [[ ! -f "$target" ]]; then
    cp "$REPOSITORY_ROOT/.env.example" "$target"
    printf '%s\n' "Created .env from .env.example"
  fi
  ENVIRONMENT_FILE="$target"
}

assert_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Required command %s was not found on PATH.\n' "$1" >&2
    return 1
  }
}

battery_compose() {
  local args=(compose --project-name "$COMPOSE_PROJECT" --env-file "$ENVIRONMENT_FILE")
  local file
  for file in "${COMPOSE_FILES[@]}"; do
    args+=(--file "$file")
  done
  docker "${args[@]}" "$@" || {
    local status=$?
    printf 'docker compose failed with exit code %s. Run ./scripts/logs.sh for diagnostics.\n' "$status" >&2
    return "$status"
  }
}

get_image_reference() {
  printf '%s:%s' "$(get_env_value CUSTOM_IMAGE battery-growth)" "$(get_env_value CUSTOM_TAG v15.120.0)"
}

project_frontend_running() {
  [[ -n "$(docker ps \
    --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" \
    --filter 'label=com.docker.compose.service=frontend' \
    --format '{{.ID}}' 2>/dev/null)" ]]
}

assert_volume_ownership() {
  local volume project
  for volume in "${EXPECTED_VOLUMES[@]}"; do
    if ! docker volume inspect "$volume" >/dev/null 2>&1; then
      continue
    fi
    project="$(docker volume inspect --format '{{ index .Labels "com.docker.compose.project" }}' "$volume")"
    if [[ "$project" != "$COMPOSE_PROJECT" ]]; then
      printf "Refusing reset: volume '%s' is not owned by Compose project '%s'.\n" "$volume" "$COMPOSE_PROJECT" >&2
      return 1
    fi
  done
}
