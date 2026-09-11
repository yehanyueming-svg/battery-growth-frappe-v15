#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/common.sh"

skip_bench_tests=false
if [[ "${1:-}" == "--skip-bench-tests" ]]; then
  skip_bench_tests=true
elif [[ $# -gt 0 ]]; then
  printf 'Usage: %s [--skip-bench-tests]\n' "$0" >&2
  exit 2
fi

write_stage verification
assert_command git
assert_command docker
revision="$(git -C "$REPOSITORY_ROOT" rev-parse HEAD)"
image_reference="$(get_image_reference)"
image_revision="$(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$image_reference")"
if [[ "$image_revision" != "$revision" ]]; then
  printf 'Image revision mismatch: expected %s, found %s.\n' "$revision" "${image_revision:-missing}" >&2
  exit 1
fi

site_name="$(get_env_value SITE_NAME battery.localhost)"
frappe_version="$(get_env_value FRAPPE_VERSION v15.120.0)"
frappe_version="${frappe_version#v}"
battery_compose exec -T backend bench --site "$site_name" execute \
  battery_growth.setup.verification.assert_deployment \
  --kwargs "{'expected_frappe_version': '$frappe_version', 'expected_mock_count': 240}"

if [[ "$skip_bench_tests" == false ]]; then
  battery_compose exec -T backend bench --site "$site_name" set-config --parse allow_tests True
  bench_test_status=0
  battery_compose exec -T backend bench --site "$site_name" run-tests --app battery_growth || bench_test_status=$?
  battery_compose exec -T backend bench --site "$site_name" set-config --parse allow_tests False
  if (( bench_test_status != 0 )); then
    exit "$bench_test_status"
  fi
else
  printf '%s\n' 'Skipping Bench tests by request.'
fi

port="$(get_env_value HTTP_PUBLISH_PORT 8080)"
routes=(
  /api/method/ping
  /login
  /app/service-subscription
  /app/query-report/User%20Growth%20Analysis
  /app/battery-growth-dashboard
  /app/growth-ai-settings
)
for route in "${routes[@]}"; do
  body="$(curl --fail --location --silent --show-error \
    --header "Host: $site_name" \
    "http://127.0.0.1:$port$route")"
  if [[ "$route" == "/api/method/ping" && "$body" != *pong* ]]; then
    printf '%s\n' 'Ping route returned HTTP success without the expected pong response.' >&2
    exit 1
  fi
  printf 'OK %s\n' "$route"
done

printf 'Deployment verification passed for image revision %s.\n' "$revision"
