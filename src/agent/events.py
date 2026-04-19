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
