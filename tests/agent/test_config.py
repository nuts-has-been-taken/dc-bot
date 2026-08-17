from pathlib import Path

from src.agent.config import (
    ALLOWED_TOOLS,
    DISALLOWED_PATHS,
    AgentConfig,
)


def test_agent_config_defaults():
    cfg = AgentConfig(
        data_dir=Path("/tmp/data"),
        db_path=Path("/tmp/sessions.sqlite"),
    )
    assert cfg.model == "claude-sonnet-5"
    assert cfg.max_turns == 20
    assert cfg.timeout_seconds == 60


def test_allowed_tools_excludes_bash():
    assert "Bash" not in ALLOWED_TOOLS
    assert "Read" in ALLOWED_TOOLS
    assert "Write" in ALLOWED_TOOLS
    assert "WebSearch" in ALLOWED_TOOLS


def test_disallowed_paths_protect_source():
    assert "src/" in DISALLOWED_PATHS
    assert ".env" in DISALLOWED_PATHS
