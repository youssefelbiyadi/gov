"""Pytest fixtures — thin wiring layer over e2e/."""
from __future__ import annotations

import logging
import os
from typing import Any, Iterator

import pytest
import requests
from coe_pylib.gateways import orcv2 as orcv2_gateway  # adjust to real path

from e2e import state as state_io
from e2e.adapters.delphix_dct import DelphixClient
from e2e.services.dsource import resolve_dsource_name
from e2e.services.subscriptions import build_vdb_payload

logger = logging.getLogger(__name__)


# ---------- Clients ----------

@pytest.fixture(scope="session")
def orcv2():
    """Authenticated orchestrator gateway client."""
    client = orcv2_gateway(base_url=os.environ["ORCV2_URL"])
    client.set_bearer_token(os.environ["ORCV2_BEARER_TOKEN"])
    return client


@pytest.fixture(scope="session")
def dlx() -> Iterator[DelphixClient]:
    """Delphix DCT client — `/dsources` is public, no Authorization header."""
    session = requests.Session()
    session.headers["Accept"] = "application/json"
    if cert := os.getenv("DLX_CERT"):
        session.verify = cert

    client = DelphixClient(
        session=session,
        base_url=os.environ["DLX_URL"].rstrip("/"),
    )
    try:
        yield client
    finally:
        session.close()


# ---------- State ----------

@pytest.fixture(scope="session")
def vdb_state() -> Iterator[dict[str, Any]]:
    """Session-scoped state dict, persisted to vdb_state.json on session end."""
    data = state_io.load()
    try:
        yield data
    finally:
        state_io.save(data)


# ---------- Payloads ----------

@pytest.fixture
def master_payload(vdb_state, orcv2, dlx):
    return build_vdb_payload(
        vdb_type="MASTER",
        description="Master VDB — E2E lifecycle test",
        dsource_name=resolve_dsource_name(vdb_state, orcv2, dlx),
    )


@pytest.fixture
def client_payload(vdb_state, orcv2, dlx):
    return build_vdb_payload(
        vdb_type="CLIENT",
        description="Client VDB — E2E lifecycle test",
        dsource_name=resolve_dsource_name(vdb_state, orcv2, dlx),
    )


# ---------- Cleanup ----------

@pytest.fixture
def created_subscriptions(orcv2) -> Iterator[list]:
    """Tracks subscriptions created during a test; best-effort cleanup at the end
    unless KEEP_VDB_AFTER_TEST=1 (the default in CI to preserve work on retry)."""
    tracked = []
    yield tracked
    if os.getenv("KEEP_VDB_AFTER_TEST") == "1":
        return
    for sub in tracked:
        try:
            orcv2.delete_subscription(sub.id)
        except Exception as exc:
            logger.warning("Best-effort delete failed for %s: %s", sub.id, exc)


# ---------- pytest-bdd hooks ----------

def pytest_bdd_before_scenario(request, feature, scenario):
    logger.info("=== Scenario start: %s ===", scenario.name)


def pytest_bdd_after_scenario(request, feature, scenario):
    logger.info("=== Scenario end: %s ===", scenario.name)
