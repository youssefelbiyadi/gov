"""Lifecycle helpers — idempotency, demand tracking, polling, terminal asserts.

The orchestrator client returns a WriteResponse with a demand_id on create,
apply_action, and delete. We persist that demand_id in vdb_state so retries
can resume polling without reissuing the write.
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from delphix_e2e.adapters.orchestrator import (
    DemandFailedError,
    OrchestratorClient,
    OrchestratorTimeoutError,
)
from delphix_e2e.models import (
    DemandStatus, Subscription, SubscriptionStatus, WriteResponse,
)

logger = logging.getLogger(__name__)

Kind = Literal["PDB", "DSOURCE", "MASTER", "CLIENT"]


# ─── Create / get-or-create ────────────────────────────────────────────────

def get_or_create_subscription(
    client: OrchestratorClient,
    sub_key: str,
    demand_key: str,
    payload: dict[str, Any],
    vdb_state: dict[str, Any],
    created_subscriptions: list[str],
    *,
    kind: Kind,
) -> Subscription:
    """Reuse the subscription from state if still healthy, else create fresh.
    Persists the create-demand id into `vdb_state[demand_key]` for polling."""
    if existing_id := vdb_state.get(sub_key):
        existing = client.get_subscription(existing_id)
        if existing.status not in (
            SubscriptionStatus.TERMINATED, SubscriptionStatus.FAILED,
        ):
            logger.info(
                "[%s] Reusing subscription_id=%s status=%s",
                kind, existing.id, existing.status.value,
            )
            return existing
        logger.info(
            "[%s] subscription_id=%s is %s — creating fresh",
            kind, existing.id, existing.status.value,
        )

    response = client.create_subscription(payload)
    created_subscriptions.append(str(response.subscription_id))

    vdb_state[sub_key] = str(response.subscription_id)
    vdb_state[demand_key] = str(response.demand_id)
    logger.info(
        "[%s] Created subscription_id=%s demand_id=%s",
        kind, response.subscription_id, response.demand_id,
    )

    return client.get_subscription(response.subscription_id)


# ─── Actions (refresh, onboard, ...) ───────────────────────────────────────

def apply_action_idempotent(
    client: OrchestratorClient,
    subscription: Subscription,
    action: str,
    payload: dict[str, Any] | None,
    vdb_state: dict[str, Any],
    demand_key: str,
    *,
    kind: Kind,
) -> Subscription:
    """Apply `action` on `subscription`, reusing any pending demand recorded
    in state. The new demand id is written to `vdb_state[demand_key]`."""
    if pending := vdb_state.get(demand_key):
        logger.info(
            "[%s] Pending demand_id=%s already recorded for action %r — reusing",
            kind, pending, action,
        )
        return subscription

    response = client.apply_action(subscription.id, action, payload=payload)
    vdb_state[demand_key] = str(response.demand_id)
    logger.info(
        "[%s] Action %r triggered demand_id=%s",
        kind, action, response.demand_id,
    )

    return client.get_subscription(subscription.id)


# ─── Delete ────────────────────────────────────────────────────────────────

def delete_subscription_idempotent(
    client: OrchestratorClient,
    subscription: Subscription,
    vdb_state: dict[str, Any],
    demand_key: str,
    *,
    kind: Kind,
) -> Subscription:
    """Delete `subscription`, tolerating already-terminated and in-flight states.
    Persists the delete demand id into state for polling."""
    if subscription.status == SubscriptionStatus.TERMINATED:
        logger.info(
            "[%s] Already TERMINATED subscription_id=%s — no-op",
            kind, subscription.id,
        )
        vdb_state.pop(demand_key, None)
        return subscription

    if subscription.status == SubscriptionStatus.TERMINATING:
        if pending := vdb_state.get(demand_key):
            logger.info(
                "[%s] Delete already in progress demand_id=%s — reusing",
                kind, pending,
            )
            return subscription
        logger.warning(
            "[%s] subscription_id=%s is TERMINATING but no delete demand "
            "recorded — re-issuing delete",
            kind, subscription.id,
        )

    response = client.delete_subscription(subscription.id)
    vdb_state[demand_key] = str(response.demand_id)
    logger.info(
        "[%s] Delete requested subscription_id=%s demand_id=%s",
        kind, subscription.id, response.demand_id,
    )

    return client.get_subscription(subscription.id)


# ─── Polling ───────────────────────────────────────────────────────────────

def wait_for_demand_success(
    client: OrchestratorClient,
    vdb_state: dict[str, Any],
    demand_key: str,
    timeout_s: int,
    *,
    kind: Kind,
    poll_interval_s: int = 30,
) -> None:
    """Poll the demand id recorded in `vdb_state[demand_key]` until SUCCESS.

    On success, clears the key from state so the next operation starts clean.
    On failure (timeout or terminal-failure status), leaves the key in place
    for debugging and raises AssertionError.
    """
    demand_id = vdb_state.get(demand_key)
    if demand_id is None:
        logger.info("[%s] No pending demand recorded — nothing to wait on", kind)
        return

    logger.info(
        "[%s] Waiting for demand_id=%s up to %d seconds",
        kind, demand_id, timeout_s,
    )
    try:
        client.wait_for_demand(
            demand_id,
            target=DemandStatus.SUCCESS,
            timeout_s=timeout_s,
            poll_interval_s=poll_interval_s,
        )
    except DemandFailedError as exc:
        raise AssertionError(f"[{kind}] {exc}") from exc
    except OrchestratorTimeoutError as exc:
        raise AssertionError(f"[{kind}] {exc}") from exc

    logger.info("[%s] demand_id=%s reached SUCCESS", kind, demand_id)
    vdb_state.pop(demand_key, None)


# ─── Terminal assertion ────────────────────────────────────────────────────

def assert_terminal_status(
    client: OrchestratorClient,
    subscription: Subscription,
    expected: SubscriptionStatus,
    vdb_state: dict[str, Any],
    demand_key: str,
    timeout_s: int,
    *,
    kind: Kind,
) -> None:
    """Wait for the recorded demand, then assert subscription reached `expected`.

    Short-circuits if the subscription is already at `expected` — handles the
    case where the DAG finished while the GitLab runner died, so the retry
    sees the final state without re-polling.
    """
    if subscription.status == expected:
        logger.info(
            "[%s] subscription_id=%s already at %s — no wait needed",
            kind, subscription.id, expected.value,
        )
        vdb_state.pop(demand_key, None)
        return

    wait_for_demand_success(
        client, vdb_state, demand_key, timeout_s, kind=kind,
    )

    final = client.get_subscription(subscription.id)
    assert final.status == expected, (
        f"[{kind}] Expected {expected.value}, got {final.status.value} "
        f"(subscription_id={subscription.id})"
    )
    logger.info(
        "[%s] subscription_id=%s reached %s",
        kind, subscription.id, expected.value,
    )
