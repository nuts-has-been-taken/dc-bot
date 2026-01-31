"""Discord Bot 啟動腳本 - 同時運行 Discord Bot 和 API Server。"""

import asyncio

import uvicorn

from src.api import create_app
from src.bot.client import DiscordBot
from src.config import Config


async def run_api_server(app, host: str, port: int):
    """運行 FastAPI Server。"""
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """主程式入口。"""
    # 驗證配置
    try:
        Config.validate()
    except ValueError as e:
        print(f"配置錯誤: {e}")
        return

    # 獲取配置
    discord_config = Config.get_discord_config()
    api_config = Config.get_api_config()

    # 建立 Bot 實例
    bot = DiscordBot(command_prefix=discord_config["command_prefix"])

    # 建立 FastAPI 應用程式並注入 bot 實例
    app = create_app(bot=bot)

    # 載入基本指令
    try:
        await bot.load_extension("src.bot.commands")
        print("已載入基本指令模組")
    except Exception as e:
        print(f"載入指令模組時發生錯誤: {e}")

    # 同時運行 Discord Bot 和 API Server
    async with bot:
        # 建立 tasks
        discord_task = asyncio.create_task(
            bot.start(discord_config["token"]),
            name="discord_bot",
        )
        api_task = asyncio.create_task(
            run_api_server(app, api_config["host"], api_config["port"]),
            name="api_server",
        )

        print(f"\n啟動 API Server: http://{api_config['host']}:{api_config['port']}")
        print("啟動 Discord Bot...")

        # 等待任一 task 完成（通常是 Ctrl+C 觸發）
        done, pending = await asyncio.wait(
            [discord_task, api_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # 取消尚未完成的 tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n正在關閉服務...")
