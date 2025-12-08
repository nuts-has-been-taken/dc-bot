"""Discord Bot 啟動腳本。"""

import asyncio

from src.config import Config
from src.bot.client import DiscordBot


async def main():
    """主程式入口。"""
    # 驗證配置
    try:
        Config.validate()
    except ValueError as e:
        print(f"配置錯誤: {e}")
        return

    # 獲取 Discord 配置
    discord_config = Config.get_discord_config()

    # 建立 Bot 實例
    bot = DiscordBot(command_prefix=discord_config["command_prefix"])

    # 載入基本指令
    try:
        await bot.load_extension("src.bot.commands")
        print("已載入基本指令模組")
    except Exception as e:
        print(f"載入指令模組時發生錯誤: {e}")

    # 啟動 Bot
    async with bot:
        await bot.start(discord_config["token"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n正在關閉 Bot...")
