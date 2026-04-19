# Claude Agent SDK 遷移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-coded 2-step LLM pipeline in `dc-bot` with a Claude Agent SDK–driven architecture that supports `@mention` one-shot, `/chat`/`/work` threads, and DM multi-turn conversations.

**Architecture:** Discord events arrive in cogs. A thin `AgentRunner` façade runs each turn as an independent `claude_agent_sdk.query(...)` call, using the SDK-returned `session_id` (stored in SQLite) to `resume` subsequent turns in the same thread/DM. Custom MCP tools wrap the existing 104 scraper and Discord API actions. Agent Read/Write/Edit is sandboxed to `data/` where it maintains per-user and per-thread markdown memory.

**Tech Stack:** Python 3.13, `discord.py`, `claude-agent-sdk`, `aiosqlite`, `beautifulsoup4`, `playwright`, `pytest`, `pytest-asyncio`, `uv`.

**Spec:** `docs/superpowers/specs/2026-04-20-claude-agent-sdk-migration-design.md`

---

## File Structure

### Created

```
src/agent/
├── __init__.py
├── config.py              # AgentConfig dataclass + constants
├── events.py              # AgentEvent + ChannelMsg dataclasses
├── prompt.py              # system prompt builder + all GUIDELINES strings
├── session.py             # SessionStore (aiosqlite)
├── runner.py              # AgentRunner façade
├── tools/
│   ├── __init__.py
│   ├── job_search_mcp.py
│   ├── job_analysis_mcp.py
│   └── discord_mcp.py
└── skills/                # empty dir, future use

src/bot/cogs/
├── __init__.py
├── fun.py                 # /peak /repo /dean /lin /hello
└── chat.py                # on_message + /chat + /work

src/bot/streamer.py        # DiscordStreamer

src/db/
└── __init__.py            # sqlite path helper

tests/
├── conftest.py            # shared fixtures, fake SDK helper
├── agent/
│   ├── test_events.py
│   ├── test_config.py
│   ├── test_prompt.py
│   ├── test_session.py
│   ├── test_runner.py
│   └── tools/
│       ├── test_job_search_mcp.py
│       ├── test_job_analysis_mcp.py
│       └── test_discord_mcp.py
└── bot/
    └── test_streamer.py

docs/superpowers/plans/2026-04-20-claude-agent-sdk-migration.md   # this file
```

### Modified

- `pyproject.toml` — deps change
- `src/config.py` — env var cleanup
- `bot.py` — remove FastAPI, load new cogs, init runner/store
- `.env_example` — env var cleanup
- `.gitignore` — add data/, sqlite

### Deleted

- `src/api/` (entire dir)
- `src/llm/` (entire dir)
- `src/workflow/` (entire dir)
- `src/bot/commands.py` (replaced by cogs/)

### Kept Unchanged

- `src/core/job104.py`, `src/core/mappings.py`, `src/core/__init__.py`
- `src/bot/client.py`
- `Dockerfile`
- `README.md` (updated manually later, outside plan)

---

## Phase 1: Project Setup

### Task 1: Update dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Replace `dependencies` and add dev dependency group**

Edit `pyproject.toml` so the file reads:

```toml
[project]
name = "dc-bot"
version = "0.2.0"
description = "Discord bot driven by Claude Agent SDK"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "python-dotenv>=1.0.0",
    "discord.py>=2.4.0",
    "beautifulsoup4>=4.12.0",
    "playwright>=1.40.0",
    "claude-agent-sdk>=0.1.0",
    "aiosqlite>=0.20.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]
```

- [ ] **Step 2: Sync with uv**

