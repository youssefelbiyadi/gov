"""Snapshot resolution for client VDB provisioning."""
from __future__ import annotations

import logging
import os

from delphix_e2e.adapters.delphix import DelphixClient
from delphix_e2e.constants import SNAPSHOT_ID_OVERRIDE

logger = logging.getLogger(__name__)


class SnapshotNotFoundError(RuntimeError):
    """No snapshot found on the given master VDB."""


def resolve_snapshot_id(
    orchestrator_client,
    dlx_client: DelphixClient,
    master_subscription_id: str,
) -> str:
    """Resolve the snapshot id to use for client VDB provisioning.

    Precedence:
        1. SNAPSHOT_ID_OVERRIDE env var (operator override for one-off runs).
        2. Latest snapshot on the master VDB via DCT.

    Raises:
        SnapshotNotFoundError: when DCT returns no snapshots for the master.
    """
    if override := os.getenv(SNAPSHOT_ID_OVERRIDE):
        logger.info("[SNAPSHOT] Using override from %s=%s", SNAPSHOT_ID_OVERRIDE, override)
        return override

    master = orchestrator_client.get_subscription(master_subscription_id)
    master_vdb_id = master.raw["state"]["data"]["delphix_id"]

    snapshot = dlx_client.get_latest_vdb_snapshot(master_vdb_id)
    if not snapshot:
        raise SnapshotNotFoundError(
            f"No snapshots found on master VDB delphix_id={master_vdb_id} "
            f"(subscription_id={master_subscription_id})"
        )

    snapshot_id = snapshot["id"]
    logger.info(
        "[SNAPSHOT] Latest snapshot_id=%s from master_vdb_id=%s",
        snapshot_id, master_vdb_id,
    )
    return snapshot_id

def get_latest_vdb_snapshot(self, vdb_id: str) -> dict[str, Any] | None:
    """Return the most recent snapshot on `vdb_id`, or None if there aren't any."""
    response = self.session.get(
        f"{self.base_url.rstrip('/')}/vdbs/{vdb_id}/snapshots",
        params={"order_by": "creation_date", "order": "desc", "limit": 1},
        timeout=30,
    )
    response.raise_for_status()
    snapshots = response.json().get("snapshots") or []
    return snapshots[0] if snapshots else None


def build_vdb_payload(
    vdb_type: str,
    description: str,
    dsource_name: str,
    snapshot_id: str | None = None,
) -> dict[str, Any]:
    spec: dict[str, Any] = {"dsource_name": dsource_name, "vdb_type": vdb_type}
    if vdb_type == "MASTER":
        spec["bu"] = "DELPHIX"
    if snapshot_id:
        spec["snapshot_id"] = snapshot_id

    payload = _base_vdb_payload(spec=spec, description=description)
    payload["environment"] = os.getenv(ENVIRONMENT) or _get_vdb_environment(vdb_type)
    payload["realm"] = _get_vdb_realm(vdb_type)
    return payload

@pytest.fixture
def client_payload(
    vdb_state,
    orchestrator_v2,
    delphix_client,
) -> dict[str, Any]:
    master_subscription_id = vdb_state[MASTER_SUBSCRIPTION_KEY]

    return build_vdb_payload(
        vdb_type="CLIENT",
        description="Client VDB — E2E lifecycle test",
        dsource_name=resolve_dsource_name(
            orchestrator_client=orchestrator_v2,
            state=vdb_state,
            dlx_client=delphix_client,
        ),
        snapshot_id=resolve_snapshot_id(
            orchestrator_client=orchestrator_v2,
            dlx_client=delphix_client,
            master_subscription_id=master_subscription_id,
        ),
    )

