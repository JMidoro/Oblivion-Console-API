from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


PROTOCOL_VERSION = 1

CommandStatus = Literal[
    "executed",
    "console_error",
    "bridge_error",
    "unattempted",
]
BatchStatus = Literal["completed", "failed"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CommandsRequest(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "commands": [
                        "player.additem 0000000F 100",
                        "tgm",
                    ]
                }
            ]
        },
    )

    commands: Annotated[
        list[str],
        Field(
            min_length=1,
            description="Raw Oblivion console commands in execution order.",
        ),
    ]


class CommandResult(StrictModel):
    command: str = Field(description="The submitted command.")
    status: CommandStatus = Field(
        description=(
            "What the bridge established about this command. Executed means "
            "dispatch completed; it does not verify the gameplay effect."
        )
    )
    console_output: str = Field(
        description=(
            "Text captured from the Oblivion console. An empty string is valid."
        )
    )


class CommandsResponse(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "status": "completed",
                    "results": [
                        {
                            "command": "player.additem 0000000F 100",
                            "status": "executed",
                            "console_output": "",
                        }
                    ],
                }
            ]
        },
    )

    status: BatchStatus
    results: list[CommandResult]


class TimeoutResponse(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={
            "examples": [{"status": "timed_out", "results": []}]
        },
    )

    status: Literal["timed_out"] = "timed_out"
    results: list[CommandResult] = Field(default_factory=list)


class ErrorResponse(StrictModel):
    status: Literal["bridge_error"] = "bridge_error"
    message: str


class MailboxRequest(StrictModel):
    protocol_version: Literal[1] = PROTOCOL_VERSION
    request_id: str
    commands: Annotated[list[str], Field(min_length=1)]


class MailboxResponse(StrictModel):
    protocol_version: Literal[1] = PROTOCOL_VERSION
    request_id: str
    status: BatchStatus
    results: list[CommandResult]

    def public_response(self) -> CommandsResponse:
        return CommandsResponse(status=self.status, results=self.results)
