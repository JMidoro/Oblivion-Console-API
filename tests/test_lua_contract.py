from __future__ import annotations

import json
from pathlib import Path

from oblivion_bridge.models import MailboxRequest, MailboxResponse


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mailbox"


def load_fixture(name: str) -> dict[str, object]:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as handle:
        value = json.load(handle)
    assert isinstance(value, dict)
    return value


def test_completed_lua_mailbox_fixture_matches_python_contract() -> None:
    request = MailboxRequest.model_validate(load_fixture("request_batch.json"))
    response = MailboxResponse.model_validate(
        load_fixture("response_completed.json")
    )

    assert response.request_id == request.request_id
    assert [result.command for result in response.results] == request.commands
    assert [result.status for result in response.results] == [
        "executed",
        "executed",
    ]
    assert response.results[0].console_output == ""


def test_failed_lua_mailbox_fixture_marks_later_commands_unattempted() -> None:
    response = MailboxResponse.model_validate(
        load_fixture("response_failed.json")
    )

    assert response.status == "failed"
    assert [result.status for result in response.results] == [
        "executed",
        "console_error",
        "unattempted",
    ]
    assert (
        'Script command "definitely_not_a_real_command" not found.'
        in response.results[1].console_output
    )
