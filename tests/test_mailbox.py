from __future__ import annotations

import asyncio

import pytest

from oblivion_bridge.mailbox import MailboxBridge
from tests.fake_consumer import FakeMailboxConsumer


@pytest.mark.asyncio
async def test_simultaneous_callers_enter_mailbox_in_fifo_order(tmp_path) -> None:
    bridge = MailboxBridge(
        tmp_path,
        timeout_seconds=2,
        poll_interval_seconds=0.005,
    )

    async with FakeMailboxConsumer(
        tmp_path,
        command_delay_seconds=0.02,
    ) as consumer:
        first = asyncio.create_task(bridge.execute(["first"]))
        await asyncio.sleep(0)
        second = asyncio.create_task(bridge.execute(["second"]))
        await asyncio.sleep(0)
        third = asyncio.create_task(bridge.execute(["third"]))

        responses = await asyncio.gather(first, second, third)

    assert consumer.received_batches == [["first"], ["second"], ["third"]]
    assert [response.status for response in responses] == [
        "completed",
        "completed",
        "completed",
    ]


@pytest.mark.asyncio
async def test_empty_console_output_is_success(tmp_path) -> None:
    bridge = MailboxBridge(
        tmp_path,
        timeout_seconds=1,
        poll_interval_seconds=0.005,
    )

    async with FakeMailboxConsumer(tmp_path):
        response = await bridge.execute(["player.additem 0000000F 100"])

    assert response.status == "completed"
    assert response.results[0].status == "executed"
    assert response.results[0].console_output == ""
