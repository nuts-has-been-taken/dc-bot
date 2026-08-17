"""MCP tool adapter: expose a small, safe subset of Discord bot actions.

The Discord bot instance is injected at construction; callers of these
coroutines get plain dicts / bools suitable for passing through the agent.
"""

from typing import Any
from urllib.parse import urlparse

import discord

# Only http(s) image URLs are accepted — blocks file://, attachment://,
# data:, javascript:, etc. so a malicious agent call can't point Discord at
# an unexpected scheme.
_ALLOWED_IMAGE_SCHEMES = {"http", "https"}


class DiscordToolset:
    def __init__(self, bot: discord.Client):
        self.bot = bot

    async def fetch_channel_history(
        self, channel_id: int, limit: int = 20
    ) -> list[dict[str, Any]]:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return []
        out: list[dict[str, Any]] = []
        async for msg in channel.history(limit=limit):
            out.append(
                {
                    "author": msg.author.display_name,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                }
            )
        return list(reversed(out))  # oldest → newest

    async def send_image(
        self,
        channel_id: int,
        image_url: str,
        caption: str | None = None,
    ) -> bool:
        """Post an image to a channel via an embed with set_image(url=...).

        Only takes a URL (never downloads / stores the binary). The scheme is
        limited to http(s); anything else is rejected to avoid pointing Discord
        at local files or other non-HTTP resources.
        """
        scheme = urlparse(image_url).scheme.lower()
        if scheme not in _ALLOWED_IMAGE_SCHEMES:
            return False
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return False
        embed = discord.Embed(description=caption or "", color=0xEE82EE)
        embed.set_image(url=image_url)
        await channel.send(embed=embed)
        return True

    async def send_embed(
        self,
        channel_id: int,
        title: str,
        description: str | None = None,
        fields: list[dict[str, str]] | None = None,
        color: int = 0xEE82EE,
    ) -> bool:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return False
        embed = discord.Embed(title=title, description=description or "", color=color)
        for f in fields or []:
            embed.add_field(
                name=f.get("name", ""),
                value=f.get("value", ""),
                inline=bool(f.get("inline", False)),
            )
        await channel.send(embed=embed)
        return True

    async def react_to_message(
        self, channel_id: int, message_id: int, emoji: str
    ) -> bool:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return False
        msg = await channel.fetch_message(message_id)
        await msg.add_reaction(emoji)
        return True

    async def get_member_info(
        self, user_id: int, guild_id: int | None = None
    ) -> dict[str, Any] | None:
        if guild_id is not None:
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                return None
            member = guild.get_member(user_id)
            if member is None:
                return None
            return {
                "id": member.id,
                "name": member.name,
                "display_name": member.display_name,
                "roles": [r.name for r in member.roles if r.name != "@everyone"],
                "joined_at": (
                    member.joined_at.isoformat() if member.joined_at else None
                ),
            }
        user = self.bot.get_user(user_id)
        if user is None:
            return None
        return {
            "id": user.id,
            "name": user.name,
            "display_name": user.display_name,
        }