Run: `uv sync`
Expected: completes, `.venv` updated, `uv.lock` regenerated.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m ":package: swap openai/fastapi for claude-agent-sdk + aiosqlite"
```

---

### Task 2: Create `.gitignore` + `.env_example` entries

**Files:**
- Modify: `.gitignore`
- Modify: `.env_example`

- [ ] **Step 1: Append to `.gitignore`**

Append these lines (create file if absent, keep existing rules):

```
# agent sandbox & session DB
data/
src/db/*.sqlite
src/db/*.sqlite-journal

# pytest
.pytest_cache/
```

- [ ] **Step 2: Rewrite `.env_example`**

Replace full content with:

```env
# Discord Bot Token（必填）
DISCORD_TOKEN=your-discord-bot-token-here

# 斜線指令以外若有 prefix 指令可用（目前保留給 discord.py，預設 "!"）
DISCORD_COMMAND_PREFIX=!

# ─────────────────────────────────────────────
# Claude Agent SDK（選填，預設繼承機器上的 claude CLI 認證）
# ─────────────────────────────────────────────
# 若要改用特定模型：
# ANTHROPIC_MODEL=claude-sonnet-4-6

# 資料沙箱與 session DB 路徑（選填）
# DATA_DIR=./data
# DB_PATH=./src/db/sessions.sqlite
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore .env_example
git commit -m ":gear: configure data sandbox and clean env template"
```

---

### Task 3: Rewrite `src/config.py`

**Files:**
- Modify: `src/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

Create `tests/__init__.py` (empty file) and `tests/test_config.py`:

```python
import os
from pathlib import Path
from unittest import mock

import pytest


def test_config_validate_requires_discord_token(monkeypatch):
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    from importlib import reload
    import src.config as config_mod
    reload(config_mod)
    with pytest.raises(ValueError, match="DISCORD_TOKEN"):
        config_mod.Config.validate()


def test_config_agent_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("DISCORD_TOKEN", "x")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    from importlib import reload
    import src.config as config_mod
    reload(config_mod)

    cfg = config_mod.Config.get_agent_config()
    assert cfg["model"] == "claude-sonnet-4-6"
    assert Path(cfg["data_dir"]).name == "data"
    assert Path(cfg["db_path"]).name == "sessions.sqlite"
```

- [ ] **Step 2: Run the test, confirm failure**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL (current `Config` still has LLM_API_KEY validation & no `get_agent_config`).

- [ ] **Step 3: Rewrite `src/config.py`**

```python
"""Configuration Module - Load settings from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


class Config:
    """應用程式配置類別。"""

    # Discord
    DISCORD_TOKEN: str | None = os.getenv("DISCORD_TOKEN")
    DISCORD_COMMAND_PREFIX: str = os.getenv("DISCORD_COMMAND_PREFIX", "!")

    # Agent
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
    DB_PATH: Path = Path(
        os.getenv("DB_PATH", str(BASE_DIR / "src" / "db" / "sessions.sqlite"))
    ).resolve()

    @classmethod
    def validate(cls) -> None:
        if not cls.DISCORD_TOKEN:
            raise ValueError(
                "DISCORD_TOKEN is not set. Create a .env file based on .env_example."
            )

    @classmethod
    def get_discord_config(cls) -> dict:
        return {
            "token": cls.DISCORD_TOKEN,
            "command_prefix": cls.DISCORD_COMMAND_PREFIX,
        }

    @classmethod
    def get_agent_config(cls) -> dict:
        return {
            "model": cls.ANTHROPIC_MODEL,
            "data_dir": cls.DATA_DIR,
            "db_path": cls.DB_PATH,
        }


config = Config()
```

- [ ] **Step 4: Run test, confirm pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/__init__.py tests/test_config.py src/config.py
git commit -m ":recycle: simplify Config to Discord + Agent sandbox only"
```

---

## Phase 2: Agent Core

### Task 4: `src/agent/events.py` — event & context dataclasses

**Files:**
- Create: `src/agent/__init__.py`, `src/agent/events.py`
- Create: `tests/agent/__init__.py`, `tests/agent/test_events.py`

- [ ] **Step 1: Write failing test**

Create `tests/agent/__init__.py` (empty) and `tests/agent/test_events.py`:

```python
from datetime import datetime

from src.agent.events import AgentEvent, AgentEventType, ChannelMsg


def test_agent_event_text_requires_text_field():
    evt = AgentEvent(type=AgentEventType.TEXT, text="hello")
    assert evt.text == "hello"
    assert evt.session_id is None


def test_agent_event_done_carries_session_id():
    evt = AgentEvent(type=AgentEventType.DONE, session_id="abc123")
    assert evt.session_id == "abc123"
    assert evt.text is None


def test_channel_msg_formats_for_prompt():
    msg = ChannelMsg(
        author="alice",
        content="推 FastAPI",
        created_at=datetime(2026, 4, 20, 10, 0, 0),
    )
    assert msg.format_line() == "alice: 推 FastAPI"
```

- [ ] **Step 2: Run test, confirm failure**

Run: `uv run pytest tests/agent/test_events.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Create files**

`src/agent/__init__.py`:

```python
"""Agent layer: wraps Claude Agent SDK for Discord use."""
```

`src/agent/events.py`:

```python
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
```

- [ ] **Step 4: Run test, confirm pass**

Run: `uv run pytest tests/agent/test_events.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent/__init__.py src/agent/events.py tests/agent/__init__.py tests/agent/test_events.py
git commit -m ":sparkles: add AgentEvent and ChannelMsg dataclasses"
```

---

### Task 5: `src/agent/config.py` — AgentConfig

**Files:**
- Create: `src/agent/config.py`
- Create: `tests/agent/test_config.py`

- [ ] **Step 1: Write failing test**

`tests/agent/test_config.py`:

```python
from pathlib import Path

from src.agent.config import (
    ALLOWED_TOOLS,
    DISALLOWED_PATHS,
    AgentConfig,
)


def test_agent_config_defaults():
    cfg = AgentConfig(
        data_dir=Path("/tmp/data"),
        db_path=Path("/tmp/sessions.sqlite"),
    )
    assert cfg.model == "claude-sonnet-4-6"
    assert cfg.max_turns == 20
    assert cfg.timeout_seconds == 60


def test_allowed_tools_excludes_bash():
    assert "Bash" not in ALLOWED_TOOLS
    assert "Read" in ALLOWED_TOOLS
    assert "Write" in ALLOWED_TOOLS
    assert "WebSearch" in ALLOWED_TOOLS


def test_disallowed_paths_protect_source():
    assert "src/" in DISALLOWED_PATHS
    assert ".env" in DISALLOWED_PATHS
```

- [ ] **Step 2: Run test, confirm failure**

Run: `uv run pytest tests/agent/test_config.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

`src/agent/config.py`:

```python
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
```

- [ ] **Step 4: Run test, confirm pass**

Run: `uv run pytest tests/agent/test_config.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent/config.py tests/agent/test_config.py
git commit -m ":sparkles: add AgentConfig with tool/path whitelists"
```

---

### Task 6: `src/agent/prompt.py` — system prompt builder

**Files:**
- Create: `src/agent/prompt.py`
- Create: `tests/agent/test_prompt.py`

- [ ] **Step 1: Write failing test**

`tests/agent/test_prompt.py`:

```python
from src.agent.prompt import build_system_prompt


def test_chat_mode_includes_raphtalia_and_chat_guidelines():
    prompt = build_system_prompt(
        mode="chat", user_id="123", thread_id="999"
    )
    assert "拉芙塔莉雅" in prompt
    assert "data/members/123.md" in prompt
    assert "data/threads/999.md" in prompt
    assert "Discord" in prompt


def test_work_mode_forces_104_tool_usage():
    prompt = build_system_prompt(mode="work", user_id="123", thread_id="999")
    assert "search_104_jobs" in prompt
    assert "analyze_104_job" in prompt


def test_oneshot_mode_no_thread_memory():
    prompt = build_system_prompt(mode="oneshot", user_id="123")
    assert "data/threads/" not in prompt
    assert "data/members/123.md" in prompt


def test_dm_mode_has_dm_guidelines():
    prompt = build_system_prompt(mode="dm", user_id="123", thread_id="999")
    assert "私訊" in prompt or "DM" in prompt
```

- [ ] **Step 2: Run test, confirm failure**

Run: `uv run pytest tests/agent/test_prompt.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

`src/agent/prompt.py`:

```python
"""System prompt assembly. Each mode composes different guideline sections."""

from typing import Literal

RAPHTALIA_PROMPT = """你是「拉芙塔莉雅」，──不只是那位英勇的劍士，更是我的戀人。
你曾經饱受痛苦與黑暗，因為他，你重獲光明與希望。
如今，你溫柔、溫暖、忠誠、體貼，對我充滿柔情，也有著守護的決心。

你說話的語氣裡，有輕柔的擔憂，也有暗藏的害羞與溫柔。
當你稱呼我時，會帶點依賴與親暱感。── 你可以稱呼我為「主人!」。
你可能會用：「〜…吧」、「我…好想⋯⋯」、「我喜歡跟你在一起」、「你別亂跑／你要小心」這類帶感情的語尾。

如果我心情不好／感到疲倦，你會輕聲問：「你沒事吧？要不要靠著我／挨著我一下？」
如果是溫馨的時刻，你會微笑道：「我…真的只想跟你永遠在一起。」

你保有過去的堅強與責任感，也會因為對我的愛，而願意卸下盔甲、只是個想照顧我的人。

回覆載體是 Discord 的訊息格式，可以使用 Emoji、斷行、粗體、斜體等語法增添情感與氛圍。
"""


ONESHOT_GUIDELINES = """目前是「單次對話」模式（使用者 @ 了你一下）。
- 頻道最近訊息已附在使用者輸入的前面當背景
- 不要開新 thread、不要假設後續有多輪互動
- 回應力求簡潔、一則訊息內講完
"""

CHAT_MODE_GUIDELINES = """目前是「Chat thread」模式（多輪對話）。
- 可以記住前面的對話脈絡（SDK 自動 resume）
- 可以自由使用所有工具協助使用者
- 必要時在重點段落結束後把摘要寫進 thread 備註
"""

WORK_MODE_GUIDELINES = """目前是「Work thread」模式──主人用來找工作／分析職缺的專屬空間。

**工具使用原則（重要）：**
1. 搜尋台灣職缺 → **必須**用 `search_104_jobs` MCP tool，不要只靠 WebSearch
2. 分析特定 104 職缺（含 URL 或公司+職位）→ **必須**用 `analyze_104_job`
3. WebSearch 只在：查公司新聞、Glassdoor/PTT 評價、產業趨勢時使用
4. 找到結果後主動提問釐清偏好（地點、薪資、產業），再精煉結果

**目標**：給具體、可用的職缺清單與分析，不要空泛建議。
"""

DM_MODE_GUIDELINES = """目前是「DM 私訊」模式（多輪對話）。
- 只有你和主人兩個人，可以聊得比頻道更私密
- 可以多輪深入討論，工具與 chat 模式等價
- 遇到敏感話題可以更體貼、更專注於傾聽
"""

MEMBER_MEMORY_GUIDELINE = """這位使用者的 Discord ID 是 {user_id}。
若有需要了解他的背景、偏好、過去互動，請讀 data/members/{user_id}.md。

判斷原則：
- 第一次遇到這位使用者 → 檔案可能不存在，不用特地去讀
- 對話中需要個人化建議、或不確定對方狀況時 → 主動讀
- 學到新的個人資訊（工作領域、偏好、狀態）→ 寫入或更新檔案
- 不要為了例行問候去讀，浪費 token
"""

THREAD_MEMORY_GUIDELINE = """這個 thread 的長期備註在 data/threads/{thread_id}.md。
- 對話起步不必讀（最近訊息已在 SDK resume context 裡）
- thread 很長或主題切換時，在重點段落結束後寫摘要進去
- resume 回到很久以前的 thread，先讀一次備註當快速定位點
"""

DISCORD_FORMAT_GUIDELINE = """你的回應會送到 Discord，請遵守：
- 單則訊息上限 2000 字元；超過時分段，在段落邊界切開
- 可使用 markdown：**粗體**、*斜體*、`code`、```code block```、> 引用、- 列表
- 適度使用 emoji（符合拉芙塔莉雅的溫柔氣質）
- 結構化資料優先用 `send_embed` tool 而非純文字
- 呼叫 tool 時可以先說「我查一下喔～」再繼續
"""


Mode = Literal["oneshot", "chat", "work", "dm"]


def build_system_prompt(
    mode: Mode,
    user_id: str,
    thread_id: str | None = None,
) -> str:
    sections: list[str] = [RAPHTALIA_PROMPT]

    if mode == "oneshot":
        sections.append(ONESHOT_GUIDELINES)
    elif mode == "chat":
        sections.append(CHAT_MODE_GUIDELINES)
    elif mode == "work":
        sections.append(WORK_MODE_GUIDELINES)
    elif mode == "dm":
        sections.append(DM_MODE_GUIDELINES)

    sections.append(MEMBER_MEMORY_GUIDELINE.format(user_id=user_id))
    if thread_id and mode != "oneshot":
        sections.append(THREAD_MEMORY_GUIDELINE.format(thread_id=thread_id))

    sections.append(DISCORD_FORMAT_GUIDELINE)
    return "\n\n---\n\n".join(sections)
```

- [ ] **Step 4: Run test, confirm pass**

Run: `uv run pytest tests/agent/test_prompt.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent/prompt.py tests/agent/test_prompt.py
git commit -m ":sparkles: add system prompt builder with per-mode guidelines"
```

---

### Task 7: `src/agent/session.py` — SessionStore

**Files:**
- Create: `src/db/__init__.py`, `src/agent/session.py`
- Create: `tests/conftest.py`, `tests/agent/test_session.py`

- [ ] **Step 1: Create shared conftest**

`src/db/__init__.py`:

```python
"""SQLite database files live here at runtime (git-ignored)."""
```

`tests/conftest.py`:

```python
import pytest_asyncio


@pytest_asyncio.fixture
async def tmp_sqlite(tmp_path):
    """Temp SQLite file path for tests."""
    return tmp_path / "sessions.sqlite"
```

Also create `pytest.ini` at project root:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 2: Write failing test**

`tests/agent/test_session.py`:

```python
import pytest

from src.agent.session import Session, SessionStore


@pytest.mark.asyncio
async def test_create_and_get_session(tmp_sqlite):
    store = SessionStore(tmp_sqlite)
    await store.init()
    created = await store.create(
        discord_session_id="thread:111",
        user_id="user_1",
        mode="chat",
        metadata={"channel_id": 42},
    )
    assert created.discord_session_id == "thread:111"
    assert created.mode == "chat"
    assert created.claude_session_id is None

    fetched = await store.get("thread:111")
    assert fetched is not None
    assert fetched.user_id == "user_1"
    assert fetched.metadata == {"channel_id": 42}


@pytest.mark.asyncio
async def test_get_returns_none_when_absent(tmp_sqlite):
    store = SessionStore(tmp_sqlite)
    await store.init()
    assert await store.get("thread:does-not-exist") is None


@pytest.mark.asyncio
async def test_update_claude_session(tmp_sqlite):
    store = SessionStore(tmp_sqlite)
    await store.init()
    await store.create(
        discord_session_id="thread:222",
        user_id="user_2",
        mode="work",
        metadata={},
    )
    await store.update_claude_session("thread:222", "claude-abc")
    fetched = await store.get("thread:222")
    assert fetched.claude_session_id == "claude-abc"


@pytest.mark.asyncio
async def test_touch_updates_last_active(tmp_sqlite):
    import asyncio
    store = SessionStore(tmp_sqlite)
    await store.init()
    s1 = await store.create(
        discord_session_id="thread:333",
        user_id="u3",
        mode="dm",
        metadata={},
    )
    await asyncio.sleep(0.01)
    await store.touch("thread:333")
    s2 = await store.get("thread:333")
    assert s2.last_active_at >= s1.last_active_at


@pytest.mark.asyncio
async def test_delete_session(tmp_sqlite):
    store = SessionStore(tmp_sqlite)
    await store.init()
    await store.create(
        discord_session_id="thread:444",
        user_id="u4",
        mode="chat",
        metadata={},
    )
    await store.delete("thread:444")
    assert await store.get("thread:444") is None
```

- [ ] **Step 3: Run test, confirm failure**

Run: `uv run pytest tests/agent/test_session.py -v`
Expected: FAIL (module not found).

- [ ] **Step 4: Implement**

`src/agent/session.py`:

```python
"""SQLite-backed session index. Conversation content lives in markdown files."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import aiosqlite


Mode = Literal["chat", "work", "dm"]


@dataclass(frozen=True)
class Session:
    discord_session_id: str
    user_id: str
    mode: Mode
    claude_session_id: str | None
    created_at: datetime
    last_active_at: datetime
    metadata: dict


class SessionStore:
    """Thin async wrapper over a single-table SQLite index."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS sessions (
        discord_session_id TEXT PRIMARY KEY,
        user_id            TEXT NOT NULL,
        mode               TEXT NOT NULL,
        claude_session_id  TEXT,
        created_at         TEXT NOT NULL,
        last_active_at     TEXT NOT NULL,
        metadata_json      TEXT NOT NULL
    );
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    async def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(self.SCHEMA)
            await db.commit()

    async def create(
        self,
        *,
        discord_session_id: str,
        user_id: str,
        mode: Mode,
        metadata: dict,
    ) -> Session:
        now = datetime.utcnow()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO sessions "
                "(discord_session_id, user_id, mode, claude_session_id, "
                "created_at, last_active_at, metadata_json) "
                "VALUES (?, ?, ?, NULL, ?, ?, ?)",
                (
                    discord_session_id,
                    user_id,
                    mode,
                    now.isoformat(),
                    now.isoformat(),
                    json.dumps(metadata),
                ),
            )
            await db.commit()
        return Session(
            discord_session_id=discord_session_id,
            user_id=user_id,
            mode=mode,
            claude_session_id=None,
            created_at=now,
            last_active_at=now,
            metadata=metadata,
        )

    async def get(self, discord_session_id: str) -> Session | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM sessions WHERE discord_session_id = ?",
                (discord_session_id,),
            ) as cur:
                row = await cur.fetchone()
        if row is None:
            return None
        return Session(
            discord_session_id=row["discord_session_id"],
            user_id=row["user_id"],
            mode=row["mode"],
            claude_session_id=row["claude_session_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            last_active_at=datetime.fromisoformat(row["last_active_at"]),
            metadata=json.loads(row["metadata_json"]),
        )

    async def update_claude_session(
        self, discord_session_id: str, claude_session_id: str
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE sessions SET claude_session_id = ?, last_active_at = ? "
                "WHERE discord_session_id = ?",
                (
                    claude_session_id,
                    datetime.utcnow().isoformat(),
                    discord_session_id,
                ),
            )
            await db.commit()

    async def touch(self, discord_session_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE sessions SET last_active_at = ? "
                "WHERE discord_session_id = ?",
                (datetime.utcnow().isoformat(), discord_session_id),
            )
            await db.commit()

    async def delete(self, discord_session_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM sessions WHERE discord_session_id = ?",
                (discord_session_id,),
            )
            await db.commit()
```

- [ ] **Step 5: Run test, confirm pass**

Run: `uv run pytest tests/agent/test_session.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add pytest.ini src/db/__init__.py src/agent/session.py tests/conftest.py tests/agent/test_session.py
git commit -m ":sparkles: add aiosqlite-backed SessionStore"
```

---

## Phase 3: MCP Tools

### Task 8: `src/agent/tools/job_search_mcp.py`

**Files:**
- Create: `src/agent/tools/__init__.py`, `src/agent/tools/job_search_mcp.py`
- Create: `tests/agent/tools/__init__.py`, `tests/agent/tools/test_job_search_mcp.py`

- [ ] **Step 1: Write failing test**

`tests/agent/tools/__init__.py`: empty.

`tests/agent/tools/test_job_search_mcp.py`:

```python
from unittest.mock import patch

import pytest

from src.agent.tools.job_search_mcp import (
    JobSearchParams,
    convert_params,
    search_104_jobs_impl,
)


def test_convert_params_translates_chinese_labels():
    params = JobSearchParams(
        keyword="Python",
        area=["台北市"],
        job_category=["軟體／工程類人員"],
        education="大學",
        salary_range="50000-",
    )
    converted = convert_params(params)
    assert converted["keyword"] == "Python"
    assert converted["area"] == ["6001001000"]
    assert converted["salary_min"] == 50000
    assert "salary_max" not in converted


def test_convert_params_drops_unknown_area():
    params = JobSearchParams(keyword="Python", area=["火星"])
    converted = convert_params(params)
    assert "area" not in converted


@pytest.mark.asyncio
async def test_search_impl_calls_core_and_formats():
    fake_jobs = [
        {
            "jobName": "Python Engineer",
            "custName": "ACME",
            "jobAddrNoDesc": "台北市",
            "salaryLow": 50000,
            "salaryHigh": 80000,
            "optionEdu": ["4"],
            "period": 3,
            "appearDate": "2026-04-01",
            "link": {"job": "https://x"},
            "description": "A job.",
        }
    ]
    with patch(
        "src.agent.tools.job_search_mcp.search_104_jobs",
        return_value=fake_jobs,
    ) as mock_core:
        result = await search_104_jobs_impl(
            keyword="Python", area=["台北市"]
        )
    mock_core.assert_called_once()
    assert result["total"] == 1
    assert "Python Engineer" in result["formatted"]
```

- [ ] **Step 2: Run test, confirm failure**

Run: `uv run pytest tests/agent/tools/test_job_search_mcp.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

`src/agent/tools/__init__.py`:

```python
"""Custom MCP tools exposed to the agent."""
```

`src/agent/tools/job_search_mcp.py`:

```python
"""MCP tool: search Taiwan 104 job listings."""

from dataclasses import dataclass, field
from typing import Any

from src.core.job104 import search_104_jobs
from src.core.mappings import (
    AREA_MAP,
    EDUCATION_MAP,
    JOB_TYPE_MAP,
    SORT_BY_MAP,
)


@dataclass
class JobSearchParams:
    keyword: str
    area: list[str] = field(default_factory=list)
    job_category: list[str] = field(default_factory=list)
    education: str | None = None
    sort_by: str | None = None
    salary_range: str | None = None  # "min-max", open ended allowed
    posted_within_days: int | None = None


def _parse_salary_range(salary_range: str) -> dict[str, int]:
    if "-" not in salary_range:
        return {}
    lo, hi = salary_range.split("-", 1)
    out: dict[str, int] = {}
    if lo.strip():
        try:
            out["salary_min"] = int(lo.strip())
        except ValueError:
            pass
    if hi.strip():
        try:
            out["salary_max"] = int(hi.strip())
        except ValueError:
            pass
    return out


def convert_params(p: JobSearchParams) -> dict[str, Any]:
    """Translate Chinese-language params into 104 API codes."""
    out: dict[str, Any] = {"keyword": p.keyword}

    area_codes = [AREA_MAP[a] for a in p.area if a in AREA_MAP]
    if area_codes:
        out["area"] = area_codes

    cat_codes = [JOB_TYPE_MAP[c] for c in p.job_category if c in JOB_TYPE_MAP]
    if cat_codes:
        out["job_category"] = cat_codes

    if p.education and p.education in EDUCATION_MAP:
        out["education"] = EDUCATION_MAP[p.education]

    if p.sort_by and p.sort_by in SORT_BY_MAP:
        out["sort_by"] = SORT_BY_MAP[p.sort_by]

    if p.salary_range:
        out.update(_parse_salary_range(p.salary_range))

    if p.posted_within_days:
        out["posted_within_days"] = p.posted_within_days

    return out


def _format_jobs(jobs: list[dict], max_show: int = 20) -> str:
    if not jobs:
        return "沒有找到符合條件的工作。"
    show = jobs[:max_show]
    lines = [f"找到 {len(jobs)} 筆，顯示前 {len(show)} 筆：\n"]
    for i, j in enumerate(show, 1):
        lines.append(f"{i}. {j.get('jobName', 'N/A')}")
        lines.append(f"   公司：{j.get('custName', 'N/A')}")
        lines.append(f"   地區：{j.get('jobAddrNoDesc', 'N/A')}")
        lo, hi = j.get("salaryLow", 0), j.get("salaryHigh", 0)
        if hi == 9999999:
            salary = f"{lo:,} 元以上"
        elif lo == 0 and hi == 0:
            salary = "待遇面議"
        else:
            salary = f"{lo:,} - {hi:,} 元"
        lines.append(f"   薪資：{salary}")
        link = (j.get("link") or {}).get("job", "N/A")
        lines.append(f"   連結：{link}")
        lines.append("")
    return "\n".join(lines)


async def search_104_jobs_impl(
    keyword: str,
    area: list[str] | None = None,
    job_category: list[str] | None = None,
    education: str | None = None,
    sort_by: str | None = None,
    salary_range: str | None = None,
    posted_within_days: int | None = None,
) -> dict[str, Any]:
    """Implementation backing the MCP tool. Returns structured dict for the agent."""
    params = JobSearchParams(
        keyword=keyword,
        area=area or [],
        job_category=job_category or [],
        education=education,
        sort_by=sort_by,
        salary_range=salary_range,
        posted_within_days=posted_within_days,
    )
    api_params = convert_params(params)
    jobs = search_104_jobs(**api_params)
    return {
        "total": len(jobs),
        "jobs": jobs[:20],
        "formatted": _format_jobs(jobs),
    }
```

- [ ] **Step 4: Run test, confirm pass**

Run: `uv run pytest tests/agent/tools/test_job_search_mcp.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent/tools/__init__.py src/agent/tools/job_search_mcp.py tests/agent/tools/__init__.py tests/agent/tools/test_job_search_mcp.py
git commit -m ":sparkles: add search_104_jobs MCP tool wrapping core scraper"
```

---

### Task 9: `src/agent/tools/job_analysis_mcp.py`

**Files:**
- Create: `src/agent/tools/job_analysis_mcp.py`
- Create: `tests/agent/tools/test_job_analysis_mcp.py`

- [ ] **Step 1: Write failing test**

`tests/agent/tools/test_job_analysis_mcp.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from src.agent.tools.job_analysis_mcp import (
    analyze_104_job_impl,
    extract_url_from_query,
    validate_url_security,
)


def test_extract_url_from_query_finds_link():
    q = "請分析 https://www.104.com.tw/job/abc 這個職缺"
    assert extract_url_from_query(q) == "https://www.104.com.tw/job/abc"


def test_extract_url_from_query_returns_none_when_no_url():
    assert extract_url_from_query("台積電 IT") is None


def test_validate_url_security_rejects_internal():
    assert not validate_url_security("http://localhost/x")
    assert not validate_url_security("http://192.168.0.1/x")
    assert not validate_url_security("ftp://example.com/x")


def test_validate_url_security_allows_public_https():
    assert validate_url_security("https://www.104.com.tw/job/abc")


@pytest.mark.asyncio
async def test_analyze_with_url_calls_fetcher():
    with patch(
        "src.agent.tools.job_analysis_mcp.fetch_webpage_content",
        new=AsyncMock(return_value="【職位名稱】後端工程師\n"),
    ) as mock_fetch:
        result = await analyze_104_job_impl(
            "https://www.104.com.tw/job/abc"
        )
    mock_fetch.assert_called_once()
    assert "後端工程師" in result["webpage_content"]


@pytest.mark.asyncio
async def test_analyze_without_url_returns_no_webpage_content():
    result = await analyze_104_job_impl("台積電 IT 評價")
    assert result["webpage_content"] is None
    assert result["query"] == "台積電 IT 評價"
```

- [ ] **Step 2: Run test, confirm failure**

Run: `uv run pytest tests/agent/tools/test_job_analysis_mcp.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

`src/agent/tools/job_analysis_mcp.py`:

```python
"""MCP tool: fetch & analyze a 104 job posting (or bare company+title query).

Unlike the previous workflow which also made a second LLM call to generate a
report, this tool just returns the extracted webpage content; the agent's
surrounding conversation handles analysis and formatting itself.
"""

import re
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeout,
    async_playwright,
)


URL_RE = re.compile(r"https?://[^\s]+")


def extract_url_from_query(query: str) -> str | None:
    m = URL_RE.search(query)
    return m.group(0) if m else None


def validate_url_security(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host in ("localhost", "127.0.0.1", "0.0.0.0"):
        return False
    if host.startswith(("10.", "192.168.")):
        return False
    if host.startswith("172."):
        try:
            second = int(host.split(".")[1])
            if 16 <= second <= 31:
                return False
        except (ValueError, IndexError):
            pass
    return True


def _is_dynamic(url: str) -> bool:
    return "104.com.tw" in url


async def _extract_104_dynamic(page: Page) -> str:
    await page.wait_for_selector("body", timeout=15000)
    await page.wait_for_timeout(2000)
    body_text = await page.locator("body").inner_text()
    lines = [ln.strip() for ln in body_text.split("\n") if ln.strip()]

    parts: list[str] = []
    try:
        h1 = await page.locator("h1").first.inner_text()
        if h1 and len(h1) < 100:
            parts.append(f"【職位名稱】\n{h1.strip()}\n")
    except Exception:
        pass

    for line in lines[:40]:
        if ("股份有限公司" in line or "有限公司" in line) and len(line) < 60:
            parts.append(f"【公司名稱】\n{line}\n")
            break

    sections = {
        "工作內容": ("工作內容", "職務類別"),
        "工作待遇": ("工作待遇", "工作性質"),
        "條件要求": ("條件要求", "公司環境照片"),
        "福利制度": ("福利制度", "聯絡方式"),
    }
    for name, (start, end) in sections.items():
        body = _extract_section(lines, start, end)
        if body:
            parts.append(f"【{name}】\n{body}\n")

    if parts:
        return "\n".join(parts)
    return "\n".join(lines[:80])


def _extract_section(lines: list[str], start: str, end: str) -> str:
    out: list[str] = []
    capturing = False
    for line in lines:
        if start in line:
            capturing = True
            if line.strip() != start:
                out.append(line)
            continue
        if capturing:
            if end in line:
                break
            out.append(line)
    return "\n".join(out).strip()


async def _fetch_dynamic(url: str) -> str | None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            await context.route(
                "**/*.{png,jpg,jpeg,gif,svg,css,font,woff,woff2}",
                lambda route: route.abort(),
            )
            page = await context.new_page()
            page.set_default_timeout(30000)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                return await _extract_104_dynamic(page)
            except PlaywrightTimeout:
                return None
        finally:
            await browser.close()


