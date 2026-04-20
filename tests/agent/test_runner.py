from pathlib import Path
from unittest.mock import patch

import pytest

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from src.agent.config import AgentConfig
from src.agent.events import AgentEventType
from src.agent.runner import AgentRunner
from tests.conftest import make_fake_query


@pytest.mark.asyncio
async def test_run_streams_text_and_emits_done(tmp_path):
    cfg = AgentConfig(
        data_dir=tmp_path / "data", db_path=tmp_path / "s.sqlite"
    )
    runner = AgentRunner(cfg, discord_toolset=None)

    messages = [
        AssistantMessage(content=[TextBlock(text="你好")], model="claude-sonnet-4-6"),
        AssistantMessage(content=[TextBlock(text="主人～")], model="claude-sonnet-4-6"),
        ResultMessage(
            subtype="success",
            duration_ms=0,
            duration_api_ms=0,
            is_error=False,
            num_turns=1,
            session_id="sess-001",
        ),
    ]
    with patch(
        "src.agent.runner.sdk_query",
        side_effect=make_fake_query(messages),
    ):
        events = []
        async for ev in runner.run(
            user_input="hi",
            mode="oneshot",
            user_id="u1",
        ):
            events.append(ev)

    assert [e.type for e in events] == [
        AgentEventType.TEXT,
        AgentEventType.TEXT,
        AgentEventType.DONE,
    ]
    assert events[-1].session_id == "sess-001"


@pytest.mark.asyncio
async def test_run_includes_channel_context_preamble(tmp_path):
    cfg = AgentConfig(
        data_dir=tmp_path / "data", db_path=tmp_path / "s.sqlite"
    )
    runner = AgentRunner(cfg, discord_toolset=None)

    from datetime import datetime
    from src.agent.events import ChannelMsg

    ctx = [
        ChannelMsg("alice", "hi", datetime(2026, 4, 20, 10)),
        ChannelMsg("bob", "yo", datetime(2026, 4, 20, 10, 1)),
    ]

    captured_prompt = {}

    async def capture(*args, **kwargs):
        # prompt is now an AsyncIterable[dict]; consume it to a single string
        prompt_arg = kwargs.get("prompt") or (args[0] if args else None)
        collected = []
        async for chunk in prompt_arg:
            if isinstance(chunk, dict):
                msg = chunk.get("message") or {}
                collected.append(msg.get("content", ""))
            else:
                collected.append(str(chunk))
        captured_prompt["input"] = "\n".join(collected)
        yield ResultMessage(
            subtype="success",
            duration_ms=0,
            duration_api_ms=0,
            is_error=False,
            num_turns=1,
            session_id="s",
        )

    with patch("src.agent.runner.sdk_query", side_effect=capture):
        async for _ in runner.run(
            user_input="what?", mode="oneshot",
            user_id="u", channel_context=ctx,
        ):
            pass

    assert "alice: hi" in captured_prompt["input"]
    assert "bob: yo" in captured_prompt["input"]
    assert "what?" in captured_prompt["input"]
