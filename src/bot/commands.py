"""Discord Bot 指令模組。"""

import discord
from discord import app_commands
from discord.ext import commands
from ..workflow.job_search import chat_with_job_search
from ..workflow.job_analysis import analyze_job_detail


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
            f"你好呀，{interaction.user.mention}！👋"
        )

    @app_commands.command(name="peak", description="童軍小隊")
    async def peak(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "童軍小隊，出發！🚀⛺🔥"
        )

    @app_commands.command(name="repo", description="撿垃圾大軍")
    async def repo(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "撿垃圾大軍，出發！🗑️🚮♻️"
        )
        
    @app_commands.command(name="dean", description="dean")
    async def dean(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "媽 dean，閉嘴"
        )

    @app_commands.command(name="找工作", description="使用 AI 搜尋 104 工作")
    @app_commands.describe(輸入="範例：我想找文山的 Python 工程師工作，薪水至少5萬")
    async def job_search(self, interaction: discord.Interaction, 輸入: str):
        """
        使用 AI 搜尋 104 工作斜線指令。

        Args:
            interaction: Discord 互動物件
            輸入: 使用者的工作需求描述
        """
        # 先回應，避免超時（Discord 要求 3 秒內回應）
        await interaction.response.send_message("🔍 正在搜尋工作中，請耐心等候...")

        try:
            # 呼叫 LLM 工作搜尋
            result = chat_with_job_search(user_message=輸入)

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

    @app_commands.command(name="分析工作", description="使用 AI 分析職缺的詳細資訊")
    @app_commands.describe(查詢="範例：我想知道台積電的IT評價，或直接貼上 104 職缺連結")
    async def job_analysis(self, interaction: discord.Interaction, 查詢: str):
        """
        使用 AI 分析特定職缺斜線指令。

        Args:
            interaction: Discord 互動物件
            查詢: 職缺查詢資訊（公司+職位，或 104 連結）
        """
        # 先回應，避免超時（Discord 要求 3 秒內回應）
        await interaction.response.send_message("🔍 正在分析職缺中，請耐心等候...")

        try:
            # 呼叫 LLM 職缺分析（異步）
            result = await analyze_job_detail(job_query=查詢)

            # 取得分析報告
            analysis_report = result.get("analysis_report", "抱歉，無法完成分析。")

            # Discord 訊息有 2000 字元限制，需要處理超長訊息
            if len(analysis_report) > 2000:
                # 分割訊息
                chunks = [analysis_report[i:i+2000] for i in range(0, len(analysis_report), 2000)]
                await interaction.edit_original_response(content=chunks[0])
                # 發送後續訊息
                for chunk in chunks[1:]:
                    await interaction.followup.send(chunk)
            else:
                # 編輯回應為最終結果
                await interaction.edit_original_response(content=analysis_report)

        except Exception as e:
            # 錯誤處理
            await interaction.edit_original_response(
                content=f"❌ 分析時發生錯誤：{str(e)}"
            )
            print(f"分析工作指令錯誤: {e}")


async def setup(bot: commands.Bot):
    """
    設定 Cog。

    注意：Cog 中的 @app_commands.command() 會自動註冊到 bot.tree

    Args:
        bot: Discord Bot 實例
    """
    await bot.add_cog(BasicCommands(bot))
