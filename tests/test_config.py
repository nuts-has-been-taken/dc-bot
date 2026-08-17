import os
from pathlib import Path
from unittest import mock

import pytest


def test_config_validate_requires_discord_token(monkeypatch):
    # Neutralize load_dotenv so reload() doesn't repopulate DISCORD_TOKEN from a
    # real .env on the developer's machine.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    from importlib import reload
    import src.config as config_mod
    reload(config_mod)
    with pytest.raises(ValueError, match="DISCORD_TOKEN"):
        config_mod.Config.validate()


def test_config_agent_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("DISCORD_TOKEN", "x")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    from importlib import reload
    import src.config as config_mod
    reload(config_mod)

    cfg = config_mod.Config.get_agent_config()
    assert cfg["model"] == "claude-sonnet-5"
    assert Path(cfg["data_dir"]).name == "data"
    assert Path(cfg["db_path"]).name == "sessions.sqlite"
