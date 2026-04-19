"""Stream AgentEvent text into one or more Discord messages with throttled edits."""

import asyncio
import time
from typing import TYPE_CHECKING

from src.agent.events import AgentEvent, AgentEventType

if TYPE_CHECKING:
    import discord


MAX_MSG_LEN = 2000
DEFAULT_FLUSH_INTERVAL = 1.0


class DiscordStreamer:
    """Accepts AgentEvent's, batches text, and edits a Discord message in place."""

    def __init__(
        self,
        channel: "discord.abc.Messageable",
        *,
        reply_to: "discord.Message | None" = None,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
    ):
        self._channel = channel
        self._reply_to = reply_to
        self._flush_interval = flush_interval
        self._buffer: str = ""
        self._last_flush: float = 0.0
        self._current_msg = None
        self._current_len = 0

    async def handle(self, event: AgentEvent) -> None:
        if event.type == AgentEventType.TEXT and event.text:
            self._buffer += event.text
            await self._maybe_flush()
            return
        if event.type == AgentEventType.ERROR and event.error:
            await self._send_new(f"主人，出了點差錯… `{event.error}`")
            return
        # TOOL_START / TOOL_RESULT / DONE are no-ops for the streamer.

    async def _maybe_flush(self) -> None:
        now = time.monotonic()
        if now - self._last_flush < self._flush_interval:
            return
        await self._flush()
        self._last_flush = now

    async def _flush(self) -> None:
        if not self._buffer:
            return

        text = self._buffer
        self._buffer = ""

        if self._current_msg is None:
            await self._send_new(text[:MAX_MSG_LEN])
            rest = text[MAX_MSG_LEN:]
        else:
            room = MAX_MSG_LEN - self._current_len
            if room > 0:
                chunk = text[:room]
                await self._edit_current(self._current_content() + chunk)
                rest = text[room:]
            else:
                rest = text

        while rest:
            chunk = rest[:MAX_MSG_LEN]
            await self._send_new(chunk)
            rest = rest[MAX_MSG_LEN:]

    def _current_content(self) -> str:
        return getattr(self._current_msg, "_streamed_content", "")

    async def _send_new(self, content: str) -> None:
        kwargs: dict = {"content": content}
        if self._reply_to is not None and self._current_msg is None:
            kwargs["reference"] = self._reply_to
        msg = await self._channel.send(**kwargs)
        try:
            setattr(msg, "_streamed_content", content)
        except Exception:
            pass
        self._current_msg = msg
        self._current_len = len(content)

    async def _edit_current(self, content: str) -> None:
        await self._current_msg.edit(content=content)
        try:
            setattr(self._current_msg, "_streamed_content", content)
        except Exception:
            pass
        self._current_len = len(content)

    async def finalize(self) -> None:
        await self._flush()
        # Smooth out race where flush was throttled on the last chunk.
        await asyncio.sleep(0)
