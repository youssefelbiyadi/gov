.test_base:
  before_script:
    - source venv/bin/activate
    - |
      # If a previous attempt of this job left a vdb_state.json artifact,
      # restore it before tests run. GitLab job retry doesn't inherit
      # artifacts from the previous attempt by default.
      if [ ! -f vdb_state.json ]; then
        echo "Looking for vdb_state.json from previous attempts..."
        curl --fail --silent --show-error --location \
          --header "JOB-TOKEN: $CI_JOB_TOKEN" \
          "${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/jobs/artifacts/${CI_COMMIT_REF_NAME}/raw/vdb_state.json?job=${CI_JOB_NAME}" \
          -o vdb_state.json || echo "No prior artifact found, starting fresh"
      fi
    - test -f .env && set -a && . ./.env && set +a || true