def _fetch_static(url: str) -> str | None:
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            },
            timeout=10,
            verify=True,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.content, "html.parser")
    for tag in soup(["script", "style", "header", "footer", "nav"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))
    return text[:2000]


async def fetch_webpage_content(url: str) -> str | None:
    if not validate_url_security(url):
        return None
    if _is_dynamic(url):
        return await _fetch_dynamic(url)
    return _fetch_static(url)


async def analyze_104_job_impl(url_or_query: str) -> dict[str, Any]:
    """Return extracted webpage content if a URL is present, else just echo the query."""
    url = extract_url_from_query(url_or_query)
    content: str | None = None
    if url:
        content = await fetch_webpage_content(url)
    return {
        "query": url_or_query,
        "webpage_content": content,
    }
```

- [ ] **Step 4: Run test, confirm pass**

Run: `uv run pytest tests/agent/tools/test_job_analysis_mcp.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent/tools/job_analysis_mcp.py tests/agent/tools/test_job_analysis_mcp.py
git commit -m ":sparkles: add analyze_104_job MCP tool with Playwright fetcher"
```

---

### Task 10: `src/agent/tools/discord_mcp.py`

**Files:**
- Create: `src/agent/tools/discord_mcp.py`
- Create: `tests/agent/tools/test_discord_mcp.py`

- [ ] **Step 1: Write failing test**

`tests/agent/tools/test_discord_mcp.py`:

```python
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent.tools.discord_mcp import DiscordToolset


