#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/common.sh"

write_stage services
battery_compose down --remove-orphans
printf '%s\n' 'Services stopped. The battery-growth volumes and site data were preserved.'
