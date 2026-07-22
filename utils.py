@pytest.mark.unit
def test_find_onboarding_candidates_but_missing_dct_entry(
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
    # DCT returns capacity for a DIFFERENT engine -> the eligible one is missing.
    mock_dct_client.list.return_value = [
        _dct_engine(
            external_id="some-other-engine",
            data_storage_capacity=10_000,
            data_storage_used=1_000,
        ),
    ]

    with pytest.raises(
        EngineServiceError,
        match="has no capacity entry in DCT",
    ):
        engine_service.find_onboarding_candidates(
            business_unit="BU_1",
            dsource_size=100,
            source_name="PDB_APP",
            ap_code="AP123",
        )
