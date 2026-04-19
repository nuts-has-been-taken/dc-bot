"""Agent-side configuration and permission whitelists."""

from dataclasses import dataclass, field
from pathlib import Path


ALLOWED_TOOLS: list[str] = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "WebSearch",
    "WebFetch",
]

ALLOWED_PATHS: list[str] = ["data/"]
DISALLOWED_PATHS: list[str] = [
    "src/",
    "bot.py",
    ".env",
    "pyproject.toml",
    "uv.lock",
]


@dataclass(frozen=True)
class AgentConfig:
    data_dir: Path
    db_path: Path
    model: str = "claude-sonnet-4-6"
    max_turns: int = 20
    timeout_seconds: int = 60

    allowed_tools: list[str] = field(default_factory=lambda: ALLOWED_TOOLS.copy())
    allowed_paths: list[str] = field(default_factory=lambda: ALLOWED_PATHS.copy())
    disallowed_paths: list[str] = field(
        default_factory=lambda: DISALLOWED_PATHS.copy()
    )
