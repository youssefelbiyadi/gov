"""E2E VDB lifecycle scenarios."""
from __future__ import annotations

import logging
import os

import pytest
from pytest_bdd import given, scenario, then, when

from delphix_e2e.constants import (
    CLIENT_CREATE_DEMAND_KEY,
    CLIENT_DELETE_DEMAND_KEY,
    CLIENT_REFRESH_DEMAND_KEY,
    CLIENT_SUBSCRIPTION_KEY,
    DELETION_TIMEOUT_S,
    MASTER_CREATE_DEMAND_KEY,
    MASTER_DELETE_DEMAND_KEY,
    MASTER_REFRESH_DEMAND_KEY,
    MASTER_SUBSCRIPTION_KEY,
    ONBOARD_ACTION,
    ONBOARD_PAYLOAD,
    ONBOARDING_TIMEOUT_S,
    PDB_ONBOARD_DEMAND_KEY,
    PROVISIONING_TIMEOUT_S,
    REFRESH_ACTION,
    REFRESH_TIMEOUT_S,
)
from delphix_e2e.models import SubscriptionStatus
from delphix_e2e.services.dsource import DsourceNotFoundError, resolve_dsource_name
from tests.e2e.helpers.lifecycle import (
    apply_action_idempotent,
    assert_terminal_status,
    delete_subscription_idempotent,
    get_or_create_subscription,
    wait_for_demand_success,
)

logger = logging.getLogger(__name__)

FEATURE_FILE = "vdb_lifecycle.feature"


# ─── Scenario bindings ─────────────────────────────────────────────────────

@scenario(FEATURE_FILE, "Onboarding the dSource from the existing PDB")
def test_dsource_onboard(): ...


@scenario(FEATURE_FILE, "Provisioning the master VDB")
def test_master_create(): ...


@scenario(FEATURE_FILE, "Refreshing the master VDB from snapshot")
def test_master_refresh(): ...


@scenario(FEATURE_FILE, "Provisioning a client VDB from the master")
def test_client_create(): ...


@scenario(FEATURE_FILE, "Decommissioning the client VDB")
def test_client_delete(): ...


@scenario(FEATURE_FILE, "Decommissioning the master VDB")
def test_master_delete(): ...


# ─── Given steps ───────────────────────────────────────────────────────────

@given("an orchestrator env", target_fixture="orchestrator_env")
def _orchestrator_env(orchestrator_v2):
    logger.info("[ORCH] Env ready: %s", os.environ.get("ORCV2_URL"))
    return orchestrator_v2


@given("an existing PDB subscription", target_fixture="pdb_subscription")
def _existing_pdb(orchestrator_v2):
    return orchestrator_v2.get_subscription(os.environ["PDB_SUBSCRIPTION_ID"])


@given("an existing master VDB", target_fixture="master_subscription")
def _existing_master(orchestrator_v2, vdb_state):
    sub_id = vdb_state.get(MASTER_SUBSCRIPTION_KEY)
    if not sub_id:
        pytest.skip("No master_subscription_id in state — run master_create first")
    return orchestrator_v2.get_subscription(sub_id)


@given("an existing client VDB", target_fixture="client_subscription")
def _existing_client(orchestrator_v2, vdb_state):
    sub_id = vdb_state.get(CLIENT_SUBSCRIPTION_KEY)
    if not sub_id:
        pytest.skip("No client_subscription_id in state — run client_create first")
    return orchestrator_v2.get_subscription(sub_id)


# ─── dSource onboarding ────────────────────────────────────────────────────

@when("I onboard the dSource", target_fixture="pdb_subscription")
def _onboard_dsource(orchestrator_v2, pdb_subscription, vdb_state):
    return apply_action_idempotent(
        orchestrator_v2,
        pdb_subscription,
        action=ONBOARD_ACTION,
        payload=ONBOARD_PAYLOAD,
        vdb_state=vdb_state,
        demand_key=PDB_ONBOARD_DEMAND_KEY,
        kind="PDB",
    )


@then("the dSource is onboarded within one hour")
def _dsource_onboarded(orchestrator_v2, dlx, pdb_subscription, vdb_state):
    wait_for_demand_success(
        orchestrator_v2, vdb_state, PDB_ONBOARD_DEMAND_KEY,
        ONBOARDING_TIMEOUT_S, kind="DSOURCE",
    )
    try:
        dsource_name = resolve_dsource_name(vdb_state, orchestrator_v2, dlx)
    except DsourceNotFoundError as exc:
        pytest.fail(f"[DSOURCE] Onboarding succeeded but dSource not findable: {exc}")
    logger.info(
        "[DSOURCE] Onboarded dsource_name=%s pdb_subscription_id=%s",
        dsource_name, pdb_subscription.id,
    )


