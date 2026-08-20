from __future__ import annotations

import argparse
import asyncio
import json
import socket

import httpx
import uvicorn

from oblivion_bridge.app import create_app
from oblivion_bridge.settings import Settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a temporary bridge server, submit one live HTTP batch, "
            "print its response, and stop the server."
        )
    )
    parser.add_argument(
        "commands",
        nargs="+",
        help="Raw Oblivion console commands in execution order.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Complete HTTP/mailbox deadline in seconds (default: 15).",
    )
    return parser.parse_args()


async def run(commands: list[str], timeout_seconds: float) -> int:
    environment = Settings.from_environment()
    settings = Settings(
        mailbox_dir=environment.mailbox_dir,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=environment.poll_interval_seconds,
        port=environment.port,
    )
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(2048)
    listener.setblocking(False)
    temporary_port = listener.getsockname()[1]

    server = uvicorn.Server(
        uvicorn.Config(
            create_app(settings),
            host="127.0.0.1",
            port=temporary_port,
            log_level="warning",
            access_log=False,
        )
    )
    server_task = asyncio.create_task(server.serve(sockets=[listener]))

    try:
        async with asyncio.timeout(5):
            while not server.started:
                if server_task.done():
                    await server_task
                    raise RuntimeError("The temporary HTTP server stopped early")
                await asyncio.sleep(0.01)

        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{temporary_port}",
            timeout=timeout_seconds + 2,
        ) as client:
            response = await client.post(
                "/v1/commands",
                json={"commands": commands},
            )

        print(
            json.dumps(
                {
                    "temporary_port": temporary_port,
                    "http_status": response.status_code,
                    "body": response.json(),
                },
                indent=2,
            )
        )
        return 0 if response.status_code == 200 else 1
    finally:
        server.should_exit = True
        try:
            async with asyncio.timeout(5):
                await server_task
        except TimeoutError:
            server_task.cancel()
            await asyncio.gather(server_task, return_exceptions=True)
        listener.close()


def main() -> None:
    args = parse_args()
    if args.timeout <= 0:
        raise SystemExit("--timeout must be greater than zero")
    raise SystemExit(asyncio.run(run(args.commands, args.timeout)))


if __name__ == "__main__":
    main()
