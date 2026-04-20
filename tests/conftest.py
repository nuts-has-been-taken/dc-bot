import pytest_asyncio

from dataclasses import dataclass
from typing import AsyncIterator

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock


@pytest_asyncio.fixture
async def tmp_sqlite(tmp_path):
    """Temp SQLite file path for tests."""
    return tmp_path / "sessions.sqlite"


@dataclass
class FakeSDKMessage:
    """Legacy stub — kept for any test that still uses it directly.

    Prefer constructing real SDK types (AssistantMessage, ResultMessage, ...)
    for new tests so that isinstance() dispatch in runner.py is exercised.
    """
    kind: str                      # "assistant" | "tool_use" | "tool_result" | "result"
    text: str = ""
    tool_name: str = ""
    tool_input: dict | None = None
    tool_output: str = ""
    session_id: str = ""


def make_fake_query(messages: list):
    """Factory producing a replacement for claude_agent_sdk.query().

    ``messages`` should be a list of real SDK message instances
    (AssistantMessage, ResultMessage, ...) so that isinstance() dispatch
    in runner.py is exercised correctly.
    """

    async def fake_query(*args, **kwargs):
        for m in messages:
            yield m

    return fake_query
