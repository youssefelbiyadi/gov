import pytest

from delphix_core.models.engine import Engine
from delphix_core.services.engine import (
    EngineOnboardingCandidate,
    STORAGE_MULTIPLIER,   # M = 3
    USAGE_FACTOR,         # n = 1.25
    CAPACITY_THRESHOLD,   # 0.8
)
from tests.common import given_an_inserted_engine


# -----------------------------------------------------------------------------
# Happy path: an eligible engine with enough capacity is returned as a candidate
# -----------------------------------------------------------------------------
@pytest.mark.unit
def test_find_onboarding_candidates_success(engine_service, mock_dct_client):
    engine = given_an_inserted_engine(
        service=engine_service,
        external_id="dct-engine-1",
        name="engine-1",
        hostname="hostname-1",
        business_unit_group="CARDIF",
        type=EngineType.VIRTUALIZATION,
        business_units=["BU_1"],
        status=Status.ACTIVE,
        can_onboard=True,
        sources=None,
        reserved_apcodes=None,
    )
    # C = 10_000 ; U = 1_000. Ceiling = 0.8*10_000 = 8_000.
    # For Ds = 100: projected = 100*3 + 1_000*1.25 = 300 + 1_250 = 1_550 <= 8_000
    mock_dct_client.list.return_value = [
        _dct_engine(
            external_id="dct-engine-1",
            data_storage_capacity=10_000,
            data_storage_used=1_000,
        ),
    ]

    candidates = engine_service.find_onboarding_candidates(
        business_unit="BU_1",
        dsource_size=100,
        source_name="PDB_APP",
        ap_code="AP123",
    )

    mock_dct_client.list.assert_called_once_with(endpoint="management/engines")
    assert len(candidates) == 1
    candidate = candidates[0]
    assert isinstance(candidate, EngineOnboardingCandidate)
    assert candidate.engine.id == engine.id
    assert candidate.projected_usage == 100 * STORAGE_MULTIPLIER + 1_000 * USAGE_FACTOR
    assert candidate.capacity_ceiling == CAPACITY_THRESHOLD * 10_000
    assert candidate.headroom == candidate.capacity_ceiling - candidate.projected_usage


# -----------------------------------------------------------------------------
# Rule 1: can_onboard=False is excluded — and DCT is never hit (short-circuit)
# -----------------------------------------------------------------------------
@pytest.mark.unit
def test_find_onboarding_candidates_skips_when_cannot_onboard(
    engine_service, mock_dct_client
):
    given_an_inserted_engine(
        service=engine_service,
        external_id="dct-engine-1",
        name="engine-1",
        hostname="hostname-1",
        business_unit_group="CARDIF",
        type=EngineType.VIRTUALIZATION,
        business_units=["BU_1"],
        status=Status.ACTIVE,
        can_onboard=False,
    )

    candidates = engine_service.find_onboarding_candidates(
        business_unit="BU_1",
        dsource_size=100,
        source_name="PDB_APP",
        ap_code="AP123",
    )

    assert candidates == []
    mock_dct_client.list.assert_not_called()


# -----------------------------------------------------------------------------
# Rule 2: engine reserved for a different source PDB is excluded
# -----------------------------------------------------------------------------
@pytest.mark.unit
def test_find_onboarding_candidates_skips_when_reserved_for_other_source(
    engine_service, mock_dct_client
):
    given_an_inserted_engine(
        service=engine_service,
        external_id="dct-engine-1",
        name="engine-1",
        hostname="hostname-1",
        business_unit_group="CARDIF",
        type=EngineType.VIRTUALIZATION,
        business_units=["BU_1"],
        status=Status.ACTIVE,
        can_onboard=True,
        sources=["PDB_OTHER"],
    )

    candidates = engine_service.find_onboarding_candidates(
        business_unit="BU_1",
        dsource_size=100,
        source_name="PDB_APP",
        ap_code="AP123",
    )

    assert candidates == []
    mock_dct_client.list.assert_not_called()


# -----------------------------------------------------------------------------
# Rule 2 (positive): engine reserved for THIS source PDB is kept
# -----------------------------------------------------------------------------
@pytest.mark.unit
def test_find_onboarding_candidates_keeps_when_reserved_for_this_source(
    engine_service, mock_dct_client
):
    engine = given_an_inserted_engine(
        service=engine_service,
        external_id="dct-engine-1",
        name="engine-1",
        hostname="hostname-1",
        business_unit_group="CARDIF",
        type=EngineType.VIRTUALIZATION,
        business_units=["BU_1"],
        status=Status.ACTIVE,
        can_onboard=True,
        sources=["PDB_APP"],
    )
    mock_dct_client.list.return_value = [
        _dct_engine(
            external_id="dct-engine-1",
            data_storage_capacity=10_000,
            data_storage_used=1_000,
        ),
    ]

    candidates = engine_service.find_onboarding_candidates(
        business_unit="BU_1",
        dsource_size=100,
        source_name="PDB_APP",
        ap_code="AP123",
    )

    assert len(candidates) == 1
    assert candidates[0].engine.id == engine.id


# -----------------------------------------------------------------------------
# Rule 3: engine reserved for a different AP-code is excluded
# -----------------------------------------------------------------------------
@pytest.mark.unit
def test_find_onboarding_candidates_skips_when_reserved_for_other_apcode(
    engine_service, mock_dct_client
):
    given_an_inserted_engine(
        service=engine_service,
        external_id="dct-engine-1",
        name="engine-1",
        hostname="hostname-1",
        business_unit_group="CARDIF",
        type=EngineType.VIRTUALIZATION,
        business_units=["BU_1"],
        status=Status.ACTIVE,
        can_onboard=True,
        reserved_apcodes=["AP_OTHER"],
    )

    candidates = engine_service.find_onboarding_candidates(
        business_unit="BU_1",
        dsource_size=100,
        source_name="PDB_APP",
        ap_code="AP123",
    )

    assert candidates == []
    mock_dct_client.list.assert_not_called()


