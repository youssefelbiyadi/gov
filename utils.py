self.ONBOARDING_STORAGE_MULTIPLIER: int = int(
    get_env_var(name="ONBOARDING_STORAGE_MULTIPLIER", default="3")
)
self.ONBOARDING_USAGE_FACTOR: float = float(
    get_env_var(name="ONBOARDING_USAGE_FACTOR", default="1.25")
)
self.ONBOARDING_CAPACITY_THRESHOLD: float = float(
    get_env_var(name="ONBOARDING_CAPACITY_THRESHOLD", default="0.8")
)



def _evaluate_capacity(self, engine, capacity, dsource_size):
    projected_usage = (
        dsource_size * self.config.ONBOARDING_STORAGE_MULTIPLIER
        + capacity.data_storage_used * self.config.ONBOARDING_USAGE_FACTOR
    )
    capacity_ceiling = (
        self.config.ONBOARDING_CAPACITY_THRESHOLD * capacity.data_storage_capacity
    )
    if projected_usage > capacity_ceiling:
        return None
    return EngineOnboardingCandidate(...)
