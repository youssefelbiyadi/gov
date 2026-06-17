"""JSON-backed state shared across CI stages via the vdb_state.json artifact."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("vdb_state.json")


def load(path: Path = DEFAULT_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save(state: dict[str, Any], path: Path = DEFAULT_PATH) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True))
