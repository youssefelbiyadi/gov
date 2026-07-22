@pytest.mark.unit
def test_engine_onboarding_candidate_to_json():
    candidate = EngineOnboardingCandidate(
        engine=engine,
        projected_usage=1_800.0,   # e.g. Ds*M + U*n
        capacity_ceiling=1_200.0,  # 0.8 * C
        headroom=-600.0,           # ceiling - projected (value carried as-is)
    )
    assert candidate.to_json() == {
        "id": "249494002-2222-3333-aaaa-bbbb",
        "status": "ACTIVE",
        "external_id": "engine_id",
        "name": "engine_name",
        "hostname": "engine_hostname",
        "business_unit_group": "CARDIF",
        "type": "VIRTUALIZATION",
        "business_units": ["CARDIF_ITALY", "UPM_CARDIF"],
        "tags": [{"key": "dummy key", "value": "dummy value"}],
        # --- new engine columns (present now that to_json exposes them) ---
        "can_onboard": engine.can_onboard,
        "sources": engine.sources,
        "reserved_apcodes": engine.reserved_apcodes,
        # --- candidate-specific fields ---
        "projected_usage": 1_800.0,
        "capacity_ceiling": 1_200.0,
        "headroom": -600.0,
    }