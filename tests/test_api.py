from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from oblivion_bridge.app import create_app
from oblivion_bridge.settings import Settings
from tests.fake_consumer import FakeMailboxConsumer


def test_request_validation_rejects_invalid_command_arrays(tmp_path) -> None:
    app = create_app(
        Settings(
            mailbox_dir=tmp_path,
            timeout_seconds=0.1,
            poll_interval_seconds=0.005,
        )
    )

    async def make_requests() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            for payload in (
                {},
                {"commands": []},
                {"commands": [123]},
                {"commands": ["tgm"], "extra": True},
            ):
                response = await client.post("/v1/commands", json=payload)
                assert response.status_code == 422

    asyncio.run(make_requests())


@pytest.mark.asyncio
async def test_single_and_batch_commands_return_complete_results(tmp_path) -> None:
    settings = Settings(
        mailbox_dir=tmp_path,
        timeout_seconds=1,
        poll_interval_seconds=0.005,
    )
    app = create_app(settings)

    async with FakeMailboxConsumer(tmp_path):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/v1/commands",
                json={"commands": ["tgm", "output:GetStage >> 20.00"]},
            )

    assert response.status_code == 200
    assert response.json() == {
        "status": "completed",
        "results": [
            {
                "command": "tgm",
                "status": "executed",
                "console_output": "",
            },
            {
                "command": "output:GetStage >> 20.00",
                "status": "executed",
                "console_output": "GetStage >> 20.00",
            },
        ],
    }


@pytest.mark.asyncio
async def test_batch_stops_on_established_failure(tmp_path) -> None:
    settings = Settings(
        mailbox_dir=tmp_path,
        timeout_seconds=1,
        poll_interval_seconds=0.005,
    )
    app = create_app(settings)

    async with FakeMailboxConsumer(tmp_path):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/v1/commands",
                json={
                    "commands": [
                        "player.additem 0000000F 100",
                        "fail:Unknown command",
                        "tgm",
                    ]
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert [result["status"] for result in body["results"]] == [
        "executed",
        "console_error",
        "unattempted",
    ]


@pytest.mark.asyncio
async def test_unavailable_consumer_returns_timeout(tmp_path) -> None:
    settings = Settings(
        mailbox_dir=tmp_path,
        timeout_seconds=0.05,
        poll_interval_seconds=0.005,
    )
    app = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/commands",
            json={"commands": ["tgm"]},
        )

    assert response.status_code == 504
    assert response.json() == {"status": "timed_out", "results": []}
    assert not (tmp_path / "request.json").exists()


@pytest.mark.asyncio
async def test_simultaneous_http_callers_complete_in_fifo_order(tmp_path) -> None:
    settings = Settings(
        mailbox_dir=tmp_path,
        timeout_seconds=2,
        poll_interval_seconds=0.005,
    )
    app = create_app(settings)

    async with FakeMailboxConsumer(
        tmp_path,
        command_delay_seconds=0.02,
    ) as consumer:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            first = asyncio.create_task(
                client.post("/v1/commands", json={"commands": ["first"]})
            )
            await asyncio.sleep(0)
            second = asyncio.create_task(
                client.post("/v1/commands", json={"commands": ["second"]})
            )
            await asyncio.sleep(0)
            third = asyncio.create_task(
                client.post("/v1/commands", json={"commands": ["third"]})
            )
            responses = await asyncio.gather(first, second, third)

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert consumer.received_batches == [["first"], ["second"], ["third"]]
