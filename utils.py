def list_engine_onboarding_candidates(
    business_unit: str,
    dsource_size: int,
    source_name: str,
    ap_code: str,
) -> Tuple[Dict[str, Any], int]:
    """
    Lists Engines able to host a DSource for the given business unit.

    An Engine qualifies only if it is ACTIVE, opted in for onboarding,
    not reserved for another source PDB or AP-code, and has enough
    storage capacity for the DSource. Capacity telemetry is fetched
    from DCT, so this endpoint depends on DCT availability.
    """
    try:
        core = get_core(current_app)
        candidates = core.engine_service.find_onboarding_candidates(
            business_unit=business_unit,
            dsource_size=dsource_size,
            source_name=source_name,
            ap_code=ap_code,
        )
        return {
            "engines": [candidate.to_json() for candidate in candidates],
            "count": len(candidates),
        }, 200
    except EngineServiceError as e:
        logger.exception("Error while listing Engine onboarding candidates")
        abort(code=500, description=str(e))
    except Exception as e:
        logger.exception("Unexpected error on GET Engine onboarding candidates")
        abort(code=500, description=str(e))




  /engines/onboarding-candidates:
    get:
      x-openapi-router-controller: api.controllers.engine_controller
      operationId: list_engine_onboarding_candidates
      tags:
        - Engine
      summary: Retrieve Engines able to host a DSource
      description: |
        Returns ACTIVE Engines that can host a DSource of the given size for
        the given business unit. An Engine is returned only if it is opted in
        for onboarding, is not reserved for a different source PDB or AP-code,
        and satisfies the storage capacity rule below.

        Capacity rule: dsource_size * 3 + data_storage_used * 1.25 <= 0.8 * data_storage_capacity

        Capacity telemetry is fetched from DCT at read time, so this endpoint
        depends on DCT availability. Results are not paginated: the full set of
        candidates for the business unit is returned so the caller can choose.
      parameters:
        - name: business_unit
          in: query
          required: true
          schema:
            type: string
          description: Business unit the DSource belongs to
        - name: dsource_size
          in: query
          required: true
          schema:
            type: integer
            format: int64
            minimum: 0
          description: Size of the DSource to onboard, in bytes
        - name: source_name
          in: query
          required: true
          schema:
            type: string
          description: Name of the source PDB to onboard
        - name: ap_code
          in: query
          required: true
          schema:
            type: string
          description: AP-code of the application owning the DSource
      responses:
        "200":
          description: List of Engines able to host the DSource
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/EngineOnboardingCandidateListResponse"
              examples:
                success:
                  summary: List of Engine onboarding candidates
                  value:
                    engines:
                      - id: "6272819-56b5-9897-919910-6262771"
                        status: "ACTIVE"
                        external_id: "48"
                        name: "engine-1"
                        hostname: "hostname-1"
                        business_unit_group: "BP2I"
                        business_units: [ "BP2I" ]
                        can_onboard: true
                        reserved_sources: []
                        reserved_apcodes: []
                        type: "VIRTUALIZATION"
                        tags: [ { "key": "tag-name-1", "value": "tag-value-1" } ]
                        projected_usage: 224447333120
                        capacity_ceiling: 496874029056
                        headroom: 272426695936
                    count: 1
                empty:
                  summary: No Engine can host the DSource
                  value:
                    engines: []
                    count: 0
        "500":
          description: Internal server error (e.g. DCT unreachable or inconsistent)
          content:
            application/json:
              schema:
                type: object
                properties:
                  error:
                    type: string
              examples:
                dct_failure:
                  summary: DCT unreachable
                  value: { "error": "Failed to fetch engine capacity from DCT: <reason>" }
                dct_inconsistent:
                  summary: Engine has no DCT counterpart
                  value: { "error": "Engine '<id>' (external_id='<external_id>') has no capacity entry in DCT" }


    EngineOnboardingCandidate:
      allOf:
        - $ref: "#/components/schemas/Engine"
        - type: object
          description: |
            An Engine that satisfies every onboarding rule, with the computed
            capacity figures that justify its selection.
          properties:
            projected_usage:
              type: number
              format: double
              description: Projected usage after onboarding, as dsource_size * 3 + data_storage_used * 1.25.
            capacity_ceiling:
              type: number
              format: double
              description: Maximum usage allowed on the Engine, as 0.8 * data_storage_capacity.
            headroom:
              type: number
              format: double
              description: Remaining margin, as capacity_ceiling - projected_usage. Always >= 0.

    EngineOnboardingCandidateListResponse:
      type: object
      properties:
        engines:
          type: array
          description: List of Engine onboarding candidate objects.
          items:
            $ref: "#/components/schemas/EngineOnboardingCandidate"
        count:
          type: integer
          description: Number of Engines able to host the DSource.


can_onboard:
  type: boolean
  description: Whether this engine is opted in to host newly onboarded DSources.
reserved_sources:
  type: array
  items:
    type: string
  description: Source PDB names this engine is reserved for. Empty means not reserved.
reserved_apcodes:
  type: array
  items:
    type: string
  description: AP-codes this engine is reserved for. Empty means not reserved.



