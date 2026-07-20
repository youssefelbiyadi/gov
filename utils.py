  Scenario: Refreshing the client VDB from snapshot
    Given an existing client VDB
    When I refresh the client VDB
    Then the client VDB is refreshed within one hour


@scenario(FEATURE_FILE, "Refreshing the client VDB from snapshot")
def test_client_refresh(): ...


stages:
  # ...
  - client_create
  - client_refresh      # NEW
  - client_delete
  - master_delete

client_refresh:
  extends: .test_base
  stage: client_refresh
  needs:
    - "setup"
    - job: "client_create"
      optional: true
      artifacts: true
  script:
    - pytest -m client_refresh --junitxml=reports/client_refresh.xml

client_delete:
  extends: .test_base
  stage: client_delete
  needs:
    - "setup"
    - job: "client_refresh"
      optional: true
      artifacts: true
  script:
    - pytest -m client_delete --junitxml=reports/client_delete.xml

@when("I refresh the client VDB", target_fixture="client_subscription")
def _refresh_client(orchestrator_v2, client_subscription, vdb_state):
    return apply_action_idempotent(
        orchestrator_v2,
        client_subscription,
        action=REFRESH_ACTION,
        payload=None,
        vdb_state=vdb_state,
        demand_key=CLIENT_REFRESH_DEMAND_KEY,
        kind="CLIENT",
    )


@then("the client VDB is refreshed within one hour")
def _client_refreshed(orchestrator_v2, client_subscription, vdb_state):
    wait_for_demand_success(
        orchestrator_v2, vdb_state, CLIENT_REFRESH_DEMAND_KEY,
        REFRESH_TIMEOUT_S, kind="CLIENT",
    )

[tool.pytest.ini_options]
markers = [
    # ...
    "client_refresh: refresh the client VDB from the master's latest snapshot",
]
