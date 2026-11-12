#!/usr/bin/env bash
set -euo pipefail
SKILL_SCRIPTS="$(dirname "$(readlink -f "$0")")"
exec node "${SKILL_SCRIPTS}/enrich.js" "$@"
