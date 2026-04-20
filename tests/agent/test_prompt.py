from src.agent.prompt import build_system_prompt


def test_chat_mode_includes_raphtalia_and_chat_guidelines():
    prompt = build_system_prompt(mode="chat", user_name="Alice", thread_id="999")
    assert "拉芙塔莉雅" in prompt
    assert "data/members/Alice.md" in prompt
    assert "data/threads/999.md" in prompt
    assert "Discord" in prompt


def test_work_mode_forces_104_tool_usage():
    prompt = build_system_prompt(mode="work", user_name="Alice", thread_id="999")
    assert "search_104_jobs" in prompt
    assert "analyze_104_job" in prompt


def test_oneshot_mode_no_thread_memory():
    prompt = build_system_prompt(mode="oneshot", user_name="Alice")
    assert "data/threads/" not in prompt
    assert "data/members/Alice.md" in prompt


def test_dm_mode_has_dm_guidelines():
    prompt = build_system_prompt(mode="dm", user_name="Alice", thread_id="999")
    assert "私訊" in prompt or "DM" in prompt


def test_member_guideline_includes_user_name():
    prompt = build_system_prompt(mode="chat", user_name="Alice", thread_id="999")
    assert "Alice" in prompt
    assert "data/members/Alice.md" in prompt  # file path uses sanitized name


def test_member_guideline_uses_sanitized_name_in_path():
    # display name with spaces → underscored in file path, raw name still shown
    prompt = build_system_prompt(mode="chat", user_name="Cool User", thread_id="1")
    assert "用戶名稱：Cool User" in prompt
    assert "data/members/Cool_User.md" in prompt


def test_member_guideline_no_user_id():
    # numeric user_id must NOT appear anywhere in the prompt
    prompt = build_system_prompt(mode="chat", user_name="Alice", thread_id="999")
    assert "123" not in prompt
