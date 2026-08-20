from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from .models import CommandsResponse, MailboxRequest, MailboxResponse


class BridgeTimeoutError(TimeoutError):
    """The complete game-side response did not arrive before the deadline."""


class BridgeProtocolError(RuntimeError):
    """The game-side response did not conform to the mailbox protocol."""


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write UTF-8 JSON to a temporary sibling, then atomically replace path."""
    temporary_path = path.with_name(f"{path.name}.tmp")
    path.parent.mkdir(parents=True, exist_ok=True)

    with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(
            payload,
            handle,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(temporary_path, path)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise BridgeProtocolError(f"{path.name} must contain a JSON object")
    return value


class MailboxBridge:
    """Serialize callers through the fixed request/response filesystem mailbox."""

    def __init__(
        self,
        mailbox_dir: Path,
        *,
        timeout_seconds: float,
        poll_interval_seconds: float,
    ) -> None:
        self.mailbox_dir = mailbox_dir
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.request_path = mailbox_dir / "request.json"
        self.response_path = mailbox_dir / "response.json"
        self._mailbox_lock = asyncio.Lock()

    async def execute(self, commands: list[str]) -> CommandsResponse:
        request = MailboxRequest(
            request_id=str(uuid4()),
            commands=commands,
        )
        request_written = False

        try:
            async with asyncio.timeout(self.timeout_seconds):
                async with self._mailbox_lock:
                    self.mailbox_dir.mkdir(parents=True, exist_ok=True)
                    await self._wait_for_mailbox()

                    atomic_write_json(
                        self.request_path,
                        request.model_dump(mode="json"),
                    )
                    request_written = True

                    response = await self._wait_for_response(request)
                    return response.public_response()
        except TimeoutError as error:
            if request_written:
                self._remove_request_if_owned(request.request_id)
            raise BridgeTimeoutError from error

    async def _wait_for_mailbox(self) -> None:
        while True:
            request_exists = self.request_path.exists()
            response_exists = self.response_path.exists()

            if not request_exists and response_exists:
                # No live HTTP request can own this response. It is an orphan
                # left by a stopped or timed-out service process.
                self.response_path.unlink(missing_ok=True)
                response_exists = False

            if not request_exists and not response_exists:
                return

            await asyncio.sleep(self.poll_interval_seconds)

    async def _wait_for_response(
        self, request: MailboxRequest
    ) -> MailboxResponse:
        while True:
            if not self.response_path.exists():
                await asyncio.sleep(self.poll_interval_seconds)
                continue

            try:
                raw_response = read_json(self.response_path)
                response = MailboxResponse.model_validate(raw_response)
            except (OSError, json.JSONDecodeError, ValidationError) as error:
                self.response_path.unlink(missing_ok=True)
                raise BridgeProtocolError(
                    "The game-side response is not valid mailbox JSON"
                ) from error

            if response.request_id != request.request_id:
                self.response_path.unlink(missing_ok=True)
                await asyncio.sleep(self.poll_interval_seconds)
                continue

            self.response_path.unlink(missing_ok=True)
            self._validate_results(request, response)
            return response

    @staticmethod
    def _validate_results(
        request: MailboxRequest, response: MailboxResponse
    ) -> None:
        response_commands = [result.command for result in response.results]
        if response_commands != request.commands:
            raise BridgeProtocolError(
                "The game-side response does not match the submitted command order"
            )

    def _remove_request_if_owned(self, request_id: str) -> None:
        if not self.request_path.exists():
            return

        try:
            request_data = read_json(self.request_path)
        except (OSError, json.JSONDecodeError, BridgeProtocolError):
            return

        if request_data.get("request_id") == request_id:
            self.request_path.unlink(missing_ok=True)
