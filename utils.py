"""Subscription payload factories.

Pure — only depends on env vars at call time. Returns plain dicts shaped for
the orchestrator's POST /api/v1/subscriptions endpoint.
"""
from __future__ import annotations

import os
from typing import Any


def _base_vdb_payload(
    spec: dict[str, Any], description: str,
) -> dict[str, Any]:
    return {
        "apcode": os.environ["APCODE"],
        "realm": os.environ["REALM"],
        "product": os.environ["PRODUCT"],
        "product_version": "1",
        "tier": os.getenv("TIER", "D"),
        "environment": os.getenv("ENVIRONMENT", "int"),
        "payload": spec,
        "description": description,
    }


def build_vdb_payload(
    vdb_type: str, description: str, dsource_name: str,
) -> dict[str, Any]:
    params: dict[str, Any] = {"dsource_name": dsource_name, "vdb_type": vdb_type}
    if vdb_type == "MASTER":
        params["bu"] = "DELPHIX"
    return _base_vdb_payload(spec=params, description=description)
