"""Discord Bot 指令模組。"""

import discord
from discord import app_commands
from discord.ext import commands
from ..workflow.job_search import chat_with_job_search


class BasicCommands(commands.Cog):
    """基本指令 Cog。"""

    def __init__(self, bot: commands.Bot):
        """
        初始化基本指令。

        Args:
            bot: Discord Bot 實例
        """
        self.bot = bot

    @app_commands.command(name="hello", description="打招呼")
    async def hello(self, interaction: discord.Interaction):
        """打招呼斜線指令。"""
        await interaction.response.send_message(
            f"你好，{interaction.user.mention}！👋"
        )

    @app_commands.command(name="info", description="顯示 Bot 資訊")
    async def info(self, interaction: discord.Interaction):
        """顯示 Bot 資訊斜線指令。"""
        embed = discord.Embed(
            title="Bot 資訊",
            description="這是拉芙塔莉雅",
            color=discord.Color.blue()
        )
        embed.add_field(name="Bot 名稱", value=self.bot.user.name, inline=True)
        embed.add_field(name="伺服器數量", value=len(self.bot.guilds), inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="找工作", description="使用 LLM 搜尋 104 工作")
    @app_commands.describe(需求="請描述你的工作需求，例如：台北市的 Python 工程師，薪水至少 5 萬")
    async def job_search(self, interaction: discord.Interaction, 需求: str):
        """
        使用 LLM 搜尋 104 工作斜線指令。

        Args:
            interaction: Discord 互動物件
            需求: 使用者的工作需求描述
        """
        # 先回應，避免超時（Discord 要求 3 秒內回應）
        await interaction.response.send_message("🔍 正在搜尋工作中...")

        try:
            # 呼叫 LLM 工作搜尋
            result = chat_with_job_search(user_message=需求)

            # 取得最終回應
            final_response = result.get("final_response", "抱歉，沒有找到相關工作。")

            # 編輯回應為最終結果
            await interaction.edit_original_response(content=final_response)

        except Exception as e:
            # 錯誤處理
            await interaction.edit_original_response(
                content=f"❌ 搜尋時發生錯誤：{str(e)}"
            )
            print(f"找工作指令錯誤: {e}")


async def setup(bot: commands.Bot):
    """
    設定 Cog。

    注意：Cog 中的 @app_commands.command() 會自動註冊到 bot.tree

    Args:
        bot: Discord Bot 實例
    """
    await bot.add_cog(BasicCommands(bot))
