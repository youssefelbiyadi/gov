#!/usr/bin/env bash
#
# Restore vdb_state.json from the most recent PRIOR ATTEMPT of THIS job in the
# current pipeline. Pipeline-scoped: never crosses pipeline boundaries.
#
# `needs: artifacts: true` drops the UPSTREAM stage's vdb_state.json on disk
# BEFORE this script runs. That copy is a SUBSET (master_create's state has the
# subscription id but no refresh demand id). A prior attempt of THIS job is
# always a SUPERSET of that baseline, so when one exists it must overwrite it.

set -euo pipefail

readonly STATE_FILE="vdb_state.json"
readonly LOG_PREFIX="[restore-state]"

log()  { echo "${LOG_PREFIX} $*"; }
warn() { echo "${LOG_PREFIX} $*" >&2; }

dump_state() {
  log "--- vdb_state.json contents ($1) ---"
  if command -v jq >/dev/null 2>&1; then
    jq . "$STATE_FILE" || cat "$STATE_FILE"
  else
    warn "jq not on runner — dumping raw JSON"
    cat "$STATE_FILE"
  fi
  log "--- end vdb_state.json ---"
}

# ── Preconditions ──
# NO "file already present -> skip" check: the needs artifact makes the file
# present with STALE content, so skipping here is exactly the bug.

if [ -z "${GITLAB_PAT:-}" ]; then
  warn "GITLAB_PAT not set — keeping needs baseline if any, fresh otherwise"
  [ -f "$STATE_FILE" ] && dump_state "needs baseline (no PAT)"
  exit 0
fi

JOBS_JSON=$(mktemp)
trap 'rm -f "$JOBS_JSON" "${STATE_FILE}.prior"' EXIT

# ── Step 1: list all jobs (including retried) in the current pipeline ──
readonly JOBS_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/pipelines/${CI_PIPELINE_ID}/jobs?per_page=100&include_retried=true"
log "GET ${JOBS_URL}"

JOBS_STATUS=$(curl --silent --show-error --location --output "$JOBS_JSON" \
  --write-out "%{http_code}" \
  --header "PRIVATE-TOKEN: ${GITLAB_PAT}" \
  "$JOBS_URL") || JOBS_STATUS="000"

if [ "$JOBS_STATUS" != "200" ]; then
  warn "Could not list pipeline jobs (HTTP $JOBS_STATUS) — keeping needs baseline"
  [ -f "$STATE_FILE" ] && dump_state "needs baseline (jobs list failed)"
  exit 0
fi

# ── Step 2: most recent PRIOR attempt of THIS job that has an artifact ──
JOB_ID=$(python3 - "$JOBS_JSON" <<'PY'
import json, os, sys
with open(sys.argv[1]) as f:
    jobs = json.load(f)
current_id = int(os.environ["CI_JOB_ID"])
name = os.environ["CI_JOB_NAME"]
candidates = [
    j for j in jobs
    if j.get("name") == name
    and j.get("id") != current_id
    and j.get("artifacts_file")
]
candidates.sort(key=lambda j: j.get("finished_at") or "", reverse=True)
print(candidates[0]["id"] if candidates else "")
PY
)

if [ -z "$JOB_ID" ]; then
  log "No prior ${CI_JOB_NAME} attempt with an artifact — keeping needs baseline"
  [ -f "$STATE_FILE" ] && dump_state "needs baseline (no prior attempt)"
  exit 0
fi

# ── Step 3: download it; SUPERSEDES the needs baseline via atomic mv ──
readonly ARTIFACT_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/jobs/${JOB_ID}/artifacts/${STATE_FILE}"
log "Found prior job_id=${JOB_ID}"
log "GET ${ARTIFACT_URL}"

ARTIFACT_STATUS=$(curl --silent --show-error --location --output "${STATE_FILE}.prior" \
  --write-out "%{http_code}" \
  --header "PRIVATE-TOKEN: ${GITLAB_PAT}" \
  "$ARTIFACT_URL") || ARTIFACT_STATUS="000"

if [ "$ARTIFACT_STATUS" = "200" ]; then
  mv "${STATE_FILE}.prior" "$STATE_FILE"
  log "Restored $STATE_FILE from prior attempt $JOB_ID (supersedes needs artifact)"
  dump_state "fetched from prior attempt"
else
  rm -f "${STATE_FILE}.prior"
  warn "Could not fetch prior artifact (HTTP $ARTIFACT_STATUS) — keeping needs baseline"
  [ -f "$STATE_FILE" ] && dump_state "needs baseline (fetch failed)"
fi
