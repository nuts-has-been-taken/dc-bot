from src.agent.naming import sanitize_user_name


def test_sanitize_passes_through_chinese_name():
    assert sanitize_user_name("小明") == "小明"


def test_sanitize_allows_ascii_and_underscore():
    assert sanitize_user_name("Alice_01") == "Alice_01"


def test_sanitize_replaces_path_separators():
    assert sanitize_user_name("../etc/passwd") == "etc_passwd"


def test_sanitize_replaces_backslashes_and_spaces():
    assert sanitize_user_name("name with spaces") == "name_with_spaces"


def test_sanitize_rejects_empty_and_dots():
    assert sanitize_user_name("") == "unnamed"
    assert sanitize_user_name("  ") == "unnamed"
    assert sanitize_user_name(".") == "unnamed"
    assert sanitize_user_name("..") == "unnamed"


def test_sanitize_truncates_long_names():
    assert len(sanitize_user_name("x" * 200)) == 64