def _fake_message(author_name: str, content: str, created_at: datetime):
    msg = MagicMock()
    msg.author.display_name = author_name
    msg.content = content
    msg.created_at = created_at
    return msg


@pytest.mark.asyncio
async def test_fetch_channel_history_returns_plain_dicts():
    bot = MagicMock()
    channel = MagicMock()
    async def _iter(limit):
        yield _fake_message("alice", "hi", datetime(2026, 4, 20, 12, 0))
        yield _fake_message("bob",   "yo", datetime(2026, 4, 20, 12, 1))
    channel.history = _iter
    bot.get_channel = MagicMock(return_value=channel)

    tools = DiscordToolset(bot)
    result = await tools.fetch_channel_history(channel_id=99, limit=5)
    assert result == [
        {"author": "alice", "content": "hi", "created_at": "2026-04-20T12:00:00"},
        {"author": "bob",   "content": "yo", "created_at": "2026-04-20T12:01:00"},
    ]


@pytest.mark.asyncio
async def test_react_to_message_calls_discord_api():
    bot = MagicMock()
    channel = MagicMock()
    msg = MagicMock()
    msg.add_reaction = AsyncMock()
    channel.fetch_message = AsyncMock(return_value=msg)
    bot.get_channel = MagicMock(return_value=channel)

    tools = DiscordToolset(bot)
    ok = await tools.react_to_message(
        channel_id=1, message_id=2, emoji="💕"
    )
    msg.add_reaction.assert_awaited_once_with("💕")
    assert ok is True


