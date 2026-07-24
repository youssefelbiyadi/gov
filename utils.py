@pytest.mark.unit
def test_list_engine_onboarding_candidates_success(mock_core):
    candidates = [
        {
            "id": "engine-id-1",
            "status": "ACTIVE",
            "external_id": "48",
            "name": "engine-1",
            "hostname": "hostname-1",
            "business_unit_group": "BP2I",
            "business_units": ["BU-1"],
            "can_onboard": True,
            "reserved_sources": [],
            "reserved_apcodes": [],
            "type": "VIRTUALIZATION",
            "tags": [{"key": "tag-name-1", "value": "tag-value-1"}],
            "projected_usage": 1_550.0,
            "capacity_ceiling": 8_000.0,
            "headroom": 6_450.0,
        },
        {
            "id": "engine-id-2",
            "status": "ACTIVE",
            "external_id": "49",
            "name": "engine-2",
            "hostname": "hostname-2",
            "business_unit_group": "BP2I",
            "business_units": ["BU-1"],
            "can_onboard": True,
            "reserved_sources": ["PDB_APP"],
            "reserved_apcodes": ["AP123"],
            "type": "VIRTUALIZATION",
            "tags": [],
            "projected_usage": 2_300.0,
            "capacity_ceiling": 16_000.0,
            "headroom": 13_700.0,
        },
    ]
    first_candidate, second_candidate = MagicMock(), MagicMock()
    first_candidate.to_json.return_value = candidates[0]
    second_candidate.to_json.return_value = candidates[1]

    mock_core.engine_service.find_onboarding_candidates.return_value = [
        first_candidate,
        second_candidate,
    ]

    with patch("api.controllers.engine_controller.get_core", return_value=mock_core):
        response, status_code = engine_controller.list_engine_onboarding_candidates(
            business_unit="BU-1",
            dsource_size=100,
            source_name="PDB_APP",
            ap_code="AP123",
        )

        mock_core.engine_service.find_onboarding_candidates.assert_called_once_with(
            business_unit="BU-1",
            dsource_size=100,
            source_name="PDB_APP",
            ap_code="AP123",
        )
        assert response == {"engines": candidates, "count": 2}
        assert status_code == 200


@pytest.mark.unit
def test_list_engine_onboarding_candidates_returns_empty_list(mock_core):
    mock_core.engine_service.find_onboarding_candidates.return_value = []

    with patch("api.controllers.engine_controller.get_core", return_value=mock_core):
        response, status_code = engine_controller.list_engine_onboarding_candidates(
            business_unit="BU-1",
            dsource_size=100,
            source_name="PDB_APP",
            ap_code="AP123",
        )

        assert response == {"engines": [], "count": 0}
        assert status_code == 200


@pytest.mark.unit
@pytest.mark.parametrize(
    "error_message",
    [
        "Failed to fetch engine capacity from DCT: boom",
        "Engine 'engine-id-1' (external_id='48') has no capacity entry in DCT",
    ],
)
def test_list_engine_onboarding_candidates_but_service_error(mock_core, error_message):
    mock_core.engine_service.find_onboarding_candidates.side_effect = (
        EngineServiceError(error_message)
    )

    with patch("api.controllers.engine_controller.get_core", return_value=mock_core):
        with pytest.raises(HTTPException) as exc_info:
            engine_controller.list_engine_onboarding_candidates(
                business_unit="BU-1",
                dsource_size=100,
                source_name="PDB_APP",
                ap_code="AP123",
            )

        assert exc_info.value.code == 500


@pytest.mark.unit
@patch(
    "api.controllers.engine_controller.get_core",
    side_effect=Exception("Unexpected Error"),
)
def test_list_engine_onboarding_candidates_but_unexpected_failure(mock_core):
    with pytest.raises(HTTPException) as exc_info:
        engine_controller.list_engine_onboarding_candidates(
            business_unit="BU-1",
            dsource_size=100,
            source_name="PDB_APP",
            ap_code="AP123",
        )
    assert exc_info.value.code == 500
