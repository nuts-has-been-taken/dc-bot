"""AgentRunner: façade over claude_agent_sdk.query with resume & sandbox."""

from pathlib import Path
from typing import Any, AsyncIterator, Literal

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query as sdk_query,
)

from src.agent.config import AgentConfig
from src.agent.events import AgentEvent, AgentEventType, ChannelMsg
from src.agent.prompt import build_system_prompt
from src.agent.tools.discord_mcp import DiscordToolset
from src.agent.tools.registry import (
    build_discord_server,
    build_job_analysis_server,
    build_job_search_server,
)


Mode = Literal["oneshot", "chat", "work", "dm"]

# Filesystem tools that should be sandbox-checked
_FS_TOOLS = frozenset({"Read", "Write", "Edit", "Glob", "Grep"})


async def _prompt_async_iter(text: str):
    """Wrap a plain string into the AsyncIterable[dict] envelope the SDK expects.

    The SDK's streaming protocol requires each dict to have the shape:
        {"type": "user", "message": {"role": "user", "content": "..."}, ...}

    Passing a plain str is rejected when can_use_tool is set on the options.
    """
    yield {
        "type": "user",
        "message": {"role": "user", "content": text},
        "parent_tool_use_id": None,
        "session_id": None,
    }


def _format_channel_context(ctx: list[ChannelMsg]) -> str:
    if not ctx:
        return ""
    lines = ["[Channel recent messages (oldest → newest)]"]
    for m in ctx:
        lines.append(m.format_line())
    return "\n".join(lines)


def _make_path_guard(allowed_root: Path):
    """Return a can_use_tool callback that restricts FS tools to allowed_root."""
    allowed_root = allowed_root.resolve()

    async def can_use_tool(
        tool_name: str, tool_input: dict[str, Any], ctx: Any
    ) -> PermissionResultAllow | PermissionResultDeny:
        if tool_name not in _FS_TOOLS:
            return PermissionResultAllow()

        # Pick the path-ish key per tool
        if tool_name == "Glob":
            raw_path = tool_input.get("path") or tool_input.get("pattern") or ""
        elif tool_name == "Grep":
            raw_path = tool_input.get("path") or ""
        else:  # Read / Write / Edit
            raw_path = tool_input.get("file_path") or ""

        if not raw_path:
            return PermissionResultAllow()

        try:
            target = Path(raw_path)
            if not target.is_absolute():
                target = (allowed_root / target).resolve()
            else:
                target = target.resolve()
            # Ensure target is within allowed_root
            target.relative_to(allowed_root)
        except (ValueError, OSError):
            return PermissionResultDeny(
                message=f"Path '{raw_path}' is outside the data/ sandbox.",
            )
        return PermissionResultAllow()

    return can_use_tool


class AgentRunner:
    def __init__(
        self,
        config: AgentConfig,
        discord_toolset: DiscordToolset | None,
    ):
        self.config = config
        self.discord = discord_toolset

        # Build MCP servers once at construction time
        self._mcp_servers: dict = {
            "job_search": build_job_search_server(),
            "job_analysis": build_job_analysis_server(),
        }
        if discord_toolset is not None:
            self._mcp_servers["discord"] = build_discord_server(discord_toolset)

        # MCP tool names built from whichever servers are present
        self._mcp_tool_names: list[str] = [
            "mcp__job_search__search_104_jobs",
            "mcp__job_analysis__analyze_104_job",
        ]
        if discord_toolset is not None:
            self._mcp_tool_names.extend([
                "mcp__discord__fetch_channel_history",
                "mcp__discord__send_embed",
                "mcp__discord__react_to_message",
                "mcp__discord__get_member_info",
            ])

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
        user_name: str,
        user_id: str,
        thread_id: str | None,
        resume: str | None,
    ) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            model=self.config.model,
            system_prompt=build_system_prompt(
                mode=mode,
                user_name=user_name,
                user_id=user_id,
                thread_id=thread_id,
                owner_id=self.config.owner_id,
            ),
            allowed_tools=list(self.config.allowed_tools) + self._mcp_tool_names,
            cwd=str(self.config.data_dir),
            max_turns=self.config.max_turns,
            resume=resume,
            mcp_servers=self._mcp_servers,
            can_use_tool=_make_path_guard(self.config.data_dir),
        )

    async def run(
        self,
        user_input: str,
        mode: Mode,
        user_name: str,
        user_id: str = "",
        *,
        resume: str | None = None,
        channel_context: list[ChannelMsg] | None = None,
        thread_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        prompt_input = self._build_prompt_input(user_input, channel_context)
        options = self._build_options(mode, user_name, user_id, thread_id, resume)

        session_id: str | None = None

        try:
            async for msg in sdk_query(prompt=_prompt_async_iter(prompt_input), options=options):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            if block.text:
                                yield AgentEvent(type=AgentEventType.TEXT, text=block.text)
                        elif isinstance(block, ToolUseBlock):
                            yield AgentEvent(
                                type=AgentEventType.TOOL_START,
                                tool_name=block.name,
                                tool_args=block.input,
                            )
                elif isinstance(msg, UserMessage):
                    # Often contains tool_result blocks in multi-turn tool calls
                    for block in getattr(msg, "content", []) or []:
                        if isinstance(block, ToolResultBlock):
                            text = block.content if isinstance(block.content, str) else str(block.content)
                            yield AgentEvent(
                                type=AgentEventType.TOOL_RESULT,
                                tool_result=text,
                            )
                elif isinstance(msg, ResultMessage):
                    session_id = getattr(msg, "session_id", None)
                elif isinstance(msg, SystemMessage):
                    # informational; ignore
                    pass

        except Exception as exc:
            yield AgentEvent(type=AgentEventType.ERROR, error=str(exc))

        yield AgentEvent(type=AgentEventType.DONE, session_id=session_id)