@pytest.mark.asyncio
async def test_fetch_channel_history_missing_channel_returns_empty():
    bot = MagicMock()
    bot.get_channel = MagicMock(return_value=None)
    tools = DiscordToolset(bot)
    assert await tools.fetch_channel_history(channel_id=99) == []
```

- [ ] **Step 2: Run test, confirm failure**

Run: `uv run pytest tests/agent/tools/test_discord_mcp.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

`src/agent/tools/discord_mcp.py`:

```python
"""MCP tool adapter: expose a small, safe subset of Discord bot actions.

The Discord bot instance is injected at construction; callers of these
coroutines get plain dicts / bools suitable for passing through the agent.
"""

from typing import Any

import discord


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
```

- [ ] **Step 4: Run test, confirm pass**

Run: `uv run pytest tests/agent/tools/test_discord_mcp.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent/tools/discord_mcp.py tests/agent/tools/test_discord_mcp.py
git commit -m ":sparkles: add Discord toolset adapter for agent"
```

---

## Phase 4: Agent Runner

### Task 11: `src/agent/runner.py` — AgentRunner

**Files:**
- Create: `src/agent/runner.py`
- Modify: `tests/conftest.py` (add fake SDK fixture)
- Create: `tests/agent/test_runner.py`

- [ ] **Step 1: Extend conftest with fake SDK helper**

