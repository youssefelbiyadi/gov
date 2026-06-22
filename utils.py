import time

_DEMAND_VISIBILITY_TIMEOUT_S = 30
_DEMAND_POLL_INTERVAL_S = 2


def _ongoing_demands(sub) -> list:
    return [
        d for d in sub.demands
        if d.status in (DemandStatus.ON_HOLD, DemandStatus.IN_PROGRESS)
    ]


def wait_for_demand_success(orchestrator_v2, subscription, timeout_s, *, kind):
    """Wait for the latest in-flight demand on `subscription` to reach SUCCESS.

    Refetches the subscription to avoid acting on a stale `demands` snapshot.
    If no in-flight demand is visible, polls briefly — the orchestrator may
    not have registered the demand yet right after the action was applied.
    """
    # Always refetch — the subscription handed to us may pre-date the demand
    fresh = orchestrator_v2.get_subscription(subscription.id)
    in_flight = _ongoing_demands(fresh)

    deadline = time.monotonic() + _DEMAND_VISIBILITY_TIMEOUT_S
    while not in_flight and time.monotonic() < deadline:
        time.sleep(_DEMAND_POLL_INTERVAL_S)
        fresh = orchestrator_v2.get_subscription(subscription.id)
        in_flight = _ongoing_demands(fresh)

    if not in_flight:
        logger.warning(
            "[%s] No in-flight demand visible after %ds on subscription_id=%s — "
            "either the action completed synchronously or wasn't registered",
            kind, _DEMAND_VISIBILITY_TIMEOUT_S, subscription.id,
        )
        return

    demand_id = in_flight[-1].id
    logger.info(
        "[%s] Waiting for demand_id=%s up to %d seconds",
        kind, demand_id, timeout_s,
    )

    try:
        ready = orchestrator_v2.wait_for_demand_status(
            demand_id, DemandStatus.SUCCESS, timeout=timeout_s,
        )
    except ValueError as exc:
        raise AssertionError(f"[{kind}] Demand {demand_id} failed: {exc}") from exc

    if not ready:
        raise AssertionError(
            f"[{kind}] Demand {demand_id} did not reach SUCCESS within {timeout_s}s"
        )

    logger.info("[%s] demand_id=%s reached SUCCESS", kind, demand_id)
