"""Configuration Module - Load settings from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


class Config:
    """應用程式配置類別。"""

    # Discord
    DISCORD_TOKEN: str | None = os.getenv("DISCORD_TOKEN")
    DISCORD_COMMAND_PREFIX: str = os.getenv("DISCORD_COMMAND_PREFIX", "!")
    DISCORD_GUILD_IDS: list[int] = [
        int(gid)
        for gid in os.getenv("DISCORD_GUILD_IDS", "").split(",")
        if gid.strip()
    ]

    # Agent
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
    DISCORD_OWNER_ID: str = os.getenv("DISCORD_OWNER_ID", "")
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
    DB_PATH: Path = Path(
        os.getenv("DB_PATH", str(BASE_DIR / "src" / "db" / "sessions.sqlite"))
    ).resolve()

    # Brave Search API（web / web_context / image 搜尋工具用）
    BRAVE_SEARCH_API_KEY: str | None = os.getenv("BRAVE_SEARCH_API_KEY")
    # 每月 Brave 搜尋次數上限（免費額度 US$5 ≈ 1000 次/月）
    BRAVE_MONTHLY_LIMIT: int = int(os.getenv("BRAVE_MONTHLY_LIMIT", "1000"))

    @classmethod
    def validate(cls) -> None:
        if not cls.DISCORD_TOKEN:
            raise ValueError(
                "DISCORD_TOKEN is not set. Create a .env file based on .env_example."
            )

    @classmethod
    def get_discord_config(cls) -> dict:
        return {
            "token": cls.DISCORD_TOKEN,
            "command_prefix": cls.DISCORD_COMMAND_PREFIX,
            "guild_ids": cls.DISCORD_GUILD_IDS,
        }

    @classmethod
    def get_agent_config(cls) -> dict:
        return {
            "model": cls.ANTHROPIC_MODEL,
            "data_dir": cls.DATA_DIR,
            "db_path": cls.DB_PATH,
            "owner_id": cls.DISCORD_OWNER_ID,
        }


config = Config()
