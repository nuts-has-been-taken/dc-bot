"""Discord Bot entry point — Claude Agent SDK driven."""

import asyncio
from pathlib import Path

from src.agent.config import AgentConfig
from src.agent.runner import AgentRunner
from src.agent.session import SessionStore
from src.agent.tools.discord_mcp import DiscordToolset
from src.bot.client import DiscordBot
from src.bot.cogs import chat as chat_cog
from src.config import Config


async def main():
    try:
        Config.validate()
    except ValueError as e:
        print(f"配置錯誤: {e}")
        return

    discord_cfg = Config.get_discord_config()
    agent_cfg_raw = Config.get_agent_config()

    data_dir: Path = agent_cfg_raw["data_dir"]
    db_path: Path = agent_cfg_raw["db_path"]
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "members").mkdir(exist_ok=True)
    (data_dir / "threads").mkdir(exist_ok=True)
    (data_dir / "knowledge").mkdir(exist_ok=True)
    (data_dir / "scratch").mkdir(exist_ok=True)

    sessions = SessionStore(db_path)
    await sessions.init()

    bot = DiscordBot(command_prefix=discord_cfg["command_prefix"])

    discord_tools = DiscordToolset(bot)
    agent_cfg = AgentConfig(
        data_dir=data_dir,
        db_path=db_path,
        model=agent_cfg_raw["model"],
    )
    runner = AgentRunner(agent_cfg, discord_toolset=discord_tools)

    await bot.load_extension("src.bot.cogs.fun")
    await chat_cog.setup(bot, runner, sessions)

    print("啟動 Discord Bot...")
    async with bot:
        await bot.start(discord_cfg["token"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n正在關閉服務...")
