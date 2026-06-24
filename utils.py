#!/usr/bin/env bash
# Restore vdb_state.json from a prior attempt of this job within the current
# pipeline, so a retried job inherits the state its previous attempt persisted.
#
# Pipeline-scoped: never crosses pipeline boundaries — retrying an old job
# after the branch has moved forward will not pick up a newer pipeline's
# artifact.
#
# Authenticates via GITLAB_PAT (PRIVATE-TOKEN). The token needs `read_api`.

set -euo pipefail

readonly STATE_FILE="vdb_state.json"
readonly LOG_PREFIX="[restore-state]"

log()  { echo "${LOG_PREFIX} $*"; }
warn() { echo "${LOG_PREFIX} $*" >&2; }

# ─── Preconditions ─────────────────────────────────────────────────────────

if [ -f "$STATE_FILE" ]; then
 log "$STATE_FILE already present — skipping fetch"
 exit 0
fi

if [ -z "${GITLAB_PAT:-}" ]; then
 warn "GITLAB_PAT not set — cannot fetch prior artifacts, starting fresh"
 exit 0
fi

# ─── Step 1: list jobs in the current pipeline ─────────────────────────────

readonly JOBS_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/pipelines/${CI_PIPELINE_ID}/jobs?per_page=100"

log "Pipeline=${CI_PIPELINE_ID} job=${CI_JOB_NAME}"
log "GET ${JOBS_URL}"

JOBS_BODY=$(mktemp)
trap 'rm -f "$JOBS_BODY"' EXIT

JOBS_STATUS=$(curl --silent --show-error --output "$JOBS_BODY" \
 --write-out "%{http_code}" \
 --header "PRIVATE-TOKEN: ${GITLAB_PAT}" \
 "$JOBS_URL")

if [ "$JOBS_STATUS" != "200" ]; then
 warn "Could not list pipeline jobs (HTTP ${JOBS_STATUS}) — starting fresh"
 warn "Response: $(head -c 300 "$JOBS_BODY")"
 exit 0
fi

# ─── Step 2: find latest prior attempt of this job with an artifact ────────

JOB_ID=$(python3 - "$JOBS_BODY" <<'PY'
import json, os, sys

with open(sys.argv[1]) as f:
   jobs = json.load(f)

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
PY
)

if [ -z "$JOB_ID" ]; then
 log "No prior ${CI_JOB_NAME} attempt with an artifact in this pipeline — starting fresh"
 exit 0
fi

# ─── Step 3: download the artifact from that prior attempt ─────────────────

readonly ARTIFACT_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/jobs/${JOB_ID}/artifacts/${STATE_FILE}"

log "Found prior job_id=${JOB_ID}"
log "GET ${ARTIFACT_URL}"

ARTIFACT_STATUS=$(curl --silent --show-error --location --output "$STATE_FILE" \
 --write-out "%{http_code}" \
 --header "PRIVATE-TOKEN: ${GITLAB_PAT}" \
 "$ARTIFACT_URL")

if [ "$ARTIFACT_STATUS" = "200" ]; then
 log "Restored ${STATE_FILE} ($(wc -c < "$STATE_FILE") bytes)"
else
 rm -f "$STATE_FILE"
 warn "Could not fetch artifact (HTTP ${ARTIFACT_STATUS}) — starting fresh"
fi
