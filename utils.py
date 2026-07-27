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


if [ -f "$STATE_FILE" ]; then
  log "$STATE_FILE already present — skipping fetch"
  dump_state "already present"
  exit 0
fi

# ... download logic writes $STATE_FILE ...
log "restored $STATE_FILE from job $JOB_ID (attempt of this pipeline)"
dump_state "fetched from GitLab"


