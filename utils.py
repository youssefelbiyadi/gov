#!/usr/bin/env bash
# Restore vdb_state.json from the latest artifact of the current job on
# the current ref. Used by every test stage so a retried job inherits the
# state its previous attempt persisted — GitLab's "retry job" doesn't carry
# artifacts across attempts by default.
#
# Silent no-op when:
#   - vdb_state.json already exists (e.g. needs: chain provided it)
#   - no previous artifact exists on this ref (first-ever run)
#
# Authenticates via CI_JOB_TOKEN — no PAT required.

set -euo pipefail

STATE_FILE="vdb_state.json"

if [ -f "$STATE_FILE" ]; then
  echo "[restore-state] $STATE_FILE already present — skipping fetch"
  exit 0
fi

URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/jobs/artifacts/${CI_COMMIT_REF_NAME}/raw/${STATE_FILE}?job=${CI_JOB_NAME}"

echo "[restore-state] Fetching previous $STATE_FILE for job=$CI_JOB_NAME ref=$CI_COMMIT_REF_NAME"

HTTP_STATUS=$(curl --silent --show-error --location --output "$STATE_FILE" \
  --write-out "%{http_code}" \
  --header "JOB-TOKEN: ${CI_JOB_TOKEN}" \
  "$URL")

case "$HTTP_STATUS" in
  200)
    echo "[restore-state] Restored $STATE_FILE ($(wc -c < "$STATE_FILE") bytes)"
    ;;
  404)
    rm -f "$STATE_FILE"
    echo "[restore-state] No prior artifact — starting fresh"
    ;;
  *)
    rm -f "$STATE_FILE"
    echo "[restore-state] Unexpected HTTP $HTTP_STATUS — starting fresh" >&2
    ;;
esac



.test_base:
  resource_group: delphix-e2e
  image: ${PYTHON_IMAGE}
  before_script:
    - source venv/bin/activate
    - ./scripts/restore_vdb_state.sh
    - test -f .env && set -a && . ./.env && set +a || true
  variables:
    KEEP_VDB_AFTER_TEST: "1"
  artifacts:
    when: always
    paths:
      - reports/
      - vdb_state.json
    expire_in: 7 days
