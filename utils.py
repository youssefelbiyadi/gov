def delete_subscription_idempotent(
    orchestrator_v2,
    subscription: Subscription,
    *,
    kind: Kind,
) -> Subscription:
    """Delete `subscription`, tolerating already-terminated and in-flight states.

    Short-circuits when the subscription is already TERMINATED, or currently
    TERMINATING (the caller should poll the existing delete demand).
    """
    if subscription.status == SubscriptionStatus.TERMINATED:
        logger.info(
            "[%s] Already TERMINATED subscription_id=%s — no-op",
            kind, subscription.id,
        )
        return subscription

    if subscription.status == SubscriptionStatus.TERMINATING:
        logger.info(
            "[%s] Delete already in progress subscription_id=%s — reusing demand",
            kind, subscription.id,
        )
        return subscription

    orchestrator_v2.delete_subscription(subscription.id)
    refreshed = orchestrator_v2.get_subscription(subscription.id)
    logger.info(
        "[%s] Delete requested subscription_id=%s",
        kind, refreshed.id,
    )
    return refreshed


@when("I delete the client VDB", target_fixture="client_subscription")
def _delete_client(orchestrator_v2, client_subscription):
    return delete_subscription_idempotent(
        orchestrator_v2, client_subscription, kind="CLIENT",
    )


@when("I delete the master VDB", target_fixture="master_subscription")
def _delete_master(orchestrator_v2, master_subscription):
    return delete_subscription_idempotent(
        orchestrator_v2, master_subscription, kind="MASTER",
    )
