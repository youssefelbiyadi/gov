# errors.py
"""Centralized constants — timeouts, action names, state keys."""
from __future__ import annotations

"""Exception hierarchy for the orchestrator client."""
from __future__ import annotations


class OrchestratorError(Exception):
    """Base class for all orchestrator client errors."""


class OrchestratorAuthError(OrchestratorError):
    """Authentication failed or token is invalid."""


class OrchestratorHTTPError(OrchestratorError):
    """HTTP request returned a non-success status."""

    def __init__(self, status_code: int, message: str, body: str = ""):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.body = body


class OrchestratorTimeoutError(OrchestratorError):
    """A polling operation exceeded its timeout."""


class DemandFailedError(OrchestratorError):
    """A demand reached a terminal failure status (ON_ERROR/DECLINED/CANCELED)."""

    def __init__(self, demand_id: str, status: str, reason: str | None = None):
        msg = f"Demand {demand_id} failed with status={status}"
        if reason:
            msg += f" reason={reason}"
        super().__init__(msg)
        self.demand_id = demand_id
        self.status = status
        self.reason = reason


# models.py

"""Dataclass models for orchestrator entities.

These mirror the API response shapes. Only the fields we actually use are
declared; unknown fields in responses are ignored gracefully.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID


class SubscriptionStatus(str, Enum):
    """Subscription lifecycle statuses."""
    PENDING = "PENDING"
    CREATING = "CREATING"
    ACTIVE = "ACTIVE"
    UPDATING = "UPDATING"
    TERMINATING = "TERMINATING"
    TERMINATED = "TERMINATED"
    FAILED = "FAILED"


class DemandStatus(str, Enum):
    """Demand lifecycle statuses."""
    ON_HOLD = "ON_HOLD"
    IN_PROGRESS = "IN_PROGRESS"
    ON_ERROR = "ON_ERROR"
    CANCELED = "CANCELED"
    DECLINED = "DECLINED"
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_DEMAND_STATUSES

    @property
    def is_failure(self) -> bool:
        return self in _FAILURE_DEMAND_STATUSES


_TERMINAL_DEMAND_STATUSES = frozenset({
    DemandStatus.SUCCESS, DemandStatus.SKIPPED,
    DemandStatus.ON_ERROR, DemandStatus.CANCELED, DemandStatus.DECLINED,
})
_FAILURE_DEMAND_STATUSES = frozenset({
    DemandStatus.ON_ERROR, DemandStatus.CANCELED, DemandStatus.DECLINED,
})


@dataclass(frozen=True)
class Subscription:
    """Subscription as returned by GET /subscriptions/{id}.

    The `demands` field is NOT populated on this endpoint — fetch demands
    separately via OrchestratorClient.list_subscription_demands.
    """
    uuid: UUID
    name: str
    status: SubscriptionStatus
    product: str
    apcode: str
    realm: str
    description: str | None = None
    product_version: str | None = None
    product_service: str | None = None
    region: str | None = None
    environment: str | None = None
    tier: str | None = None
    parent_subscription_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def id(self) -> UUID:
        """Alias for uuid — matches the COE lib field name."""
        return self.uuid

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Subscription":
        return cls(
            uuid=UUID(data["uuid"]),
            name=data["name"],
            status=SubscriptionStatus(data["status"]),
            product=data["product"],
            apcode=data["apcode"],
            realm=data["realm"],
            description=data.get("description"),
            product_version=data.get("product_version"),
            product_service=data.get("product_service"),
            region=data.get("region"),
            environment=data.get("environment"),
            tier=data.get("tier"),
            parent_subscription_id=data.get("parent_subscription_id"),
            raw=data,
        )


@dataclass(frozen=True)
class Demand:
    """A demand (workflow execution) attached to a subscription."""
    uuid: UUID
    action: str
    status: DemandStatus
    subscription_id: UUID
    status_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def id(self) -> UUID:
        return self.uuid

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Demand":
        return cls(
            uuid=UUID(data["uuid"]),
            action=data["action"],
            status=DemandStatus(data["status"]),
            subscription_id=UUID(data["subscription_id"]),
            status_reason=data.get("status_reason"),
            raw=data,
        )


@dataclass(frozen=True)
class WriteResponse:
    """Envelope returned by create / action / delete operations."""
    subscription_id: UUID
    demand_id: UUID
    action: str
    product: str
    product_version: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WriteResponse":
        return cls(
            subscription_id=UUID(data["subscription_id"]),
            demand_id=UUID(data["demand_id"]),
            action=data["action"],
            product=data["product"],
            product_version=data["product_version"],
        )

##### auth.py

"""Token acquisition for the orchestrator API.

