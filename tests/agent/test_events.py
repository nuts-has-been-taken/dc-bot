from datetime import datetime

from src.agent.events import (
    AgentEvent,
    AgentEventType,
    ChannelMsg,
    trim_to_char_budget,
)


def _msg(content: str, author: str = "u") -> ChannelMsg:
    return ChannelMsg(author=author, content=content, created_at=datetime(2026, 4, 20))


def test_agent_event_text_requires_text_field():
    evt = AgentEvent(type=AgentEventType.TEXT, text="hello")
    assert evt.text == "hello"
    assert evt.session_id is None


def test_agent_event_done_carries_session_id():
    evt = AgentEvent(type=AgentEventType.DONE, session_id="abc123")
    assert evt.session_id == "abc123"
    assert evt.text is None


def test_channel_msg_formats_for_prompt():
    msg = ChannelMsg(
        author="alice",
        content="推 FastAPI",
        created_at=datetime(2026, 4, 20, 10, 0, 0),
    )
    assert msg.format_line() == "alice: 推 FastAPI"


def test_trim_empty_list_returns_empty():
    assert trim_to_char_budget([], 100) == []


def test_trim_keeps_all_when_under_budget():
    msgs = [_msg("aaa"), _msg("bbb")]
    # each line is "u: aaa" = 6 chars, total 12 < 100
    assert trim_to_char_budget(msgs, 100) == msgs


def test_trim_drops_oldest_when_over_budget():
    msgs = [_msg("old"), _msg("mid"), _msg("new")]
    # each line "u: xxx" = 6 chars; budget 13 fits only the newest 2 (12 chars)
    assert trim_to_char_budget(msgs, 13) == [_msg("mid"), _msg("new")]


def test_trim_counts_full_format_line_including_author_prefix():
    msgs = [_msg("x", author="alice"), _msg("y", author="bob")]
    # "alice: x" = 8 chars, "bob: y" = 6 chars; budget 6 keeps only newest
    assert trim_to_char_budget(msgs, 6) == [_msg("y", author="bob")]


def test_trim_keeps_newest_even_when_single_message_exceeds_budget():
    msgs = [_msg("short"), _msg("a very long final message")]
    assert trim_to_char_budget(msgs, 1) == [_msg("a very long final message")]
