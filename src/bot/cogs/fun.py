"""Stateless fun/meme slash commands. Do not go through the agent."""

import discord
from discord import app_commands
from discord.ext import commands


class FunCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="hello", description="打招呼")
    async def hello(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"你好呀，{interaction.user.mention}！👋"
        )

    @app_commands.command(name="peak", description="童軍小隊")
    async def peak(self, interaction: discord.Interaction):
        await interaction.response.send_message("童軍小隊，出發！🚀⛺🔥")

    @app_commands.command(name="repo", description="撿垃圾大軍")
    async def repo(self, interaction: discord.Interaction):
        await interaction.response.send_message("撿垃圾大軍，出發！🗑️🚮♻️")

    @app_commands.command(name="dean", description="dean")
    async def dean(self, interaction: discord.Interaction):
        await interaction.response.send_message("媽 dean")

    @app_commands.command(name="lin", description="lin")
    async def lin(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"林冠勳會養 {interaction.user.mention}！💵"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(FunCog(bot))
