def _ongoing_demands(sub: Subscription, action: str) -> list[Demand]:
    """Demands on `sub` matching `action` that are still in-flight."""
    return [
        d for d in sub.demands
        if d.action == action
        and d.status in (DemandStatus.IN_PROGRESS, DemandStatus.ON_HOLD)
    ]


def apply_action_idempotent(
    orchestrator_v2,
    subscription: Subscription,
    action: str,
    payload: dict | None = None,
    *,
    kind: Kind,
) -> Subscription:
    """Apply `action` to `subscription`, reusing any in-flight demand for the
    same action instead of firing a duplicate.

    A demand is considered in-flight when its status is ON_HOLD or IN_PROGRESS.
    If one is found, the subscription is returned as-is and the caller should
    poll the existing demand. Otherwise the action is applied fresh and the
    refreshed subscription is returned.
    """
    if in_flight := _ongoing_demands(subscription, action):
        latest = in_flight[-1]
        logger.info(
            "[%s] Action %r already in flight demand_id=%s status=%s — reusing",
            kind, action, latest.id, latest.status,
        )
        return subscription

    refreshed = orchestrator_v2.apply_action_subscription(
        subscription.id, action, payload=payload,
    )

    new_demands = _ongoing_demands(refreshed, action)
    if new_demands:
        logger.info(
            "[%s] Action %r triggered demand_id=%s",
            kind, action, new_demands[-1].id,
        )
    else:
        logger.warning(
            "[%s] Action %r applied but no in-flight demand reported — "
            "completed synchronously or not yet visible",
            kind, action,
        )
    return refreshed
