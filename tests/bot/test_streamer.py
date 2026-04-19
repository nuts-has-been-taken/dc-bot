from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent.events import AgentEvent, AgentEventType
from src.bot.streamer import DiscordStreamer


@pytest.mark.asyncio
async def test_streamer_sends_one_message_for_short_content():
    channel = MagicMock()
    first = MagicMock()
    first.edit = AsyncMock()
    channel.send = AsyncMock(return_value=first)

    s = DiscordStreamer(channel, flush_interval=0)
    await s.handle(AgentEvent(type=AgentEventType.TEXT, text="hello "))
    await s.handle(AgentEvent(type=AgentEventType.TEXT, text="world"))
    await s.finalize()

    channel.send.assert_awaited_once()
    first.edit.assert_awaited()
    args, kwargs = first.edit.call_args
    assert "hello world" in kwargs["content"]


@pytest.mark.asyncio
async def test_streamer_splits_when_over_limit():
    channel = MagicMock()
    msg1, msg2 = MagicMock(), MagicMock()
    msg1.edit = AsyncMock()
    msg2.edit = AsyncMock()
    channel.send = AsyncMock(side_effect=[msg1, msg2])

    long = "A" * 1900
    second = "B" * 200

    s = DiscordStreamer(channel, flush_interval=0)
    await s.handle(AgentEvent(type=AgentEventType.TEXT, text=long))
    await s.handle(AgentEvent(type=AgentEventType.TEXT, text=second))
    await s.finalize()

    assert channel.send.await_count == 2


@pytest.mark.asyncio
async def test_streamer_ignores_non_text_events():
    channel = MagicMock()
    channel.send = AsyncMock()
    s = DiscordStreamer(channel, flush_interval=0)

    await s.handle(AgentEvent(type=AgentEventType.TOOL_START, tool_name="x"))
    await s.handle(AgentEvent(type=AgentEventType.DONE, session_id="s"))
    await s.finalize()

    channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_streamer_emits_error_event_as_message():
    channel = MagicMock()
    channel.send = AsyncMock()

    s = DiscordStreamer(channel, flush_interval=0)
    await s.handle(AgentEvent(type=AgentEventType.ERROR, error="boom"))
    await s.finalize()

    channel.send.assert_awaited()
    args, kwargs = channel.send.call_args
    content = kwargs.get("content") or (args[0] if args else "")
    assert "boom" in content
