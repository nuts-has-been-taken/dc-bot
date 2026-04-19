import pytest_asyncio

from dataclasses import dataclass
from typing import AsyncIterator


@pytest_asyncio.fixture
async def tmp_sqlite(tmp_path):
    """Temp SQLite file path for tests."""
    return tmp_path / "sessions.sqlite"


@dataclass
class FakeSDKMessage:
    """Mimics subset of claude_agent_sdk message types we consume."""
    kind: str                      # "assistant" | "tool_use" | "tool_result" | "result"
    text: str = ""
    tool_name: str = ""
    tool_input: dict | None = None
    tool_output: str = ""
    session_id: str = ""


def make_fake_query(messages: list[FakeSDKMessage]):
    """Factory producing a replacement for claude_agent_sdk.query()."""

    async def fake_query(*args, **kwargs) -> AsyncIterator[FakeSDKMessage]:
        for m in messages:
            yield m

    return fake_query
