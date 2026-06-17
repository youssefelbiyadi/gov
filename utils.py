"""Subscription payload factories.

Pure — only depends on the Subscription model and env vars at call time.
"""
from __future__ import annotations

import os
from typing import Any

from coe_pylib.models import Subscription  # adjust to your real import path


def _base_payload(*, spec: dict[str, Any], description: str) -> Subscription:
    return Subscription(
        apcode=os.environ["APCODE"],
        realm=os.environ["REALM"],
        product=os.environ["PRODUCT"],
        spec=spec,
        description=description,
    )


def build_vdb_payload(
    *, vdb_type: str, description: str, dsource_name: str,
) -> Subscription:
    return _base_payload(
        spec={"dsource_name": dsource_name, "vdb_type": vdb_type},
        description=description,
    )
