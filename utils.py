"""E2E VDB lifecycle scenarios."""
from __future__ import annotations

import logging
import os

import pytest
from pytest_bdd import given, scenario, then, when

from e2e.constants import (
    CLIENT_SUB_STATE_KEY,
    DELETION_TIMEOUT_S,
    DSOURCE_NAME_STATE_KEY,
    MASTER_SUB_STATE_KEY,
    ONBOARDING_TIMEOUT_S,
    ONBOARD_ACTION,
    ONBOARD_PAYLOAD,
    PROVISIONING_TIMEOUT_S,
    REFRESH_ACTION,
    REFRESH_TIMEOUT_S,
)
from e2e.services.dsource import DsourceNotFoundError, discover_dsource_name
from tests.helpers.lifecycle import (
    apply_action_idempotent,
    assert_terminal_status,
    get_or_create_subscription,
    wait_for_demand_success,
)

logger = logging.getLogger(__name__)

# ... @scenario bindings unchanged ...


@then("the dSource is onboarded within one hour")
def _dsource_onboarded(orcv2, dlx, pdb_subscription, vdb_state):
    wait_for_demand_success(
        orcv2, pdb_subscription, ONBOARDING_TIMEOUT_S, kind="DSOURCE",
    )
    try:
        dsource_name = discover_dsource_name(orcv2, dlx, pdb_subscription.id)
    except DsourceNotFoundError as exc:
        pytest.fail(f"[DSOURCE] Onboarding succeeded but discovery failed: {exc}")

    vdb_state[DSOURCE_NAME_STATE_KEY] = dsource_name
    logger.info(
        "[DSOURCE] Onboarded dsource_name=%s pdb_subscription_id=%s",
        dsource_name, pdb_subscription.id,
    )


=======

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
bdd_features_base_dir = "tests/features"

=======

.test_base:
  before_script:
    - source venv/bin/activate
    - test -f .env && set -a && . ./.env && set +a || true
  variables:
    KEEP_VDB_AFTER_TEST: "1"
  resource_group: delphix-e2e
  artifacts:
    when: always
    paths:
      - vdb_state.json
      - reports/




