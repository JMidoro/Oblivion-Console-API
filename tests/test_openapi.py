from __future__ import annotations

import json
from pathlib import Path

from oblivion_bridge.app import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_committed_openapi_contract_is_current() -> None:
    committed_contract = json.loads(
        (PROJECT_ROOT / "docs" / "openapi.json").read_text(encoding="utf-8")
    )

    assert committed_contract == app.openapi()
    operation = committed_contract["paths"]["/v1/commands"]["post"]
    assert operation["operationId"] == "oblivion_console"
    assert set(operation["responses"]) == {"200", "502", "504", "422"}