Kept separate from the client so it can be swapped (e.g. when moving from
password auth to a service-account token managed elsewhere).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from .errors import OrchestratorAuthError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenProvider:
    """Acquires a bearer token from POST /auth/token.

    For long-running sessions, wrap this in a refresh layer; for E2E test
    suites that complete within token lifetime, one acquisition at start is
    sufficient.
    """
    base_url: str
    username: str
    password: str
    session: requests.Session

    def acquire(self) -> str:
        url = f"{self.base_url}/auth/token"
        try:
            response = self.session.post(
                url,
                json={"username": self.username, "password": self.password},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise OrchestratorAuthError(f"Auth request failed: {exc}") from exc

        if response.status_code != 200:
            raise OrchestratorAuthError(
                f"Auth returned HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            token = response.json()["access_token"]
        except (KeyError, ValueError) as exc:
            raise OrchestratorAuthError(
                f"Auth response missing access_token: {response.text[:200]}"
            ) from exc

        logger.info("Acquired orchestrator bearer token")
        return token

######## orchestrator/client.py

"""HTTP client for the orchestrator API.

Designed as a thin, typed wrapper — no caching, no retry logic, no business
logic. Higher layers (helpers) compose these calls into idempotent operations.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import requests

from .errors import (
    DemandFailedError, OrchestratorHTTPError, OrchestratorTimeoutError,
)
from .models import Demand, DemandStatus, Subscription, WriteResponse

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 30
_DEFAULT_POLL_INTERVAL_S = 30


@dataclass
class OrchestratorClient:
    """Typed client for the orchestrator REST API.

    Use the factory `from_credentials` for password auth, or construct directly
    with a pre-acquired token via `from_token`.
    """
    session: requests.Session
    base_url: str

    # ─── Factories ─────────────────────────────────────────────────────────

    @classmethod
    def from_token(
        cls, base_url: str, token: str, session: requests.Session | None = None,
    ) -> "OrchestratorClient":
        session = session or requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        return cls(session=session, base_url=base_url.rstrip("/"))

    # ─── Subscriptions ─────────────────────────────────────────────────────

    def create_subscription(self, payload: dict[str, Any]) -> WriteResponse:
        """POST /api/v1/subscriptions"""
        data = self._post("/api/v1/subscriptions", json=payload)
        return WriteResponse.from_dict(data)

    def get_subscription(self, subscription_id: UUID | str) -> Subscription:
        """GET /api/v1/subscriptions/{id}"""
        data = self._get(f"/api/v1/subscriptions/{subscription_id}")
        return Subscription.from_dict(data)

    def delete_subscription(
        self, subscription_id: UUID | str, body: dict[str, Any] | None = None,
    ) -> WriteResponse:
        """DELETE /api/v1/subscriptions/{id}"""
        data = self._delete(
            f"/api/v1/subscriptions/{subscription_id}",
            json=body or {"payload": {}},
        )
        return WriteResponse.from_dict(data)

    def apply_action(
        self,
        subscription_id: UUID | str,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> WriteResponse:
        """POST /api/v1/subscriptions/{id}/action/{action}"""
        data = self._post(
            f"/api/v1/subscriptions/{subscription_id}/action/{action}",
            json={"payload": payload or {}},
        )
        return WriteResponse.from_dict(data)

    # ─── Demands ───────────────────────────────────────────────────────────

    def list_subscription_demands(
        self, subscription_id: UUID | str,
    ) -> list[Demand]:
        """GET /api/v1/subscriptions/{id}/demands"""
        data = self._get(f"/api/v1/subscriptions/{subscription_id}/demands")
        return [Demand.from_dict(d) for d in data.get("demands", [])]

    def get_demand(self, demand_id: UUID | str) -> Demand:
        """GET /api/v1/demands/{demand_id}"""
        data = self._get(f"/api/v1/demands/{demand_id}")
        return Demand.from_dict(data)

    def wait_for_demand(
        self,
        demand_id: UUID | str,
        *,
        target: DemandStatus = DemandStatus.SUCCESS,
        timeout_s: int,
        poll_interval_s: int = _DEFAULT_POLL_INTERVAL_S,
    ) -> Demand:
        """Poll a demand until it reaches `target` or a terminal failure.

        Raises:
            DemandFailedError: demand reached a terminal failure status.
            OrchestratorTimeoutError: target not reached within `timeout_s`.
        """
        deadline = time.monotonic() + timeout_s
        while True:
            demand = self.get_demand(demand_id)

            if demand.status == target:
                logger.info("Demand %s reached %s", demand_id, target)
                return demand

            if demand.status.is_failure:
                raise DemandFailedError(
                    str(demand_id), demand.status.value, demand.status_reason,
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OrchestratorTimeoutError(
                    f"Demand {demand_id} did not reach {target.value} within "
                    f"{timeout_s}s (last status: {demand.status.value})"
                )

            sleep_for = min(poll_interval_s, remaining)
            logger.debug(
                "Demand %s status=%s — sleeping %ds (remaining %ds)",
                demand_id, demand.status.value, sleep_for, int(remaining),
            )
            time.sleep(sleep_for)

    # ─── HTTP plumbing ─────────────────────────────────────────────────────

    def _get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def _post(self, path: str, *, json: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, json=json)

    def _delete(self, path: str, *, json: dict[str, Any]) -> dict[str, Any]:
        return self._request("DELETE", path, json=json)

    def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(
                method, url, json=json, timeout=_DEFAULT_TIMEOUT_S,
            )
        except requests.RequestException as exc:
            raise OrchestratorHTTPError(0, f"Request failed: {exc}") from exc

        if not response.ok:
            raise OrchestratorHTTPError(
                response.status_code,
                f"{method} {path} failed",
                body=response.text[:500],
            )

        try:
            return response.json()
        except ValueError as exc:
            raise OrchestratorHTTPError(
                response.status_code,
                f"{method} {path} returned non-JSON",
                body=response.text[:500],
            ) from exc


#### __init__.py

"""Public interface of the orchestrator adapter."""
from .auth import TokenProvider
from .client import OrchestratorClient
from .errors import (
    DemandFailedError,
    OrchestratorAuthError,
    OrchestratorError,
    OrchestratorHTTPError,
    OrchestratorTimeoutError,
)
from .models import Demand, DemandStatus, Subscription, SubscriptionStatus, WriteResponse

__all__ = [
    "Demand",
    "DemandFailedError",
    "DemandStatus",
    "OrchestratorAuthError",
    "OrchestratorClient",
    "OrchestratorError",
    "OrchestratorHTTPError",
    "OrchestratorTimeoutError",
    "Subscription",
    "SubscriptionStatus",
    "TokenProvider",
    "WriteResponse",
]


