#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/common.sh"

if [[ "${1:-}" != "--yes" || $# -ne 1 ]]; then
  printf '%s\n' 'Reset deletes the battery-growth database, site files, and logs. Re-run with --yes to confirm.' >&2
  exit 2
fi

write_stage environment
assert_command docker
assert_volume_ownership

write_stage services
battery_compose down --volumes --remove-orphans
printf '%s\n' 'Removed only the validated battery-growth containers, network, and named volumes.'
