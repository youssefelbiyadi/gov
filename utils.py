# =============================================================================
# delphix_core/models/engine.py  —  CHANGES ONLY
# =============================================================================
#
# Add the three onboarding attributes to the Engine mapped class, alongside the
# existing mapped_column declarations (external_id, name, hostname, ...).
#
# Rationale for the column choices:
#   - can_onboard        : plain boolean gate, non-nullable, defaults False so an
#                          engine is never accidentally eligible before it's been
#                          explicitly opted in.
#   - sources            : list of source PDB names this engine is *reserved* for.
#                          NULL / empty  => not reserved (open to any PDB).
#                          Reuses the JSONEncodedType pattern already used by
#                          business_units and tags.
#   - reserved_apcodes   : list of AP-codes this engine is reserved for.
#                          NULL / empty  => not reserved (open to any AP-code).
# -----------------------------------------------------------------------------

# --- add these imports if not already present ---
from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column


class Engine(BaseModel):  # noqa: F811  (illustrative — this is the existing class)
    # ... existing columns (external_id, name, hostname, business_unit_group,
    #     type, business_units, tags, vdbs, environments) stay unchanged ...

    can_onboard: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    sources: Mapped[Optional[List[str]]] = mapped_column(
        JSONEncodedType, nullable=True, default=list
    )

    reserved_apcodes: Mapped[Optional[List[str]]] = mapped_column(
        JSONEncodedType, nullable=True, default=list
    )

    # -------------------------------------------------------------------------
    # to_json(): add the three fields to the existing dict so the attributes are
    # serialized consistently with the rest of the model. Insert these keys into
    # the dict returned by the CURRENT to_json() — do not rewrite the method.
    # -------------------------------------------------------------------------
    def to_json(self) -> "Dict[str, Any]":
        return {
            "id": self.id,
            "status": self.status.value,
            "external_id": self.external_id,
            "name": self.name,
            "hostname": self.hostname,
            "business_unit_group": self.business_unit_group,
            "business_units": self.business_units,
            "type": self.type.value,
            "tags": self.tags,
            # --- new ---
            "can_onboard": self.can_onboard,
            "sources": self.sources,
            "reserved_apcodes": self.reserved_apcodes,
        }
        
        
        
        
# =============================================================================
# delphix_core/services/engine.py  —  ADDITIONS
# =============================================================================

from dataclasses import dataclass
from typing import Dict, List, Optional

# (existing imports: Engine, EngineCapacity, Status, EngineServiceError, etc.)


# -----------------------------------------------------------------------------
# Onboarding capacity constants
#
# Capacity rule (from the onboarding spec):
#
#       Ds * M  +  U * n   <=   THRESHOLD * C
#
#   Ds = size of the DSource to onboard (input, bytes)
#   U  = engine used capacity            (data_storage_used, from DCT)
#   C  = engine global storage capacity  (data_storage_capacity, from DCT)
#   M  = storage multiplier applied to the incoming DSource
#   n  = safety factor applied to current usage
#   THRESHOLD = fraction of C we allow ourselves to fill
# -----------------------------------------------------------------------------
STORAGE_MULTIPLIER: int = 3       # M
USAGE_FACTOR: float = 1.25        # n
CAPACITY_THRESHOLD: float = 0.8   # 80% ceiling


# -----------------------------------------------------------------------------
# Result type
#
# We return a small, immutable DTO rather than a bare Engine so the API layer
# can rank candidates (e.g. pick the one with the most headroom) without
# recomputing the capacity math. Only engines that pass ALL rules are returned.
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class EngineOnboardingCandidate:
    engine: Engine
    projected_usage: float   # Ds * M + U * n
    capacity_ceiling: float  # THRESHOLD * C
    headroom: float          # capacity_ceiling - projected_usage  (>= 0 here)

    def to_json(self) -> Dict[str, "Any"]:
        return {
            **self.engine.to_json(),
            "projected_usage": self.projected_usage,
            "capacity_ceiling": self.capacity_ceiling,
            "headroom": self.headroom,
        }


