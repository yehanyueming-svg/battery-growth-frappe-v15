#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/common.sh"

skip_build=false
if [[ "${1:-}" == "--skip-build" ]]; then
  skip_build=true
elif [[ $# -gt 0 ]]; then
  printf 'Usage: %s [--skip-build]\n' "$0" >&2
  exit 2
fi

write_stage prerequisites
assert_command git
assert_command docker
server_version="$(docker version --format '{{.Server.Version}}' 2>/dev/null || true)"
if [[ -z "$server_version" ]]; then
  printf '%s\n' 'Docker Engine is not running.' >&2
  exit 1
fi
server_major="${server_version%%.*}"
if (( server_major < 23 )); then
  printf 'Docker Engine 23 or newer is required; found %s.\n' "$server_version" >&2
  exit 1
fi
docker compose version >/dev/null
available_kb="$(df -Pk "$REPOSITORY_ROOT" | awk 'NR == 2 {print $4}')"
if (( available_kb < 10485760 )); then
  printf '%s\n' 'At least 10 GiB free disk space is required.' >&2
  exit 1
fi
port="$(get_env_value HTTP_PUBLISH_PORT 8080)"
if (echo >/dev/tcp/127.0.0.1/"$port") 2>/dev/null && ! project_frontend_running; then
  printf 'Port %s is already in use. Change HTTP_PUBLISH_PORT in .env.\n' "$port" >&2
  exit 1
fi

write_stage submodule
submodule="$REPOSITORY_ROOT/deploy/frappe_docker"
if [[ ! -f "$submodule/compose.yaml" ]]; then
  git -C "$REPOSITORY_ROOT" submodule update --init --depth 1 -- deploy/frappe_docker
fi
expected_upstream="$(get_env_value FRAPPE_DOCKER_REVISION 380b9d069ab949754fe78331af647b673984dc04)"
actual_upstream="$(git -C "$submodule" rev-parse HEAD)"
if [[ "$actual_upstream" != "$expected_upstream" ]]; then
  printf 'frappe_docker revision mismatch: expected %s, found %s.\n' "$expected_upstream" "$actual_upstream" >&2
  exit 1
fi

write_stage environment
initialize_environment
site_name="$(get_env_value SITE_NAME battery.localhost)"
port="$(get_env_value HTTP_PUBLISH_PORT 8080)"

write_stage build
revision="$(git -C "$REPOSITORY_ROOT" rev-parse HEAD)"
if [[ "$skip_build" == false ]]; then
  if [[ -n "$(git -C "$REPOSITORY_ROOT" status --porcelain --untracked-files=no)" ]]; then
    printf '%s\n' 'Tracked files are dirty. Commit them before building the remote-source image.' >&2
    exit 1
  fi
  app_ref="${BATTERY_GROWTH_APP_REF:-}"
  if [[ -n "$app_ref" ]]; then
    if [[ ! "$app_ref" =~ ^[A-Za-z0-9._/-]+$ || "$app_ref" != "$revision" ]]; then
      printf '%s\n' 'BATTERY_GROWTH_APP_REF must be the current full commit revision for an exact CI build.' >&2
      exit 1
    fi
  else
    upstream_revision="$(git -C "$REPOSITORY_ROOT" rev-parse '@{upstream}' 2>/dev/null || true)"
    if [[ "$upstream_revision" != "$revision" ]]; then
      printf '%s\n' 'HEAD must be pushed to its tracked branch before building the remote-source image.' >&2
      exit 1
    fi
  fi
  frappe_version="$(get_env_value FRAPPE_VERSION v15.120.0)"
  image_reference="$(get_image_reference)"
  builder_image_reference="${image_reference}-build"
  apps_json="$REPOSITORY_ROOT/deploy/apps.json"
  temporary_apps_json=""
  if [[ -n "$app_ref" ]]; then
    temporary_apps_json="$(mktemp)"
    trap 'rm -f "$temporary_apps_json"' EXIT
    sed -E "s#(\"branch\"[[:space:]]*:[[:space:]]*\")[^\"]*(\")#\1$app_ref\2#" \
      "$apps_json" >"$temporary_apps_json"
    apps_json="$temporary_apps_json"
  fi
  docker build \
    --build-arg "FRAPPE_BRANCH=$frappe_version" \
    --build-arg "CACHE_BUST=$revision" \
    --secret "id=apps_json,src=$apps_json" \
    --label "org.opencontainers.image.revision=$revision" \
    --label 'org.opencontainers.image.source=https://github.com/yehanyueming-svg/battery-growth-frappe-v15' \
    --tag "$builder_image_reference" \
    --file "$submodule/images/layered/Containerfile" \
    "$submodule"
  docker build \
    --build-arg "SOURCE_IMAGE=$builder_image_reference" \
    --label "org.opencontainers.image.revision=$revision" \
    --label 'org.opencontainers.image.source=https://github.com/yehanyueming-svg/battery-growth-frappe-v15' \
    --tag "$image_reference" \
    --file "$REPOSITORY_ROOT/deploy/runtime.Containerfile" \
    "$REPOSITORY_ROOT/deploy"
else
  printf '%s\n' 'Skipping image build by request.'
fi

write_stage dependencies
battery_compose up -d db redis-cache redis-queue
battery_compose up --no-deps --exit-code-from configurator configurator

write_stage site-init
battery_compose up --no-deps --exit-code-from site-init site-init

write_stage services
battery_compose up -d --no-deps backend websocket queue-short queue-long scheduler frontend

write_stage health
deadline=$((SECONDS + 180))
until curl --fail --silent --show-error --header "Host: $site_name" "http://127.0.0.1:$port/api/method/ping" | grep -q pong; do
  if (( SECONDS >= deadline )); then
    printf '%s\n' 'Health check timed out. Run ./scripts/logs.sh for redacted diagnostics.' >&2
    exit 1
  fi
  sleep 3
done

printf 'Battery Growth is ready at http://%s:%s\n' "$site_name" "$port"
printf '%s\n' 'WARNING: local demo login only: Administrator / admin.'
printf 'Workspace: http://%s:%s/app/battery-growth\n' "$site_name" "$port"
printf 'Subscriptions: http://%s:%s/app/service-subscription\n' "$site_name" "$port"
printf 'Report: http://%s:%s/app/query-report/User%%20Growth%%20Analysis\n' "$site_name" "$port"
printf 'Dashboard: http://%s:%s/app/battery-growth-dashboard\n' "$site_name" "$port"
printf 'AI settings: http://%s:%s/app/growth-ai-settings\n' "$site_name" "$port"
