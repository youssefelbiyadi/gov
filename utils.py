def get_dlx_engine_for_onboarding(
    self, bu: str, dsource_size: int, source_name: str, ap_code: str
) -> dict[str, Any]:
    """
    Get a Delphix engine able to host a DSource for the given business unit.

    Business units are synced first so the candidate selection runs against
    up-to-date BU membership. Among the returned candidates, the one with the
    largest headroom (remaining margin under the capacity ceiling after this
    DSource lands) is selected.

    Args:
        bu: a string representing the business unit
        dsource_size: size of the DSource to onboard, in bytes
        source_name: name of the source PDB to onboard
        ap_code: AP-code of the application owning the DSource
    Returns: the selected engine as dict.
    """
    self._delphix.post(endpoint="/engines/sync-business-units")
    response = self._delphix.list(
        endpoint="engines/onboarding-candidates",
        payload={
            "business_unit": bu,
            "dsource_size": dsource_size,
            "source_name": source_name,
            "ap_code": ap_code,
        },
    )
    candidates = response.get("engines", [])
    if not candidates:
        raise ValueError(
            f"No engine can host a DSource of size {dsource_size} "
            f"for business unit '{bu}'"
        )
    return max(candidates, key=lambda candidate: candidate.get("headroom", 0))
