from unittest.mock import MagicMock

import pytest

from oradbaas.bp2i_oracle.services.environment import EnvironmentServiceDelphix


@pytest.fixture
def mock_gateway():
    return MagicMock()


@pytest.fixture
def service(mock_gateway):
    return EnvironmentServiceDelphix(delphix_gateway=mock_gateway)


@pytest.mark.unit
def test_get_dsource_engine_for_onboarding_selects_largest_headroom(
    service, mock_gateway
):
    engine_low = {"id": "engine-low", "headroom": 1_000}
    engine_high = {"id": "engine-high", "headroom": 9_000}
    engine_mid = {"id": "engine-mid", "headroom": 5_000}
    mock_gateway.list.return_value = {
        "engines": [engine_low, engine_high, engine_mid],
        "count": 3,
    }

    selected = service.get_dsource_engine_for_onboarding(
        bu="BU_1",
        dsource_size=1_000_000,
        source_name="PDB_APP",
        ap_code="AP123",
    )

    # business units are synced before candidates are queried
    mock_gateway.post.assert_called_once_with(
        endpoint="/engines/sync-business-units"
    )
    mock_gateway.list.assert_called_once_with(
        endpoint="engines/onboarding-candidates",
        payload={
            "business_unit": "BU_1",
            "dsource_size": 1_000_000,
            "source_name": "PDB_APP",
            "ap_code": "AP123",
        },
    )
    # the engine with the most headroom wins
    assert selected == engine_high


@pytest.mark.unit
def test_get_dsource_engine_for_onboarding_syncs_before_listing(
    service, mock_gateway
):
    call_order = []
    mock_gateway.post.side_effect = lambda **_: call_order.append("post")
    mock_gateway.list.side_effect = lambda **_: (
        call_order.append("list")
        or {"engines": [{"id": "e", "headroom": 1}], "count": 1}
    )

    service.get_dsource_engine_for_onboarding(
        bu="BU_1",
        dsource_size=1_000,
        source_name="PDB_APP",
        ap_code="AP123",
    )

    assert call_order == ["post", "list"]


@pytest.mark.unit
def test_get_dsource_engine_for_onboarding_single_candidate(service, mock_gateway):
    only = {"id": "engine-only", "headroom": 42}
    mock_gateway.list.return_value = {"engines": [only], "count": 1}

    selected = service.get_dsource_engine_for_onboarding(
        bu="BU_1",
        dsource_size=1_000,
        source_name="PDB_APP",
        ap_code="AP123",
    )

    assert selected == only


@pytest.mark.unit
def test_get_dsource_engine_for_onboarding_raises_when_no_candidates(
    service, mock_gateway
):
    mock_gateway.list.return_value = {"engines": [], "count": 0}

    with pytest.raises(
        ValueError,
        match="No engine can host a DSource of size '1000' for business unit 'BU_1'",
    ):
        service.get_dsource_engine_for_onboarding(
            bu="BU_1",
            dsource_size=1_000,
            source_name="PDB_APP",
            ap_code="AP123",
        )

    # sync still happened before we discovered there were no candidates
    mock_gateway.post.assert_called_once_with(
        endpoint="/engines/sync-business-units"
    )


@pytest.mark.unit
def test_get_dsource_engine_for_onboarding_raises_when_engines_key_missing(
    service, mock_gateway
):
    # response has no "engines" key at all -> response.get("engines", []) -> []
    mock_gateway.list.return_value = {"count": 0}

    with pytest.raises(ValueError, match="No engine can host a DSource"):
        service.get_dsource_engine_for_onboarding(
            bu="BU_1",
            dsource_size=1_000,
            source_name="PDB_APP",
            ap_code="AP123",
        )