# ─── Master VDB ────────────────────────────────────────────────────────────

@when("I create a master VDB", target_fixture="master_subscription")
def _create_master(orchestrator_v2, master_payload, vdb_state, created_subscriptions):
    return get_or_create_subscription(
        orchestrator_v2,
        sub_key=MASTER_SUBSCRIPTION_KEY,
        demand_key=MASTER_CREATE_DEMAND_KEY,
        payload=master_payload,
        vdb_state=vdb_state,
        created_subscriptions=created_subscriptions,
        kind="MASTER",
    )


@then("the master VDB is ACTIVE within two hours")
def _master_active(orchestrator_v2, master_subscription, vdb_state):
    assert_terminal_status(
        orchestrator_v2,
        master_subscription,
        SubscriptionStatus.ACTIVE,
        vdb_state=vdb_state,
        demand_key=MASTER_CREATE_DEMAND_KEY,
        timeout_s=PROVISIONING_TIMEOUT_S,
        kind="MASTER",
    )


@when("I refresh the master VDB", target_fixture="master_subscription")
def _refresh_master(orchestrator_v2, master_subscription, vdb_state):
    return apply_action_idempotent(
        orchestrator_v2,
        master_subscription,
        action=REFRESH_ACTION,
        payload=None,
        vdb_state=vdb_state,
        demand_key=MASTER_REFRESH_DEMAND_KEY,
        kind="MASTER",
    )


@then("the master VDB is refreshed within one hour")
def _master_refreshed(orchestrator_v2, master_subscription, vdb_state):
    wait_for_demand_success(
        orchestrator_v2, vdb_state, MASTER_REFRESH_DEMAND_KEY,
        REFRESH_TIMEOUT_S, kind="MASTER",
    )


@when("I delete the master VDB", target_fixture="master_subscription")
def _delete_master(orchestrator_v2, master_subscription, vdb_state):
    return delete_subscription_idempotent(
        orchestrator_v2,
        master_subscription,
        vdb_state=vdb_state,
        demand_key=MASTER_DELETE_DEMAND_KEY,
        kind="MASTER",
    )


@then("the master VDB is TERMINATED within thirty minutes")
def _master_terminated(orchestrator_v2, master_subscription, vdb_state):
    assert_terminal_status(
        orchestrator_v2,
        master_subscription,
        SubscriptionStatus.TERMINATED,
        vdb_state=vdb_state,
        demand_key=MASTER_DELETE_DEMAND_KEY,
        timeout_s=DELETION_TIMEOUT_S,
        kind="MASTER",
    )


# ─── Client VDB ────────────────────────────────────────────────────────────

@when("I create a client VDB", target_fixture="client_subscription")
def _create_client(orchestrator_v2, client_payload, vdb_state, created_subscriptions):
    return get_or_create_subscription(
        orchestrator_v2,
        sub_key=CLIENT_SUBSCRIPTION_KEY,
        demand_key=CLIENT_CREATE_DEMAND_KEY,
        payload=client_payload,
        vdb_state=vdb_state,
        created_subscriptions=created_subscriptions,
        kind="CLIENT",
    )


@then("the client VDB is ACTIVE within two hours")
def _client_active(orchestrator_v2, client_subscription, vdb_state):
    assert_terminal_status(
        orchestrator_v2,
        client_subscription,
        SubscriptionStatus.ACTIVE,
        vdb_state=vdb_state,
        demand_key=CLIENT_CREATE_DEMAND_KEY,
        timeout_s=PROVISIONING_TIMEOUT_S,
        kind="CLIENT",
    )


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


@when("I delete the client VDB", target_fixture="client_subscription")
def _delete_client(orchestrator_v2, client_subscription, vdb_state):
    return delete_subscription_idempotent(
        orchestrator_v2,
        client_subscription,
        vdb_state=vdb_state,
        demand_key=CLIENT_DELETE_DEMAND_KEY,
        kind="CLIENT",
    )


@then("the client VDB is TERMINATED within thirty minutes")
def _client_terminated(orchestrator_v2, client_subscription, vdb_state):
    assert_terminal_status(
        orchestrator_v2,
        client_subscription,
        SubscriptionStatus.TERMINATED,
        vdb_state=vdb_state,
        demand_key=CLIENT_DELETE_DEMAND_KEY,
        timeout_s=DELETION_TIMEOUT_S,
        kind="CLIENT",
    )
