def test_get_environment_by_id_success(self):
    environment = {"id": "env-1", "name": "ENV-1", "status": "ACTIVE"}
    self.gateway.get.return_value = environment

    result = self.service.get_environment_by_id(environment_id="env-1")

    self.gateway.get.assert_called_once_with(endpoint="environments/env-1")
    assert result == environment


def test_get_environment_by_id_wraps_gateway_error(self):
    original = Exception("boom")
    self.gateway.get.side_effect = original

    with pytest.raises(
        DelphixApiError,
        match="Failed to get environment 'env-1'",
    ) as exc_info:
        self.service.get_environment_by_id(environment_id="env-1")

    self.gateway.get.assert_called_once_with(endpoint="environments/env-1")
    assert exc_info.value.__cause__ is original


def test_refresh_environment_success(self):
    self.gateway.post.return_value = {"refresh_job_id": "job-123"}

    result = self.service.refresh_environment(environment_id="env-1")

    self.gateway.post.assert_called_once_with(
        endpoint="environments/env-1/refresh"
    )
    assert result == {"job_id": "job-123", "environment_id": "env-1"}


def test_refresh_environment_missing_job_id_maps_to_none(self):
    # response without refresh_job_id -> job_id defaults to None
    self.gateway.post.return_value = {}

    result = self.service.refresh_environment(environment_id="env-1")

    assert result == {"job_id": None, "environment_id": "env-1"}


def test_refresh_environment_wraps_gateway_error(self):
    original = Exception("boom")
    self.gateway.post.side_effect = original

    with pytest.raises(
        DelphixApiError,
        match="Failed to refresh environment 'env-1'",
    ) as exc_info:
        self.service.refresh_environment(environment_id="env-1")

    self.gateway.post.assert_called_once_with(
        endpoint="environments/env-1/refresh"
    )
    assert exc_info.value.__cause__ is original