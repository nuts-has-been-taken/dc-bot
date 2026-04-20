"""Chat cog: agent-backed conversation via @mention, /chat, /work, DM."""

from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from src.agent.events import AgentEventType, ChannelMsg
from src.agent.runner import AgentRunner
from src.agent.session import SessionStore
from src.bot.streamer import DiscordStreamer


Mode = Literal["chat", "work", "dm"]

DEFAULT_CONTEXT_LIMIT = 10


class ChatCog(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        runner: AgentRunner,
        sessions: SessionStore,
    ):
        self.bot = bot
        self.runner = runner
        self.sessions = sessions

    # ─────────────── Events ───────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        if message.webhook_id is not None:
            return

        # DM
        if isinstance(message.channel, discord.DMChannel):
            await self._stateful(
                message,
                mode="dm",
                discord_session_id=f"dm:{message.author.id}",
            )
            return

        # Bot-managed thread
        if isinstance(message.channel, discord.Thread):
            sess = await self.sessions.get(f"thread:{message.channel.id}")
            if sess is not None:
                await self._stateful(
                    message,
                    mode=sess.mode,
                    discord_session_id=sess.discord_session_id,
                )
                return

        # @mention in a guild channel → one-shot
        if self.bot.user in message.mentions:
            await self._oneshot(message)
            return

    # ─────────────── Slash commands ───────────────

    @app_commands.command(
        name="chat",
        description="開一個私人 thread 與 bot 多輪對話",
    )
    async def chat_cmd(self, interaction: discord.Interaction):
        await self._open_thread(interaction, mode="chat", topic="聊天")

    @app_commands.command(
        name="work",
        description="開一個 thread 專門討論工作（使用 104 工具）",
    )
    async def work_cmd(self, interaction: discord.Interaction):
        await self._open_thread(interaction, mode="work", topic="找工作")

    # ─────────────── Handlers ───────────────

    async def _open_thread(
        self,
        interaction: discord.Interaction,
        *,
        mode: Mode,
        topic: str,
    ):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "這裡不支援開 thread 喔～請到一般頻道使用。", ephemeral=True
            )
            return

        thread = await interaction.channel.create_thread(
            name=f"{topic} - {interaction.user.display_name}",
            type=discord.ChannelType.public_thread,
        )
        await thread.add_user(interaction.user)

        await self.sessions.create(
            discord_session_id=f"thread:{thread.id}",
            user_id=str(interaction.user.id),
            mode=mode,
            metadata={
                "thread_name": thread.name,
                "parent_channel_id": interaction.channel.id,
            },
        )

        await interaction.response.send_message(
            f"{thread.mention} 我們在那邊聊～", ephemeral=True
        )
        greeting = (
            "主人～我們開始聊吧 💕"
            if mode == "chat"
            else "主人想找什麼樣的工作呢？告訴我地點、職類、薪資期待就好～"
        )
        await thread.send(f"{interaction.user.mention} {greeting}")

    async def _oneshot(self, message: discord.Message):
        history = [m async for m in message.channel.history(limit=DEFAULT_CONTEXT_LIMIT)]
        history.reverse()  # oldest → newest
        ctx = [
            ChannelMsg(
                author=m.author.display_name,
                content=m.content,
                created_at=m.created_at,
            )
            for m in history
            if m.id != message.id
        ]

        async with message.channel.typing():
            streamer = DiscordStreamer(message.channel, reply_to=message)
            async for event in self.runner.run(
                user_input=message.content,
                mode="oneshot",
                user_name=str(message.author.display_name),
                channel_context=ctx,
            ):
                await streamer.handle(event)
            await streamer.finalize()

    async def _stateful(
        self,
        message: discord.Message,
        *,
        mode: Mode,
        discord_session_id: str,
    ):
        sess = await self.sessions.get(discord_session_id)
        if sess is None:
            sess = await self.sessions.create(
                discord_session_id=discord_session_id,
                user_id=str(message.author.id),
                mode=mode,
                metadata={"channel_id": message.channel.id},
            )

        thread_id = (
            str(message.channel.id)
            if isinstance(message.channel, discord.Thread)
            else None
        )

        async with message.channel.typing():
            streamer = DiscordStreamer(message.channel)
            final_session_id: str | None = None
            async for event in self.runner.run(
                user_input=message.content,
                mode=mode,
                user_name=str(message.author.display_name),
                resume=sess.claude_session_id,
                thread_id=thread_id,
            ):
                await streamer.handle(event)
                if event.type == AgentEventType.DONE:
                    final_session_id = event.session_id
            await streamer.finalize()

        if final_session_id and final_session_id != sess.claude_session_id:
            await self.sessions.update_claude_session(
                discord_session_id, final_session_id
            )
        await self.sessions.touch(discord_session_id)


async def setup(bot: commands.Bot, runner: AgentRunner, sessions: SessionStore):
    await bot.add_cog(ChatCog(bot, runner, sessions))