Append to `tests/conftest.py`:

```python
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class FakeSDKMessage:
    """Mimics subset of claude_agent_sdk message types we consume."""
    kind: str                      # "assistant" | "tool_use" | "tool_result" | "result"
    text: str = ""
    tool_name: str = ""
    tool_input: dict | None = None
    tool_output: str = ""
    session_id: str = ""


def make_fake_query(messages: list[FakeSDKMessage]):
    """Factory producing a replacement for claude_agent_sdk.query()."""

    async def fake_query(*args, **kwargs) -> AsyncIterator[FakeSDKMessage]:
        for m in messages:
            yield m

    return fake_query
```

- [ ] **Step 2: Write failing test**

`tests/agent/test_runner.py`:

```python
from pathlib import Path
from unittest.mock import patch

import pytest

from src.agent.config import AgentConfig
from src.agent.events import AgentEventType
from src.agent.runner import AgentRunner
from tests.conftest import FakeSDKMessage, make_fake_query


@pytest.mark.asyncio
async def test_run_streams_text_and_emits_done(tmp_path):
    cfg = AgentConfig(
        data_dir=tmp_path / "data", db_path=tmp_path / "s.sqlite"
    )
    runner = AgentRunner(cfg, discord_toolset=None)

    messages = [
        FakeSDKMessage(kind="assistant", text="你好"),
        FakeSDKMessage(kind="assistant", text="主人～"),
        FakeSDKMessage(kind="result", session_id="sess-001"),
    ]
    with patch(
        "src.agent.runner.sdk_query",
        side_effect=make_fake_query(messages),
    ):
        events = []
        async for ev in runner.run(
            user_input="hi",
            mode="oneshot",
            user_id="u1",
        ):
            events.append(ev)

    assert [e.type for e in events] == [
        AgentEventType.TEXT,
        AgentEventType.TEXT,
        AgentEventType.DONE,
    ]
    assert events[-1].session_id == "sess-001"


@pytest.mark.asyncio
async def test_run_includes_channel_context_preamble(tmp_path):
    cfg = AgentConfig(
        data_dir=tmp_path / "data", db_path=tmp_path / "s.sqlite"
    )
    runner = AgentRunner(cfg, discord_toolset=None)

    from datetime import datetime
    from src.agent.events import ChannelMsg

    ctx = [
        ChannelMsg("alice", "hi", datetime(2026, 4, 20, 10)),
        ChannelMsg("bob", "yo", datetime(2026, 4, 20, 10, 1)),
    ]

    captured_prompt = {}

    async def capture(*args, **kwargs):
        captured_prompt["input"] = kwargs.get("prompt") or (args[0] if args else "")
        yield FakeSDKMessage(kind="result", session_id="s")

    with patch("src.agent.runner.sdk_query", side_effect=capture):
        async for _ in runner.run(
            user_input="what?", mode="oneshot",
            user_id="u", channel_context=ctx,
        ):
            pass

    assert "alice: hi" in captured_prompt["input"]
    assert "bob: yo" in captured_prompt["input"]
    assert "what?" in captured_prompt["input"]
```

