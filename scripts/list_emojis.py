"""One-off: dump all emojis of a given guild. Usage: uv run python scripts/list_emojis.py <guild_id>"""

import asyncio
import os
import sys

import discord
from dotenv import load_dotenv


async def main(guild_id: int) -> None:
    load_dotenv()
    token = os.environ["DISCORD_TOKEN"]

    intents = discord.Intents.default()
    intents.emojis_and_stickers = True
    intents.guilds = True
    client = discord.Client(intents=intents)

    ready = asyncio.Event()

    @client.event
    async def on_ready() -> None:
        ready.set()

    async with client:
        asyncio.create_task(client.start(token))
        await ready.wait()

        guild = client.get_guild(guild_id) or await client.fetch_guild(guild_id)
        print(f"Guild: {guild.name} ({guild.id})")

        emojis = guild.emojis or tuple(await guild.fetch_emojis())
        print(f"Total: {len(emojis)} emojis\n")

        for e in sorted(emojis, key=lambda x: x.name.lower()):
            prefix = "a" if e.animated else ""
            fmt = f"<{prefix}:{e.name}:{e.id}>"
            print(f"{e.name:<30} {e.id:<22} {fmt}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run python scripts/list_emojis.py <guild_id>")
        sys.exit(1)
    asyncio.run(main(int(sys.argv[1])))
