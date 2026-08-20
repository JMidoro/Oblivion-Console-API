from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .mailbox import BridgeProtocolError, BridgeTimeoutError, MailboxBridge
from .models import (
    CommandsRequest,
    CommandsResponse,
    ErrorResponse,
    TimeoutResponse,
)
from .settings import Settings


def create_app(
    settings: Settings | None = None,
    bridge: MailboxBridge | None = None,
) -> FastAPI:
    active_settings = settings or Settings.from_environment()
    active_bridge = bridge or MailboxBridge(
        active_settings.mailbox_dir,
        timeout_seconds=active_settings.timeout_seconds,
        poll_interval_seconds=active_settings.poll_interval_seconds,
    )

    app = FastAPI(
        title="Oblivion Remastered Companion Bridge",
        version="0.1.0",
        description=(
            "Execute ordered batches of raw Oblivion console commands through "
            "a local UE4SS mailbox."
        ),
        servers=[{"url": f"http://127.0.0.1:{active_settings.port}"}],
    )

    @app.post(
        "/v1/commands",
        operation_id="oblivion_console",
        summary="Execute Oblivion console commands",
        description=(
            "Execute one or more raw Oblivion console commands in order. The "
            "HTTP request remains open until the complete batch result is "
            "available or the service times out. Commands stop after the first "
            "detected failure. Console output may be empty. Executed means "
            "dispatch completed; it does not verify the gameplay effect. A "
            "timeout does not distinguish loading, a closed game, or an "
            "unavailable game-side mod."
        ),
        response_model=CommandsResponse,
        responses={
            502: {
                "model": ErrorResponse,
                "description": "The mailbox returned an invalid response.",
            },
            504: {
                "model": TimeoutResponse,
                "description": (
                    "The complete game-side response did not arrive before "
                    "the configured deadline. No unavailable-game subtype is "
                    "reported."
                ),
            },
        },
    )
    async def execute_commands(
        request: CommandsRequest,
    ) -> CommandsResponse | JSONResponse:
        try:
            return await active_bridge.execute(request.commands)
        except BridgeTimeoutError:
            return JSONResponse(
                status_code=504,
                content=TimeoutResponse().model_dump(mode="json"),
            )
        except (BridgeProtocolError, OSError) as error:
            return JSONResponse(
                status_code=502,
                content=ErrorResponse(message=str(error)).model_dump(mode="json"),
            )

    return app


app = create_app()