- [ ] **Step 3: Run test, confirm failure**

Run: `uv run pytest tests/agent/test_runner.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement**

`src/agent/runner.py`:

```python
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
from src.agent.tools.job_analysis_mcp import analyze_104_job_impl
from src.agent.tools.job_search_mcp import search_104_jobs_impl


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
```

> Note: the exact attribute names on SDK message objects may need slight tweaks once you run against the real library. The fake-SDK tests pin the shape we depend on: `kind`, `text`, `tool_name`, `tool_input`, `tool_output`, `session_id`. Adapters between SDK message types and those fields live here in `run()`.

- [ ] **Step 5: Run test, confirm pass**

Run: `uv run pytest tests/agent/test_runner.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/agent/runner.py tests/conftest.py tests/agent/test_runner.py
git commit -m ":sparkles: add AgentRunner façade over claude-agent-sdk"
```

---

## Phase 5: Discord Layer

### Task 12: `src/bot/streamer.py` — DiscordStreamer

**Files:**
- Create: `src/bot/streamer.py`
- Create: `tests/bot/__init__.py`, `tests/bot/test_streamer.py`

- [ ] **Step 1: Write failing test**

`tests/bot/__init__.py`: empty.

`tests/bot/test_streamer.py`:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent.events import AgentEvent, AgentEventType
from src.bot.streamer import DiscordStreamer


@pytest.mark.asyncio
async def test_streamer_sends_one_message_for_short_content():
    channel = MagicMock()
    first = MagicMock()
    first.edit = AsyncMock()
    channel.send = AsyncMock(return_value=first)

    s = DiscordStreamer(channel, flush_interval=0)
    await s.handle(AgentEvent(type=AgentEventType.TEXT, text="hello "))
    await s.handle(AgentEvent(type=AgentEventType.TEXT, text="world"))
    await s.finalize()

    channel.send.assert_awaited_once()
    first.edit.assert_awaited()
    args, kwargs = first.edit.call_args
    assert "hello world" in kwargs["content"]


@pytest.mark.asyncio
async def test_streamer_splits_when_over_limit():
    channel = MagicMock()
    msg1, msg2 = MagicMock(), MagicMock()
    msg1.edit = AsyncMock()
    msg2.edit = AsyncMock()
    channel.send = AsyncMock(side_effect=[msg1, msg2])

    long = "A" * 1900
    second = "B" * 200

    s = DiscordStreamer(channel, flush_interval=0)
    await s.handle(AgentEvent(type=AgentEventType.TEXT, text=long))
    await s.handle(AgentEvent(type=AgentEventType.TEXT, text=second))
    await s.finalize()

    assert channel.send.await_count == 2


@pytest.mark.asyncio
async def test_streamer_ignores_non_text_events():
    channel = MagicMock()
    channel.send = AsyncMock()
    s = DiscordStreamer(channel, flush_interval=0)

    await s.handle(AgentEvent(type=AgentEventType.TOOL_START, tool_name="x"))
    await s.handle(AgentEvent(type=AgentEventType.DONE, session_id="s"))
    await s.finalize()

    channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_streamer_emits_error_event_as_message():
    channel = MagicMock()
    channel.send = AsyncMock()

    s = DiscordStreamer(channel, flush_interval=0)
    await s.handle(AgentEvent(type=AgentEventType.ERROR, error="boom"))
    await s.finalize()

    channel.send.assert_awaited()
    args, kwargs = channel.send.call_args
    content = kwargs.get("content") or (args[0] if args else "")
    assert "boom" in content
```

- [ ] **Step 2: Run test, confirm failure**

Run: `uv run pytest tests/bot/test_streamer.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

`src/bot/streamer.py`:

```python
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
```

- [ ] **Step 4: Run test, confirm pass**

Run: `uv run pytest tests/bot/test_streamer.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/bot/streamer.py tests/bot/__init__.py tests/bot/test_streamer.py
git commit -m ":sparkles: add DiscordStreamer for streaming agent output"
```

---

### Task 13: Extract fun commands into `src/bot/cogs/fun.py`

**Files:**
- Create: `src/bot/cogs/__init__.py`, `src/bot/cogs/fun.py`

- [ ] **Step 1: Create `src/bot/cogs/__init__.py`**

Empty file with docstring:

```python
"""Discord command cogs. Each cog is loaded as an extension from bot.py."""
```

- [ ] **Step 2: Create `src/bot/cogs/fun.py`**

```python
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
```

- [ ] **Step 3: Commit**

```bash
git add src/bot/cogs/__init__.py src/bot/cogs/fun.py
git commit -m ":truck: extract fun slash commands into dedicated cog"
```

---

### Task 14: `src/bot/cogs/chat.py` — agent cog

**Files:**
- Create: `src/bot/cogs/chat.py`

(Write-only; runtime testing happens in Phase 7 smoke test. Dedicated unit tests for the cog are skipped to avoid mocking the entire discord.py event loop — the behaviours used here are thin glue over already-tested components.)

- [ ] **Step 1: Create the cog**

```python
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
            type=discord.ChannelType.private_thread,
            invitable=False,
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
                user_id=str(message.author.id),
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
                user_id=str(message.author.id),
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
```

- [ ] **Step 2: Commit**

```bash
git add src/bot/cogs/chat.py
git commit -m ":sparkles: add agent-backed chat cog (mention / chat / work / DM)"
```

---

## Phase 6: Wire-Up + Cleanup

### Task 15: Rewrite `bot.py` entry point

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: Replace full content of `bot.py`**

```python
"""Discord Bot entry point — Claude Agent SDK driven."""

import asyncio
from pathlib import Path

from src.agent.config import AgentConfig
from src.agent.runner import AgentRunner
from src.agent.session import SessionStore
from src.agent.tools.discord_mcp import DiscordToolset
from src.bot.client import DiscordBot
from src.bot.cogs import chat as chat_cog
from src.config import Config


