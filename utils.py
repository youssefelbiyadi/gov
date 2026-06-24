"""Pytest fixtures — thin wiring layer over delphix_e2e/."""
from __future__ import annotations

import logging
import os
from typing import Any, Iterator

import pytest
import requests

from delphix_e2e import state as state_io
from delphix_e2e.adapters.delphix import DelphixClient
from delphix_e2e.adapters.orchestrator import OrchestratorClient
from delphix_e2e.services.dsource import resolve_dsource_name
from delphix_e2e.services.subscriptions import build_vdb_payload

logger = logging.getLogger(__name__)


# ─── Clients ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def orchestrator_v2() -> OrchestratorClient:
    """Orchestrator client.

    Reads ORCV2_BEARER_TOKEN (CI default) or ORCV2_USERNAME/ORCV2_PASSWORD
    (local dev fallback).
    """
    return OrchestratorClient.from_env(os.environ["ORCV2_URL"])


@pytest.fixture(scope="session")
def dlx() -> Iterator[DelphixClient]:
    """Delphix DCT client — `/dsources` is public, no Authorization header."""
    session = requests.Session()
    session.headers["Accept"] = "application/json"
    client = DelphixClient(
        session=session,
        base_url=os.environ["DLX_URL"].rstrip("/"),
    )
    try:
        yield client
    finally:
        session.close()


# ─── State ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def vdb_state() -> Iterator[dict[str, Any]]:
    """Session-scoped state dict, persisted to vdb_state.json on session end."""
    data = state_io.load()
    try:
        yield data
    finally:
        state_io.save(data)


# ─── Payloads ──────────────────────────────────────────────────────────────

@pytest.fixture
def master_payload(vdb_state, orchestrator_v2, dlx) -> dict[str, Any]:
    return build_vdb_payload(
        vdb_type="MASTER",
        description="Master VDB — E2E lifecycle test",
        dsource_name=resolve_dsource_name(vdb_state, orchestrator_v2, dlx),
    )


@pytest.fixture
def client_payload(vdb_state, orchestrator_v2, dlx) -> dict[str, Any]:
    return build_vdb_payload(
        vdb_type="CLIENT",
        description="Client VDB — E2E lifecycle test",
        dsource_name=resolve_dsource_name(vdb_state, orchestrator_v2, dlx),
    )


# ─── Cleanup ───────────────────────────────────────────────────────────────

@pytest.fixture
def created_subscriptions(orchestrator_v2) -> Iterator[list[str]]:
    """Tracks subscription ids created during a test. Best-effort cleanup
    at end unless KEEP_VDB_AFTER_TEST=1 (CI default — preserves work for retry)."""
    tracked: list[str] = []
    yield tracked
    if os.getenv("KEEP_VDB_AFTER_TEST") == "1":
        logger.info(
            "[CLEANUP] KEEP_VDB_AFTER_TEST set, leaving %d subscription(s) alive",
            len(tracked),
        )
        return
    for sub_id in tracked:
        try:
            orchestrator_v2.delete_subscription(sub_id)
        except Exception as exc:
            logger.warning("Best-effort delete failed for %s: %s", sub_id, exc)


# ─── pytest-bdd hooks ──────────────────────────────────────────────────────

def pytest_bdd_before_scenario(request, feature, scenario):
    logger.info("=== Scenario start: %s ===", scenario.name)


def pytest_bdd_after_scenario(request, feature, scenario):
    logger.info("=== Scenario end:   %s ===", scenario.name)
