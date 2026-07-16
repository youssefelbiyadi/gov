# delphix_e2e/services/subscriptions.py (or a new services/master.py)

import os
from delphix_e2e.constants import MASTER_SUBSCRIPTION_KEY


def resolve_master_subscription_id(state: dict[str, Any]) -> str:
    """Resolve the master VDB subscription id from the cheapest source first:

        1. Cached in state (set by @master_create earlier in the pipeline).
        2. MASTER_SUBSCRIPTION_ID env var (operator override, mapped from
           MASTER_SUBSCRIPTION_OVERRIDE in the CI job).

    Raises:
        RuntimeError: when neither source yields a value — this indicates the
            operator meant to skip master stages but didn't provide the id.
    """
    if cached := state.get(MASTER_SUBSCRIPTION_KEY):
        return cached
    if override := os.getenv("MASTER_SUBSCRIPTION_ID"):
        return override

    raise RuntimeError(
        "No master_subscription_id in state or MASTER_SUBSCRIPTION_ID env — "
        "run @master_create first, or set MASTER_SUBSCRIPTION_OVERRIDE when "
        "resuming from client_create."
    )

@pytest.fixture
def client_payload(
    vdb_state,
    orchestrator_v2,
    delphix_client,
) -> dict[str, Any]:
    master_subscription_id = resolve_master_subscription_id(vdb_state)

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


@given("an existing master VDB", target_fixture="master_subscription")
def _existing_master(orchestrator_v2, vdb_state):
    try:
        sub_id = resolve_master_subscription_id(vdb_state)
    except RuntimeError as exc:
        pytest.skip(str(exc))
    return orchestrator_v2.get_subscription(sub_id)

