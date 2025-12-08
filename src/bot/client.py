"""Discord Bot Client Module."""

import discord
from discord.ext import commands


class DiscordBot(commands.Bot):
    """Discord Bot 客戶端類別。"""

    def __init__(self, command_prefix: str = "!", **kwargs):
        """
        初始化 Discord Bot。

        Args:
            command_prefix: 指令前綴，預設為 "!"
            **kwargs: 其他傳遞給 commands.Bot 的參數
        """
        # 設定 Intents（權限）
        intents = discord.Intents.default()
        intents.message_content = True  # 需要讀取訊息內容
        intents.members = True  # 需要讀取成員資訊

        super().__init__(
            command_prefix=command_prefix,
            intents=intents,
            **kwargs
        )

    async def setup_hook(self):
        """Bot 設定 Hook，在 Bot 啟動前執行。"""
        print(f"正在設定 {self.user.name} Bot...")

    async def on_ready(self):
        """當 Bot 成功連接到 Discord 時觸發。"""
        print(f"\n{'=' * 50}")
        print(f"Bot 已成功登入！")
        print(f"Bot 名稱: {self.user.name}")
        print(f"Bot ID: {self.user.id}")
        print(f"Discord.py 版本: {discord.__version__}")
        print(f"{'=' * 50}\n")

    async def on_message(self, message: discord.Message):
        """
        當收到訊息時觸發。

        Args:
            message: Discord 訊息物件
        """
        # 忽略 Bot 自己的訊息
        if message.author == self.user:
            return

        # 處理指令
        await self.process_commands(message)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """
        當指令執行錯誤時觸發。

        Args:
            ctx: 指令上下文
            error: 錯誤物件
        """
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(f"找不到指令：{ctx.invoked_with}")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"缺少必要參數：{error.param.name}")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("你沒有權限執行此指令。")
        else:
            await ctx.send(f"執行指令時發生錯誤：{str(error)}")
            print(f"指令錯誤: {error}")
