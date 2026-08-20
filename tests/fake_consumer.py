from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Any

from oblivion_bridge.mailbox import atomic_write_json, read_json
from oblivion_bridge.models import PROTOCOL_VERSION


class FakeMailboxConsumer:
    def __init__(
        self,
        mailbox_dir: Path,
        *,
        poll_interval_seconds: float = 0.005,
        command_delay_seconds: float = 0,
    ) -> None:
        self.mailbox_dir = mailbox_dir
        self.request_path = mailbox_dir / "request.json"
        self.response_path = mailbox_dir / "response.json"
        self.poll_interval_seconds = poll_interval_seconds
        self.command_delay_seconds = command_delay_seconds
        self.received_batches: list[list[str]] = []
        self._task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> FakeMailboxConsumer:
        self.mailbox_dir.mkdir(parents=True, exist_ok=True)
        self._task = asyncio.create_task(self._run())
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run(self) -> None:
        last_request_id: str | None = None
        while True:
            if not self.request_path.exists():
                await asyncio.sleep(self.poll_interval_seconds)
                continue

            request = read_json(self.request_path)
            request_id = request["request_id"]
            if request_id == last_request_id:
                await asyncio.sleep(self.poll_interval_seconds)
                continue

            last_request_id = request_id
            commands = request["commands"]
            self.received_batches.append(commands)
            response = await self._execute(request_id, commands)
            atomic_write_json(self.response_path, response)
            self.request_path.unlink(missing_ok=True)

    async def _execute(
        self, request_id: str, commands: list[str]
    ) -> dict[str, Any]:
        results: list[dict[str, str]] = []
        failed = False

        for command in commands:
            if self.command_delay_seconds:
                await asyncio.sleep(self.command_delay_seconds)

            if failed:
                results.append(
                    {
                        "command": command,
                        "status": "unattempted",
                        "console_output": "",
                    }
                )
            elif command.startswith("fail:"):
                failed = True
                results.append(
                    {
                        "command": command,
                        "status": "console_error",
                        "console_output": command.removeprefix("fail:"),
                    }
                )
            else:
                output = command.removeprefix("output:")
                if output == command:
                    output = ""
                results.append(
                    {
                        "command": command,
                        "status": "executed",
                        "console_output": output,
                    }
                )

        return {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": request_id,
            "status": "failed" if failed else "completed",
            "results": results,
        }
