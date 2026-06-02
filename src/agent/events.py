"""Dataclasses for agent streaming events and channel context."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AgentEventType(str, Enum):
    TEXT = "text"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    DONE = "done"
    ERROR = "error"


@dataclass(frozen=True)
class AgentEvent:
    type: AgentEventType
    text: str | None = None
    tool_name: str | None = None
    tool_args: dict | None = None
    tool_result: str | None = None
    session_id: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ChannelMsg:
    author: str
    content: str
    created_at: datetime

    def format_line(self) -> str:
        return f"{self.author}: {self.content}"


def trim_to_char_budget(
    msgs: list[ChannelMsg], budget: int
) -> list[ChannelMsg]:
    """Drop oldest messages until the formatted lines fit within `budget` chars.

    Character count is used as a rough token proxy. Walks from newest to oldest,
    keeping messages while the running total stays within budget. Always keeps at
    least the newest message, even if it alone exceeds the budget.
    """
    if not msgs:
        return []

    kept: list[ChannelMsg] = []
    total = 0
    for msg in reversed(msgs):
        total += len(msg.format_line())
        if kept and total > budget:
            break
        kept.append(msg)
    kept.reverse()
    return kept
