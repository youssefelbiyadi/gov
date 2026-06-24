"""Subscription payload factories — pure, no I/O."""
from __future__ import annotations

import os
from typing import Any


def _base_payload(*, spec: dict[str, Any], description: str) -> dict[str, Any]:
    return {
        "product": os.environ["PRODUCT"],
        "apcode": os.environ["APCODE"],
        "realm": os.environ["REALM"],
        "description": description,
        "payload": spec,
    }


def build_vdb_payload(
    *, vdb_type: str, description: str, dsource_name: str,
) -> dict[str, Any]:
    """Build the request body for POST /api/v1/subscriptions."""
    return _base_payload(
        spec={"dsource_name": dsource_name, "vdb_type": vdb_type},
        description=description,
    )
