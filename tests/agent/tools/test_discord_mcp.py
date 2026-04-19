from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent.tools.discord_mcp import DiscordToolset


def _fake_message(author_name: str, content: str, created_at: datetime):
    msg = MagicMock()
    msg.author.display_name = author_name
    msg.content = content
    msg.created_at = created_at
    return msg


@pytest.mark.asyncio
async def test_fetch_channel_history_returns_plain_dicts_oldest_first():
    """Real discord.py iterates newest-first; toolset reverses for caller convenience."""
    bot = MagicMock()
    channel = MagicMock()

    async def _iter(limit):
        # Emulate real discord.py: yields newest-first
        yield _fake_message("bob", "yo", datetime(2026, 4, 20, 12, 1))
        yield _fake_message("alice", "hi", datetime(2026, 4, 20, 12, 0))

    channel.history = _iter
    bot.get_channel = MagicMock(return_value=channel)

    tools = DiscordToolset(bot)
    result = await tools.fetch_channel_history(channel_id=99, limit=5)
    # After reversal, the agent sees oldest → newest
    assert result == [
        {"author": "alice", "content": "hi", "created_at": "2026-04-20T12:00:00"},
        {"author": "bob", "content": "yo", "created_at": "2026-04-20T12:01:00"},
    ]


@pytest.mark.asyncio
async def test_react_to_message_calls_discord_api():
    bot = MagicMock()
    channel = MagicMock()
    msg = MagicMock()
    msg.add_reaction = AsyncMock()
    channel.fetch_message = AsyncMock(return_value=msg)
    bot.get_channel = MagicMock(return_value=channel)

    tools = DiscordToolset(bot)
    ok = await tools.react_to_message(
        channel_id=1, message_id=2, emoji="💕"
    )
    msg.add_reaction.assert_awaited_once_with("💕")
    assert ok is True


@pytest.mark.asyncio
async def test_fetch_channel_history_missing_channel_returns_empty():
    bot = MagicMock()
    bot.get_channel = MagicMock(return_value=None)
    tools = DiscordToolset(bot)
    assert await tools.fetch_channel_history(channel_id=99) == []
