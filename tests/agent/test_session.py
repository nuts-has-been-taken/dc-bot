import pytest

from src.agent.session import Session, SessionStore


@pytest.mark.asyncio
async def test_create_and_get_session(tmp_sqlite):
    store = SessionStore(tmp_sqlite)
    await store.init()
    created = await store.create(
        discord_session_id="thread:111",
        user_id="user_1",
        mode="chat",
        metadata={"channel_id": 42},
    )
    assert created.discord_session_id == "thread:111"
    assert created.mode == "chat"
    assert created.claude_session_id is None

    fetched = await store.get("thread:111")
    assert fetched is not None
    assert fetched.user_id == "user_1"
    assert fetched.metadata == {"channel_id": 42}


@pytest.mark.asyncio
async def test_get_returns_none_when_absent(tmp_sqlite):
    store = SessionStore(tmp_sqlite)
    await store.init()
    assert await store.get("thread:does-not-exist") is None


@pytest.mark.asyncio
async def test_update_claude_session(tmp_sqlite):
    store = SessionStore(tmp_sqlite)
    await store.init()
    await store.create(
        discord_session_id="thread:222",
        user_id="user_2",
        mode="work",
        metadata={},
    )
    await store.update_claude_session("thread:222", "claude-abc")
    fetched = await store.get("thread:222")
    assert fetched.claude_session_id == "claude-abc"


@pytest.mark.asyncio
async def test_touch_updates_last_active(tmp_sqlite):
    import asyncio
    store = SessionStore(tmp_sqlite)
    await store.init()
    s1 = await store.create(
        discord_session_id="thread:333",
        user_id="u3",
        mode="dm",
        metadata={},
    )
    await asyncio.sleep(0.01)
    await store.touch("thread:333")
    s2 = await store.get("thread:333")
    assert s2.last_active_at >= s1.last_active_at


@pytest.mark.asyncio
async def test_delete_session(tmp_sqlite):
    store = SessionStore(tmp_sqlite)
    await store.init()
    await store.create(
        discord_session_id="thread:444",
        user_id="u4",
        mode="chat",
        metadata={},
    )
    await store.delete("thread:444")
    assert await store.get("thread:444") is None
