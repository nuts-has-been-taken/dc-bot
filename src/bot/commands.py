"""Discord Bot 指令模組。"""

from discord.ext import commands


class BasicCommands(commands.Cog):
    """基本指令 Cog。"""

    def __init__(self, bot: commands.Bot):
        """
        初始化基本指令。

        Args:
            bot: Discord Bot 實例
        """
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        """
        回應 Pong! 並顯示延遲時間。

        使用方式: !ping
        """
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"🏓 Pong! 延遲: {latency}ms")

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
            description="這是 Carbarcha bot",
            color=discord.Color.blue()
        )
        embed.add_field(name="Bot 名稱", value=self.bot.user.name, inline=True)
        embed.add_field(name="伺服器數量", value=len(self.bot.guilds), inline=True)

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """
    設定 Cog。

    Args:
        bot: Discord Bot 實例
    """
    await bot.add_cog(BasicCommands(bot))
