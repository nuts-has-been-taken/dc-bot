from src.agent.prompt import build_system_prompt


def test_chat_mode_includes_raphtalia_and_chat_guidelines():
    prompt = build_system_prompt(
        mode="chat", user_id="123", thread_id="999"
    )
    assert "拉芙塔莉雅" in prompt
    assert "data/members/123.md" in prompt
    assert "data/threads/999.md" in prompt
    assert "Discord" in prompt


def test_work_mode_forces_104_tool_usage():
    prompt = build_system_prompt(mode="work", user_id="123", thread_id="999")
    assert "search_104_jobs" in prompt
    assert "analyze_104_job" in prompt


def test_oneshot_mode_no_thread_memory():
    prompt = build_system_prompt(mode="oneshot", user_id="123")
    assert "data/threads/" not in prompt
    assert "data/members/123.md" in prompt


def test_dm_mode_has_dm_guidelines():
    prompt = build_system_prompt(mode="dm", user_id="123", thread_id="999")
    assert "私訊" in prompt or "DM" in prompt
