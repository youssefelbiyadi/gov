#!/usr/bin/env bash
# Restore vdb_state.json from a prior attempt of this job within the current
# pipeline. Pipeline-scoped — never crosses pipeline boundaries, so retrying
# an old job after the branch has moved forward will not pick up a newer
# pipeline's artifact.
#
# Authenticates via CI_JOB_TOKEN — no PAT required.

set -euo pipefail

STATE_FILE="vdb_state.json"

if [ -f "$STATE_FILE" ]; then
  echo "[restore-state] $STATE_FILE already present — skipping fetch"
  exit 0
fi

echo "[restore-state] Searching pipeline=$CI_PIPELINE_ID for prior $CI_JOB_NAME with artifacts"

JOBS_JSON=$(curl --fail --silent --show-error \
  --header "JOB-TOKEN: ${CI_JOB_TOKEN}" \
  "${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/pipelines/${CI_PIPELINE_ID}/jobs?per_page=100")

JOB_ID=$(echo "$JOBS_JSON" | python3 -c '
import json, os, sys

jobs = json.load(sys.stdin)
name = os.environ["CI_JOB_NAME"]
current_id = os.environ["CI_JOB_ID"]

candidates = [
    j for j in jobs
    if j["name"] == name
    and str(j["id"]) != current_id
    and j.get("artifacts_file")
]
candidates.sort(key=lambda j: j.get("finished_at") or "", reverse=True)
print(candidates[0]["id"] if candidates else "")
')

if [ -z "$JOB_ID" ]; then
  echo "[restore-state] No prior $CI_JOB_NAME attempt in this pipeline — starting fresh"
  exit 0
fi

echo "[restore-state] Found prior job_id=$JOB_ID, fetching $STATE_FILE"

HTTP_STATUS=$(curl --silent --show-error --location --output "$STATE_FILE" \
  --write-out "%{http_code}" \
  --header "JOB-TOKEN: ${CI_JOB_TOKEN}" \
  "${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/jobs/${JOB_ID}/artifacts/${STATE_FILE}")

if [ "$HTTP_STATUS" = "200" ]; then
  echo "[restore-state] Restored $STATE_FILE ($(wc -c < "$STATE_FILE") bytes)"
else
  rm -f "$STATE_FILE"
  echo "[restore-state] Unexpected HTTP $HTTP_STATUS fetching artifact — starting fresh" >&2
fi
