# Explicit seed wins over artifact restoration.
if [ -n "${VDB_STATE_JSON:-}" ]; then
  log "VDB_STATE_JSON provided — using seeded state, skipping artifact restore"
  [ -f "$STATE_FILE" ] && dump_state "seeded"
  exit 0
fi


.test_base:
  before_script:
    - source venv/bin/activate
    - |
      if [ -n "${VDB_STATE_JSON:-}" ]; then
        echo "[seed-state] writing vdb_state.json from VDB_STATE_JSON var"
        printf '%s' "$VDB_STATE_JSON" > vdb_state.json
        if command -v jq >/dev/null 2>&1; then
          jq . vdb_state.json || { echo "[seed-state] VDB_STATE_JSON is not valid JSON" >&2; exit 1; }
        fi
      fi
    - bash scripts/restore_vdb_state.sh          # ← seed block goes ABOVE this
    - test -f .env && set -a && . ./.env && set +a || true


#!/usr/bin/env bash
# Usage: ./scripts/derive_start.sh [vdb_state.json]
set -euo pipefail
STATE_FILE="${1:-vdb_state.json}"
[ -f "$STATE_FILE" ] || { echo "no $STATE_FILE" >&2; exit 1; }
if command -v jq >/dev/null 2>&1; then
  compact=$(jq -c . "$STATE_FILE")
else
  compact=$(tr -d '\n' < "$STATE_FILE")
fi
echo "VDB_STATE_JSON=${compact}"


