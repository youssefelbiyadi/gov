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
# Convention: <resource>_<purpose>
#   *_subscription_id   — the subscription's UUID
#   *_pending_demand_id — the demand currently being waited on;
#                         cleared once the demand reaches SUCCESS.

DSOURCE_NAME_KEY: Final[str] = "dsource_name"

PDB_PENDING_DEMAND_KEY: Final[str] = "pdb_pending_demand_id"

MASTER_SUBSCRIPTION_KEY: Final[str] = "master_subscription_id"
MASTER_PENDING_DEMAND_KEY: Final[str] = "master_pending_demand_id"

CLIENT_SUBSCRIPTION_KEY: Final[str] = "client_subscription_id"
CLIENT_PENDING_DEMAND_KEY: Final[str] = "client_pending_demand_id"
