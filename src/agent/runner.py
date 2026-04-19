"""AgentRunner: façade over claude_agent_sdk.query with resume & sandbox."""

from typing import AsyncIterator, Literal

from claude_agent_sdk import (
    ClaudeAgentOptions,
    query as sdk_query,
)

from src.agent.config import AgentConfig
from src.agent.events import AgentEvent, AgentEventType, ChannelMsg
from src.agent.prompt import build_system_prompt
from src.agent.tools.discord_mcp import DiscordToolset
from src.agent.tools.job_analysis_mcp import analyze_104_job_impl  # noqa: F401
from src.agent.tools.job_search_mcp import search_104_jobs_impl  # noqa: F401


Mode = Literal["oneshot", "chat", "work", "dm"]


def _format_channel_context(ctx: list[ChannelMsg]) -> str:
    if not ctx:
        return ""
    lines = ["[Channel recent messages (oldest → newest)]"]
    for m in ctx:
        lines.append(m.format_line())
    return "\n".join(lines)


class AgentRunner:
    def __init__(
        self,
        config: AgentConfig,
        discord_toolset: DiscordToolset | None,
    ):
        self.config = config
        self.discord = discord_toolset

    def _build_prompt_input(
        self,
        user_input: str,
        channel_context: list[ChannelMsg] | None,
    ) -> str:
        preamble = _format_channel_context(channel_context or [])
        if not preamble:
            return user_input
        return f"{preamble}\n\n[User's current message]\n{user_input}"

    def _build_options(
        self,
        mode: Mode,
        user_id: str,
        thread_id: str | None,
        resume: str | None,
    ) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            model=self.config.model,
            system_prompt=build_system_prompt(
                mode=mode, user_id=user_id, thread_id=thread_id
            ),
            allowed_tools=list(self.config.allowed_tools),
            cwd=str(self.config.data_dir),
            max_turns=self.config.max_turns,
            resume=resume,
        )

    async def run(
        self,
        user_input: str,
        mode: Mode,
        user_id: str,
        *,
        resume: str | None = None,
        channel_context: list[ChannelMsg] | None = None,
        thread_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        prompt_input = self._build_prompt_input(user_input, channel_context)
        options = self._build_options(mode, user_id, thread_id, resume)

        session_id: str | None = None

        try:
            async for msg in sdk_query(prompt=prompt_input, options=options):
                kind = getattr(msg, "kind", None) or msg.__class__.__name__.lower()

                if kind in ("assistant", "assistantmessage") and getattr(msg, "text", None):
                    yield AgentEvent(
                        type=AgentEventType.TEXT, text=msg.text
                    )
                elif kind in ("tool_use", "tooluse"):
                    yield AgentEvent(
                        type=AgentEventType.TOOL_START,
                        tool_name=getattr(msg, "tool_name", None),
                        tool_args=getattr(msg, "tool_input", None),
                    )
                elif kind in ("tool_result", "toolresult"):
                    yield AgentEvent(
                        type=AgentEventType.TOOL_RESULT,
                        tool_name=getattr(msg, "tool_name", None),
                        tool_result=getattr(msg, "tool_output", None),
                    )
                elif kind in ("result", "resultmessage"):
                    session_id = getattr(msg, "session_id", None)

        except Exception as exc:
            yield AgentEvent(type=AgentEventType.ERROR, error=str(exc))

        yield AgentEvent(type=AgentEventType.DONE, session_id=session_id)
