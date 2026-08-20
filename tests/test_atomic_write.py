from __future__ import annotations

import json
import os

from oblivion_bridge.mailbox import atomic_write_json


def test_atomic_write_uses_temporary_sibling_and_replace(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "request.json"
    replace_calls = []
    real_replace = os.replace

    def recording_replace(source, destination) -> None:
        replace_calls.append((source, destination))
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", recording_replace)

    atomic_write_json(target, {"command": "player.additem 0000000F 100"})

    assert replace_calls == [(tmp_path / "request.json.tmp", target)]
    assert not (tmp_path / "request.json.tmp").exists()
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "command": "player.additem 0000000F 100"
    }