class EngineService(EngineServiceInterface, SessionManagerMixin):  # existing class
    # ... existing methods (list_capacity_reports, _fetch_capacity_by_id,
    #     _get_capacity, update, ...) stay unchanged ...

    # -------------------------------------------------------------------------
    # Public: find engines that can host a DSource for a given business unit.
    # -------------------------------------------------------------------------
    def find_onboarding_candidates(
        self,
        business_unit: str,
        dsource_size: int,
        source_name: str,
        ap_code: str,
    ) -> List[EngineOnboardingCandidate]:
        """
        Return the engines able to host a DSource of size ``dsource_size`` for
        the business unit ``business_unit``.

        An engine qualifies only if it passes, in order:
          1. can_onboard is True
          2. it is not reserved for a *different* source PDB
             (sources empty  => open; else source_name must be in sources)
          3. it is not reserved for a *different* AP-code
             (reserved_apcodes empty => open; else ap_code must be in them)
          4. the capacity check holds:
                 Ds * M + U * n <= THRESHOLD * C
             using live U / C fetched from DCT.

        Capacity telemetry is fetched from DCT only for the engines that already
        survived rules 1-3, so a fully-filtered request never hits DCT.
        """
        # Filter by BU + ACTIVE at the DB level (same pattern as
        # list_capacity_reports). business_units is a JSON list column, so we
        # match membership rather than equality.
        effective_filters = [
            Engine.status == Status.ACTIVE,
            Engine.business_units.contains(business_unit),
        ]
        engines = self.list(filters=effective_filters)

        # Rules 1-3: pure in-memory eligibility, no I/O.
        eligible = [
            engine
            for engine in engines
            if self._is_eligible_for_onboarding(engine, source_name, ap_code)
        ]

        if not eligible:
            return []

        # Rule 4: fetch capacity once, only now, and only match survivors.
        capacity_data = self._fetch_capacity_by_id()

        candidates: List[EngineOnboardingCandidate] = []
        for engine in eligible:
            capacity = capacity_data.get(engine.external_id)
            if capacity is None:
                # Engine present in DB but with no DCT counterpart: it cannot be
                # sized, so it cannot be a hosting candidate. Skip silently.
                continue

            candidate = self._evaluate_capacity(engine, capacity, dsource_size)
            if candidate is not None:
                candidates.append(candidate)

        return candidates

    # -------------------------------------------------------------------------
    # Rules 1-3 — pure predicate, trivially unit-testable.
    # -------------------------------------------------------------------------
    @staticmethod
    def _is_eligible_for_onboarding(
        engine: Engine,
        source_name: str,
        ap_code: str,
    ) -> bool:
        # Rule 1
        if not engine.can_onboard:
            return False

        # Rule 2 — reserved for specific source PDBs?
        if engine.sources and source_name not in engine.sources:
            return False

        # Rule 3 — reserved for specific AP-codes?
        if engine.reserved_apcodes and ap_code not in engine.reserved_apcodes:
            return False

        return True

    # -------------------------------------------------------------------------
    # Rule 4 — capacity math. Returns a candidate if it fits, else None.
    # Pure given (engine, capacity, dsource_size): no I/O, easy to test.
    # -------------------------------------------------------------------------
    @staticmethod
    def _evaluate_capacity(
        engine: Engine,
        capacity: EngineCapacity,
        dsource_size: int,
    ) -> Optional[EngineOnboardingCandidate]:
        projected_usage = (
            dsource_size * STORAGE_MULTIPLIER
            + capacity.data_storage_used * USAGE_FACTOR
        )
        capacity_ceiling = CAPACITY_THRESHOLD * capacity.data_storage_capacity

        if projected_usage > capacity_ceiling:
            return None

        return EngineOnboardingCandidate(
            engine=engine,
            projected_usage=projected_usage,
            capacity_ceiling=capacity_ceiling,
            headroom=capacity_ceiling - projected_usage,
        )
        
        
# =============================================================================
# tests for the onboarding logic — pure, no HTTP/DB mocking needed
# =============================================================================
import pytest

from delphix_core.models.engine import Engine, EngineCapacity
from delphix_core.services.engine import (
    EngineService,
    EngineOnboardingCandidate,
    STORAGE_MULTIPLIER,
    USAGE_FACTOR,
    CAPACITY_THRESHOLD,
)


def make_engine(**overrides) -> Engine:
    defaults = dict(
        can_onboard=True,
        sources=None,
        reserved_apcodes=None,
    )
    defaults.update(overrides)
    e = Engine.__new__(Engine)          # skip SQLAlchemy __init__
    for k, v in defaults.items():
        setattr(e, k, v)
    return e


# ---- Rules 1-3 ---------------------------------------------------------------

def test_rule1_can_onboard_false_is_rejected():
    e = make_engine(can_onboard=False)
    assert EngineService._is_eligible_for_onboarding(e, "PDB1", "AP1") is False


def test_rule2_reserved_for_other_source_is_rejected():
    e = make_engine(sources=["PDB_OTHER"])
    assert EngineService._is_eligible_for_onboarding(e, "PDB1", "AP1") is False


def test_rule2_reserved_for_this_source_passes():
    e = make_engine(sources=["PDB1"])
    assert EngineService._is_eligible_for_onboarding(e, "PDB1", "AP1") is True


def test_rule2_empty_sources_is_open():
    for empty in (None, []):
        e = make_engine(sources=empty)
        assert EngineService._is_eligible_for_onboarding(e, "PDB1", "AP1") is True


def test_rule3_reserved_for_other_apcode_is_rejected():
    e = make_engine(reserved_apcodes=["AP_OTHER"])
    assert EngineService._is_eligible_for_onboarding(e, "PDB1", "AP1") is False


def test_rule3_empty_apcodes_is_open():
    e = make_engine(reserved_apcodes=[])
    assert EngineService._is_eligible_for_onboarding(e, "PDB1", "AP1") is True


# ---- Rule 4 (capacity) -------------------------------------------------------

def test_capacity_fits_exactly_at_ceiling():
    # Ds*M + U*n == 0.8*C  -> must fit (<=)
    C = 1000
    U = 0
    # Ds*3 = 0.8*1000 = 800  -> Ds = 266.67; use Ds so that it's exactly 800
    Ds = 800 // STORAGE_MULTIPLIER  # 266
    cap = EngineCapacity(data_storage_capacity=C, data_storage_used=U)
    e = make_engine()
    result = EngineService._evaluate_capacity(e, cap, Ds)
    assert result is not None
    assert result.capacity_ceiling == CAPACITY_THRESHOLD * C


def test_capacity_exceeds_ceiling_returns_none():
    cap = EngineCapacity(data_storage_capacity=1000, data_storage_used=900)
    e = make_engine()
    # U*n = 900*1.25 = 1125 already > 0.8*1000 = 800
    assert EngineService._evaluate_capacity(e, cap, 0) is None


def test_candidate_headroom_is_positive_and_correct():
    C, U, Ds = 10_000, 1_000, 100
    cap = EngineCapacity(data_storage_capacity=C, data_storage_used=U)
    e = make_engine()
    result = EngineService._evaluate_capacity(e, cap, Ds)
    expected_projected = Ds * STORAGE_MULTIPLIER + U * USAGE_FACTOR
    expected_ceiling = CAPACITY_THRESHOLD * C
    assert result.projected_usage == expected_projected
    assert result.headroom == expected_ceiling - expected_projected
    assert result.headroom >= 0