# -----------------------------------------------------------------------------
# Rule 4: engine passes rules 1-3 but fails the capacity check -> excluded
# -----------------------------------------------------------------------------
@pytest.mark.unit
def test_find_onboarding_candidates_skips_when_capacity_exceeded(
    engine_service, mock_dct_client
):
    given_an_inserted_engine(
        service=engine_service,
        external_id="dct-engine-1",
        name="engine-1",
        hostname="hostname-1",
        business_unit_group="CARDIF",
        type=EngineType.VIRTUALIZATION,
        business_units=["BU_1"],
        status=Status.ACTIVE,
        can_onboard=True,
    )
    # C = 1_000 ; U = 900 -> U*n = 1_125 already > 0.8*1_000 = 800
    mock_dct_client.list.return_value = [
        _dct_engine(
            external_id="dct-engine-1",
            data_storage_capacity=1_000,
            data_storage_used=900,
        ),
    ]

    candidates = engine_service.find_onboarding_candidates(
        business_unit="BU_1",
        dsource_size=100,
        source_name="PDB_APP",
        ap_code="AP123",
    )

    mock_dct_client.list.assert_called_once_with(endpoint="management/engines")
    assert candidates == []


# -----------------------------------------------------------------------------
# BU filter + DELETED exclusion: only the ACTIVE engine in the target BU that
# fits is returned. Verifies BU membership, status, and capacity together.
# -----------------------------------------------------------------------------
@pytest.mark.unit
def test_find_onboarding_candidates_filters_by_bu_and_status(
    engine_service, mock_dct_client
):
    fitting = given_an_inserted_engine(
        service=engine_service,
        external_id="dct-engine-fit",
        name="engine-fit",
        hostname="hostname-fit",
        business_unit_group="CARDIF",
        type=EngineType.VIRTUALIZATION,
        business_units=["BU_1"],
        status=Status.ACTIVE,
        can_onboard=True,
    )
    # Same BU but soft-deleted: must never reach DCT / the result.
    given_an_inserted_engine(
        service=engine_service,
        external_id="dct-engine-deleted",
        name="engine-deleted",
        hostname="hostname-deleted",
        business_unit_group="CARDIF",
        type=EngineType.VIRTUALIZATION,
        business_units=["BU_1"],
        status=Status.DELETED,
        can_onboard=True,
    )
    # Different BU: filtered out at the DB level.
    given_an_inserted_engine(
        service=engine_service,
        external_id="dct-engine-other-bu",
        name="engine-other-bu",
        hostname="hostname-other-bu",
        business_unit_group="ARVAL",
        type=EngineType.VIRTUALIZATION,
        business_units=["BU_2"],
        status=Status.ACTIVE,
        can_onboard=True,
    )
    mock_dct_client.list.return_value = [
        _dct_engine(
            external_id="dct-engine-fit",
            data_storage_capacity=10_000,
            data_storage_used=1_000,
        ),
        _dct_engine(
            external_id="dct-engine-deleted",
            data_storage_capacity=10_000,
            data_storage_used=1_000,
        ),
        _dct_engine(
            external_id="dct-engine-other-bu",
            data_storage_capacity=10_000,
            data_storage_used=1_000,
        ),
    ]

    candidates = engine_service.find_onboarding_candidates(
        business_unit="BU_1",
        dsource_size=100,
        source_name="PDB_APP",
        ap_code="AP123",
    )

    assert {c.engine.id for c in candidates} == {fitting.id}


# -----------------------------------------------------------------------------
# No engine matches the BU at all -> empty list, DCT untouched
# -----------------------------------------------------------------------------
@pytest.mark.unit
def test_find_onboarding_candidates_returns_empty_when_no_bu_match(
    engine_service, mock_dct_client
):
    given_an_inserted_engine(
        service=engine_service,
        external_id="dct-engine-1",
        name="engine-1",
        hostname="hostname-1",
        business_unit_group="CARDIF",
        type=EngineType.VIRTUALIZATION,
        business_units=["BU_2"],
        status=Status.ACTIVE,
        can_onboard=True,
    )

    candidates = engine_service.find_onboarding_candidates(
        business_unit="BU_1",
        dsource_size=100,
        source_name="PDB_APP",
        ap_code="AP123",
    )

    assert candidates == []
    mock_dct_client.list.assert_not_called()


# -----------------------------------------------------------------------------
# DCT failure propagates as EngineServiceError (reuses _fetch_capacity_by_id's
# error handling — same behaviour as list_capacity_reports).
# -----------------------------------------------------------------------------
@pytest.mark.unit
def test_find_onboarding_candidates_but_dct_failure(
    engine_service, mock_dct_client
):
    given_an_inserted_engine(
        service=engine_service,
        external_id="dct-engine-1",
        name="engine-1",
        hostname="hostname-1",
        business_unit_group="CARDIF",
        type=EngineType.VIRTUALIZATION,
        business_units=["BU_1"],
        status=Status.ACTIVE,
        can_onboard=True,
    )
    mock_dct_client.list.side_effect = Exception("boom")

    with pytest.raises(
        EngineServiceError,
        match="Failed to fetch engine capacity from DCT",
    ):
        engine_service.find_onboarding_candidates(
            business_unit="BU_1",
            dsource_size=100,
            source_name="PDB_APP",
            ap_code="AP123",
        )