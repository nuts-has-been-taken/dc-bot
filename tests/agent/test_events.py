from datetime import datetime

from src.agent.events import AgentEvent, AgentEventType, ChannelMsg


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
