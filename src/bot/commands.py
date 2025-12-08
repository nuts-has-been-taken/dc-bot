"""Discord Bot 指令模組。"""

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

    @commands.command(name="hello")
    async def hello(self, ctx: commands.Context):
        """
        打招呼。

        使用方式: !hello
        """
        await ctx.send(f"你好，{ctx.author.mention}！👋")

    @commands.command(name="info")
    async def info(self, ctx: commands.Context):
        """
        顯示 Bot 資訊。

        使用方式: !info
        """
        import discord

        embed = discord.Embed(
            title="Bot 資訊",
            description="這是拉芙塔莉雅",
            color=discord.Color.blue()
        )
        embed.add_field(name="Bot 名稱", value=self.bot.user.name, inline=True)
        embed.add_field(name="伺服器數量", value=len(self.bot.guilds), inline=True)

        await ctx.send(embed=embed)

    @commands.command(name="找工作")
    async def job_search(self, ctx: commands.Context, *, message: str):
        """
        使用 LLM 搜尋 104 工作。

        使用方式: /找工作 <你的需求>
        範例: /找工作 我想找台北市的 Python 工程師工作，薪水至少 5 萬
        """
        # 發送處理中訊息
        processing_msg = await ctx.send("🔍 正在搜尋工作中...")

        try:
            # 呼叫 LLM 工作搜尋
            result = chat_with_job_search(user_message=message)

            # 取得最終回應
            final_response = result.get("final_response", "抱歉，沒有找到相關工作。")

            # 編輯處理中訊息為最終結果
            await processing_msg.edit(content=final_response)

        except Exception as e:
            # 錯誤處理
            await processing_msg.edit(content=f"❌ 搜尋時發生錯誤：{str(e)}")
            print(f"找工作指令錯誤: {e}")


async def setup(bot: commands.Bot):
    """
    設定 Cog。

    Args:
        bot: Discord Bot 實例
    """
    await bot.add_cog(BasicCommands(bot))
