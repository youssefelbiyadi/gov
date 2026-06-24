"""Centralized constants — timeouts, action names, state keys."""
from __future__ import annotations

from typing import Final

# ─── Timeouts (seconds) ────────────────────────────────────────────────────
ONBOARDING_TIMEOUT_S: Final[int] = 60 * 60
PROVISIONING_TIMEOUT_S: Final[int] = 2 * 60 * 60
REFRESH_TIMEOUT_S: Final[int] = 60 * 60
DELETION_TIMEOUT_S: Final[int] = 30 * 60

# ─── Orchestrator actions ──────────────────────────────────────────────────
ONBOARD_ACTION: Final[str] = "onboard_delphix"
REFRESH_ACTION: Final[str] = "refresh"

ONBOARD_PAYLOAD: Final[dict[str, bool]] = {"trigger_master_vdb_dag": False}

# ─── State keys (persisted to vdb_state.json) ──────────────────────────────
# Convention:
#   <resource>_<operation>_demand_id  — per-operation demand handle
#   <resource>_subscription_id        — the subscription's UUID
#
# A demand key is written when its operation is fired and cleared once the
# demand reaches SUCCESS. Operation-scoped naming prevents the refresh demand
# from clobbering the create demand on the same resource, which matters for
# retries: each stage owns its own handle.

DSOURCE_NAME_KEY: Final[str] = "dsource_name"

# PDB — onboarding is a day-2 action on a pre-existing subscription; the PDB
# subscription id is provided via env, so we only track the onboard demand.
PDB_ONBOARD_DEMAND_KEY: Final[str] = "pdb_onboard_demand_id"

# Master VDB
MASTER_SUBSCRIPTION_KEY: Final[str] = "master_subscription_id"
MASTER_CREATE_DEMAND_KEY: Final[str] = "master_create_demand_id"
MASTER_REFRESH_DEMAND_KEY: Final[str] = "master_refresh_demand_id"
MASTER_DELETE_DEMAND_KEY: Final[str] = "master_delete_demand_id"

# Client VDB
CLIENT_SUBSCRIPTION_KEY: Final[str] = "client_subscription_id"
CLIENT_CREATE_DEMAND_KEY: Final[str] = "client_create_demand_id"
CLIENT_REFRESH_DEMAND_KEY: Final[str] = "client_refresh_demand_id"
CLIENT_DELETE_DEMAND_KEY: Final[str] = "client_delete_demand_id"
