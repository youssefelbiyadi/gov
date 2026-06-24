"""dSource discovery and name resolution against the Delphix DCT API."""
from __future__ import annotations

import logging
import os
from typing import Any

from delphix_e2e.adapters.delphix import DelphixClient
from delphix_e2e.constants import DSOURCE_NAME_KEY

logger = logging.getLogger(__name__)


class DsourceNotFoundError(RuntimeError):
    """No ACTIVE dSource matches the given PDB."""


def discover_dsource_name(
    orchestrator_v2, dlx: DelphixClient, pdb_subscription_id: str,
) -> str:
    """Find the ACTIVE dSource onboarded for a given PDB subscription.

        1. Read the PDB subscription's `name` (PDB identifier) and `apcode`.
        2. List dSources scoped to that ap_code (server-side narrowing).
        3. Keep only those whose `pdb_name` matches exactly and status == ACTIVE.
        4. Return the dSource's `name` — used as `dsource_name` in VDB payloads.
    """
    pdb = orchestrator_v2.get_subscription(pdb_subscription_id)
    pdb_name, ap_code = pdb.name, pdb.apcode

    active = [
        d for d in dlx.list_dsources(ap_code=ap_code)
        if d.get("pdb_name") == pdb_name and d.get("status") == "ACTIVE"
    ]
    if not active:
        raise DsourceNotFoundError(
            f"No ACTIVE dSource for pdb_name={pdb_name} ap_code={ap_code}"
        )
    if len(active) > 1:
        logger.warning(
            "[DSOURCE] %d ACTIVE dSources for pdb_name=%s — picking %s (others: %s)",
            len(active), pdb_name, active[0]["name"],
            [d["name"] for d in active[1:]],
        )
    return active[0]["name"]


def resolve_dsource_name(
    state: dict[str, Any], orchestrator_v2, dlx: DelphixClient,
) -> str:
    """Resolve the dSource name from the cheapest source first:

        1. Cached in state (set by @dsource_onboard earlier in the pipeline).
        2. DSOURCE_NAME env var (local-dev override).
        3. Live discovery via PDB → DCT, then cached into state.
    """
    if cached := state.get(DSOURCE_NAME_KEY):
        return cached
    if override := os.getenv("DSOURCE_NAME"):
        return override

    name = discover_dsource_name(
        orchestrator_v2, dlx, os.environ["PDB_SUBSCRIPTION_ID"],
    )
    state[DSOURCE_NAME_KEY] = name
    return name
