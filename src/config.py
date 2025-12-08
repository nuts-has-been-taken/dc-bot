"""Configuration Module - Load settings from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# 找到 .env 文件的路徑（在專案根目錄）
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

# 載入 .env 文件
load_dotenv(ENV_FILE)


class Config:
    """應用程式配置類別。"""

    # LLM API 設定
    LLM_API_KEY = os.getenv("LLM_API_KEY")
    LLM_API_URL = os.getenv("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5")

    # Discord Bot 設定
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    DISCORD_COMMAND_PREFIX = os.getenv("DISCORD_COMMAND_PREFIX", "!")

    @classmethod
    def validate(cls):
        """
        驗證必要的配置是否已設定。

        Raises:
            ValueError: 當必要的配置缺失時
        """
        if not cls.LLM_API_KEY:
            raise ValueError(
                "LLM_API_KEY is not set. Please create a .env file with your API key."
            )
        if not cls.DISCORD_TOKEN:
            raise ValueError(
                "DISCORD_TOKEN is not set. Please create a .env file with your Discord bot token."
            )

    @classmethod
    def get_llm_config(cls):
        """
        獲取 LLM 配置。

        Returns:
            包含 LLM 配置的字典
        """
        return {
            "api_key": cls.LLM_API_KEY,
            "api_url": cls.LLM_API_URL,
            "model": cls.LLM_MODEL,
        }

    @classmethod
    def get_discord_config(cls):
        """
        獲取 Discord 配置。

        Returns:
            包含 Discord 配置的字典
        """
        return {
            "token": cls.DISCORD_TOKEN,
            "command_prefix": cls.DISCORD_COMMAND_PREFIX,
        }


# 建立全域配置實例
config = Config()