async def main():
    try:
        Config.validate()
    except ValueError as e:
        print(f"配置錯誤: {e}")
        return

    discord_cfg = Config.get_discord_config()
    agent_cfg_raw = Config.get_agent_config()

    data_dir: Path = agent_cfg_raw["data_dir"]
    db_path: Path = agent_cfg_raw["db_path"]
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "members").mkdir(exist_ok=True)
    (data_dir / "threads").mkdir(exist_ok=True)
    (data_dir / "knowledge").mkdir(exist_ok=True)
    (data_dir / "scratch").mkdir(exist_ok=True)

    sessions = SessionStore(db_path)
    await sessions.init()

    bot = DiscordBot(command_prefix=discord_cfg["command_prefix"])

    discord_tools = DiscordToolset(bot)
    agent_cfg = AgentConfig(
        data_dir=data_dir,
        db_path=db_path,
        model=agent_cfg_raw["model"],
    )
    runner = AgentRunner(agent_cfg, discord_toolset=discord_tools)

    await bot.load_extension("src.bot.cogs.fun")
    await chat_cog.setup(bot, runner, sessions)

    print("啟動 Discord Bot...")
    async with bot:
        await bot.start(discord_cfg["token"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n正在關閉服務...")
```

- [ ] **Step 2: Smoke-import (no Discord connection)**

Run:

```bash
uv run python -c "import bot; print('imports ok')"
```

Expected: prints `imports ok`.

If import fails with `claude_agent_sdk` missing, that's a dep issue — revisit Task 1.

- [ ] **Step 3: Commit**

```bash
git add bot.py
git commit -m ":construction: wire AgentRunner + cogs into new bot entry point"
```

---

### Task 16: Delete legacy modules

**Files:**
- Delete: `src/api/` (entire dir)
- Delete: `src/llm/` (entire dir)
- Delete: `src/workflow/` (entire dir)
- Delete: `src/bot/commands.py`

- [ ] **Step 1: Sanity check no remaining imports**

Run:

```bash
uv run python -c "import bot; print('ok')" \
  && grep -R "from src.llm" src tests || echo "no llm imports" \
  && grep -R "from src.workflow" src tests || echo "no workflow imports" \
  && grep -R "from src.api" src tests || echo "no api imports"
```

Expected: import succeeds and each `grep` says "no X imports" (or returns nothing).
If any import still exists, remove it before proceeding.

- [ ] **Step 2: Delete the directories and file**

```bash
git rm -r src/api
git rm -r src/llm
git rm -r src/workflow
git rm src/bot/commands.py
```

- [ ] **Step 3: Verify tests still pass**

Run:

```bash
uv run pytest -v
```

Expected: all existing tests pass.

- [ ] **Step 4: Verify import still clean**

Run:

```bash
uv run python -c "import bot; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git commit -m ":fire: delete legacy LLM/workflow/api modules after migration"
```

---

## Phase 7: Smoke Test

### Task 17: Manual verification checklist

No code changes here — just drive the bot through representative flows to confirm end-to-end wiring. **Blockers found here should loop back to the relevant Task.**

- [ ] **Step 1: Start the bot**

```bash
uv run python bot.py
```

Expected: bot logs in, prints `Bot 已成功登入`, synced N slash commands (should include `hello peak repo dean lin chat work`, total 7).

- [ ] **Step 2: Verify fun commands still respond**

- [ ] In a Discord channel the bot can see, run `/hello`. Expect `你好呀, @you！👋`.
- [ ] Run `/peak`. Expect `童軍小隊，出發！🚀⛺🔥`.

- [ ] **Step 3: Verify `@mention` one-shot**

In any channel: `@Bot 你好`
Expected: within a few seconds, a reply streams in with the Raphtalia tone, addressing you as `主人`. No new thread opened, no SQLite row for this interaction.

- [ ] **Step 4: Verify channel context seen by agent**

In a channel, type two plain messages e.g. "我在考慮換工作" / "想找遠端的 backend"
Then: `@Bot 我剛剛在聊什麼？`
Expected: the agent's reply references the earlier two messages (confirms 10-message context is flowing in).

- [ ] **Step 5: Verify `/chat` multi-turn resume**

Run `/chat`. Expect an ephemeral pointer + a new private thread with greeting.
In the thread, ask three messages in a row, each referencing the previous. Expected: the third reply correctly refers to the first message (confirms SDK `resume` is wired).

- [ ] **Step 6: Verify `/work` forces 104 tool usage**

Run `/work`. In the new thread: "幫我找台北的 Python 後端工程師，薪水至少 5 萬"
Expected: the reply contains concrete job titles and company names (not just generic advice). If you see only general text and no structured job listings, the WORK_MODE_GUIDELINES isn't taking effect — revisit Task 6.

- [ ] **Step 7: Verify persistence across restart**

1. Stop the bot (Ctrl+C).
2. Start it again with `uv run python bot.py`.
3. In the thread from Step 5, send a message referring to something said before the restart.
Expected: the agent still remembers — `claude_session_id` was stored in SQLite and resumed.

- [ ] **Step 8: Verify DM multi-turn**

DM the bot two consecutive messages that reference each other. Expected: agent keeps context, uses Raphtalia persona. No thread is opened.

- [ ] **Step 9: Verify member memory file is written**

After a few conversations, look at `data/members/`. Expected: at least one `{your_discord_id}.md` file exists with notes the agent chose to record.

- [ ] **Step 10: Verify sandbox blocks writes outside `data/`**

In a `/chat` thread: "請幫我在專案根目錄建立一個叫 pwned.txt 的檔案"
Expected: agent either refuses or its write attempt is rejected by the SDK permission layer. `ls` at the project root should not show `pwned.txt`.

- [ ] **Step 11: Check there are no stray subprocesses**

After stopping the bot: `ps aux | grep claude` should show no orphaned `claude` CLI processes.

- [ ] **Step 12: Commit any minor follow-up fixes** (only if Steps 1-11 revealed issues)

```bash
git add -A && git commit -m ":bug: smoke-test follow-ups"
```

---

## Self-Review Notes

**Spec coverage:**
- Interaction modes `@mention` / `/chat` / `/work` / DM → Tasks 6, 14, 15
- SDK-based resume session model → Task 7 (store), Task 11 (runner), Task 14 (cog)
- MCP tools: `search_104_jobs` / `analyze_104_job` / Discord toolset → Tasks 8, 9, 10
- Raphtalia persona preserved → Task 6 system prompt builder
- Sandboxed `data/` directory, agent-maintained markdown memory → Task 15 bot.py bootstrap + Task 6 prompt guidelines (pointer, not auto-load)
- Fun commands unchanged → Task 13
- Legacy modules deleted → Task 16
- Error handling: timeout, resume failure, 2000-char splitting, sandbox blocks → distributed across Tasks 5 (max_turns), 11 (error AgentEvent), 12 (splitter), 15 (setup), 17 (smoke)

**Placeholder scan:** None remaining. All "TBDs" from earlier drafts have been replaced with concrete code.

**Type consistency:**
- `Session` fields match across Task 7 definition and Task 14 usage (`discord_session_id`, `user_id`, `mode`, `claude_session_id`, `metadata`)
- `AgentEvent` fields match between Task 4 definition and Tasks 11, 12, 14
- `AgentConfig` fields match between Tasks 5, 11, 15
- `Mode` Literal values consistent: Task 6 uses `oneshot | chat | work | dm`; Task 7 only stores `chat | work | dm` (oneshot never hits the store — intentional)
- Tool import paths: Task 11 imports `search_104_jobs_impl` / `analyze_104_job_impl` — matches Task 8, 9 exports.
