####### client.py

"""HTTP client for the orchestrator API."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import requests

from delphix_e2e.models import (
    Demand, DemandStatus, Subscription, WriteResponse,
)

from .auth import resolve_token
from .errors import (
    DemandFailedError, OrchestratorHTTPError, OrchestratorTimeoutError,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 30
_DEFAULT_POLL_INTERVAL_S = 30


@dataclass
class OrchestratorClient:
    """Typed client for the orchestrator REST API."""
    session: requests.Session
    base_url: str

    # ─── Factories ─────────────────────────────────────────────────────────

    @classmethod
    def from_token(
        cls, base_url: str, token: str, session: requests.Session | None = None,
    ) -> "OrchestratorClient":
        """Build a client from a pre-acquired token."""
        session = session or requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        return cls(session=session, base_url=base_url.rstrip("/"))

    @classmethod
    def from_env(
        cls, base_url: str, session: requests.Session | None = None,
    ) -> "OrchestratorClient":
        """Build a client by resolving credentials from the environment.

        Reads ORCV2_BEARER_TOKEN first, falls back to ORCV2_USERNAME +
        ORCV2_PASSWORD for password auth.
        """
        session = session or requests.Session()
        token = resolve_token(base_url, session=session)
        return cls.from_token(base_url, token, session=session)

    # ─── Subscriptions ─────────────────────────────────────────────────────

    def create_subscription(self, payload: dict[str, Any]) -> WriteResponse:
        data = self._post("/api/v1/subscriptions", json=payload)
        return WriteResponse.from_dict(data)

    def get_subscription(self, subscription_id: UUID | str) -> Subscription:
        data = self._get(f"/api/v1/subscriptions/{subscription_id}")
        return Subscription.from_dict(data)

    def delete_subscription(
        self, subscription_id: UUID | str, body: dict[str, Any] | None = None,
    ) -> WriteResponse:
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
        data = self._post(
            f"/api/v1/subscriptions/{subscription_id}/action/{action}",
            json={"payload": payload or {}},
        )
        return WriteResponse.from_dict(data)

    # ─── Demands ───────────────────────────────────────────────────────────

    def list_subscription_demands(
        self, subscription_id: UUID | str,
    ) -> list[Demand]:
        data = self._get(f"/api/v1/subscriptions/{subscription_id}/demands")
        return [Demand.from_dict(d) for d in data.get("demands", [])]

    def get_demand(self, demand_id: UUID | str) -> Demand:
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
        """Poll a demand until it reaches `target` or a terminal failure."""
        deadline = time.monotonic() + timeout_s
        while True:
            demand = self.get_demand(demand_id)

            if demand.status == target:
                logger.info("Demand %s reached %s", demand_id, target.value)
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

###### auth.py

"""Token acquisition and resolution for the orchestrator API."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import requests

from .errors import OrchestratorAuthError

logger = logging.getLogger(__name__)

# Env var names — kept here so they're discoverable from one place.
TOKEN_ENV_VAR = "ORCV2_BEARER_TOKEN"
USERNAME_ENV_VAR = "ORCV2_USERNAME"
PASSWORD_ENV_VAR = "ORCV2_PASSWORD"


@dataclass(frozen=True)
class TokenProvider:
    """Acquires a bearer token from POST /auth/token.

    Use directly when you have credentials in hand. For environment-driven
    resolution, use `resolve_token` instead.
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

        logger.info("Acquired orchestrator bearer token via password auth")
        return token


def resolve_token(
    base_url: str, session: requests.Session | None = None,
) -> str:
    """Resolve a bearer token from the environment.

    Precedence:
        1. ORCV2_BEARER_TOKEN — pre-acquired token (the CI default).
        2. ORCV2_USERNAME + ORCV2_PASSWORD — password auth (local dev fallback).

    Raises:
        OrchestratorAuthError: when neither path yields a token.
    """
    if token := os.getenv(TOKEN_ENV_VAR):
        logger.info("Using orchestrator token from %s", TOKEN_ENV_VAR)
        return token

    username = os.getenv(USERNAME_ENV_VAR)
    password = os.getenv(PASSWORD_ENV_VAR)
    if username and password:
        provider = TokenProvider(
            base_url=base_url,
            username=username,
            password=password,
            session=session or requests.Session(),
        )
        return provider.acquire()

    raise OrchestratorAuthError(
        f"No credentials: set {TOKEN_ENV_VAR}, or both "
        f"{USERNAME_ENV_VAR} and {PASSWORD_ENV_VAR}"
    )

##### __init__

"""Orchestrator HTTP adapter."""
from .auth import (
    PASSWORD_ENV_VAR,
    TOKEN_ENV_VAR,
    TokenProvider,
    USERNAME_ENV_VAR,
    resolve_token,
)
from .client import OrchestratorClient
from .errors import (
    DemandFailedError,
    OrchestratorAuthError,
    OrchestratorError,
    OrchestratorHTTPError,
    OrchestratorTimeoutError,
)

__all__ = [
    "DemandFailedError",
    "OrchestratorAuthError",
    "OrchestratorClient",
    "OrchestratorError",
    "OrchestratorHTTPError",
    "OrchestratorTimeoutError",
    "PASSWORD_ENV_VAR",
    "TOKEN_ENV_VAR",
    "TokenProvider",
    "USERNAME_ENV_VAR",
    "resolve_token",
]

