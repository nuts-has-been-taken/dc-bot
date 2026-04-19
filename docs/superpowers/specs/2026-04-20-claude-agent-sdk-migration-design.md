# Claude Agent SDK 遷移設計

**狀態：** Draft (待 user review)
**日期：** 2026-04-20
**作者：** carbarcha (brainstormed with Claude)
**目標讀者：** 後續接手實作的工程師 / writing-plans skill

---

## 1. 背景與目標

現有 `dc-bot` 是以「寫死的 2-step LLM call」驅動的 Discord 機器人：使用者輸入 → LLM 解析參數 → 執行 104 爬蟲 → LLM 生成回覆。這種架構擴充性低、不支援多輪對話、工具呼叫靠手動編排、無法使用 skill。

本次升級把 driver 整個換成 **Anthropic Claude Agent SDK**（Python 套件 `claude-agent-sdk`），讓機器人轉為 agent-centric：使用者透過 Discord 與 Claude agent 對話，agent 自主決定何時呼叫工具、讀寫記憶檔、查 104 職缺等。

### 設計目標

1. **對話為主**：主要互動方式為多輪對話而非 one-shot 指令
2. **工具可擴充**：新功能以 MCP tool / skill 形式加入，不需改 driver
3. **Session 可持久**：對話跨 bot 重啟仍能延續
4. **Agent 自主管理記憶**：透過 markdown 檔案累積使用者 profile 與 thread 摘要
5. **沙箱安全**：Agent 的 Read/Write/Edit 僅限 `data/`，不可觸碰程式碼
6. **LLM 供應商交給機器**：繼承主機上的 `claude` CLI 認證，不在 bot 中管 API key

### 非目標（暫不處理）

- 多使用者同時寫入同一 knowledge 檔的 lock 機制（使用者是少量好友，併發率低）
- Bash tool（安全考量，禁用）
- FastAPI 通知 server（功能已遷移到另一 bot，直接砍）
- Fine-grained rate limit / token budget（先跑，後續觀察再加）

---

## 2. 互動模式

三種觸發方式並存：

| 模式 | 觸發 | 多輪 | Session 持久 | Context 來源 |
|---|---|---|---|---|
| `@mention` | 在任何頻道 @bot | 否（單次） | 否 | 頻道最近 10 則訊息 |
| `/chat` | Slash command | 是 | 是（跨重啟） | SDK resume 續上 thread 歷史 |
| `/work` | Slash command | 是 | 是 | 同上，system prompt 強化 104 工具使用 |
| DM | 私訊 bot | 是 | 是 | 同上 |

### 保留的舊功能

- **人格**：`RAPHTALIA_PROMPT`（拉芙塔莉雅）塞進 system prompt
- **彩蛋指令**：`/peak`、`/repo`、`/dean`、`/lin`、`/hello` 完全不變、不經過 agent

### 移除的舊功能

- `/找工作`、`/分析工作` → 功能由 agent 在 `/work` thread 中透過 MCP tool 完成
- `src/api/`（FastAPI 通知 server）整個刪除
- `src/llm/`、`src/workflow/` 整個刪除

---

## 3. 整體架構

```
┌────────────────────────────────────────────────────────────────┐
│                        bot.py (entry)                          │
│              discord.py Client + Cogs 載入                     │
└───────────────────────┬────────────────────────────────────────┘
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
   ┌──────────────────┐   ┌──────────────────────────┐
   │ src/bot/cogs/    │   │ src/agent/               │
   │  - fun.py        │   │  - runner.py  ← 核心     │
   │    (peak/dean/   │   │  - session.py ← 狀態     │
   │     lin/repo/    │   │  - prompt.py  ← system   │
   │     hello)       │   │  - config.py             │
   │  - chat.py       │   │  - tools/                │
   │    (@mention,    │   │    ├─ job_search_mcp.py  │
   │     /chat,       │   │    ├─ job_analysis_mcp.py│
   │     DM,          │   │    ├─ discord_mcp.py     │
   │     /work)       │   │    └─ __init__.py        │
   └────────┬─────────┘   │  - skills/               │
            │             │    └─ (預留，目前未使用) │
            │             └──────────┬───────────────┘
            │                        │
            └─── AgentRunner ────────┘
                        │
                        ▼
            ┌────────────────────────┐
            │ claude_agent_sdk       │
            │ .query(...,            │
            │   resume=session_id)   │
            └────────────────────────┘

src/core/        (保留，被 MCP tool 包裝)
├── job104.py    (104 爬蟲)
└── mappings.py  (地區/職類/學歷代碼)

data/                           (git-ignored，agent 沙箱)
├── members/{user_id}.md        (使用者 profile)
├── threads/{thread_id}.md      (thread 長期備註)
├── knowledge/*.md              (通用知識)
└── scratch/{session_id}/       (單次暫存)

src/db/sessions.sqlite          (session 索引)
```

### 架構原則

1. `src/bot/` 只負責 Discord 事件接收與分流，不直接呼 LLM
2. `src/agent/` 封裝所有 Agent 邏輯，Discord 層只透過 `AgentRunner.run(...)` 介面呼叫
3. 舊的 `src/llm/`、`src/workflow/`、`src/api/` 整個刪除
4. 保留 `src/core/`（104 爬蟲），被 `src/agent/tools/job_search_mcp.py` 包成 MCP tool
5. Persona 走 system prompt 而非 skill（簡單、省 token）
6. **不維護長連線 `ClaudeSDKClient`**；每次訊息都是獨立 `query()`，透過 `resume` 續接

---

## 4. 核心元件

### 4.1 `src/agent/runner.py` — AgentRunner

對外唯一介面：Discord 層只呼一個方法。

```python
class AgentRunner:
    def __init__(self, config: AgentConfig): ...

    async def run(
        self,
        user_input: str,
        mode: Literal["oneshot", "chat", "work", "dm"],
        user_id: str,
        *,
        resume: str | None = None,                  # SDK 回的 claude_session_id
        channel_context: list[ChannelMsg] | None = None,  # 僅 oneshot 模式使用
        thread_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """
        每次都是獨立 query。有 resume 就延續、沒有就新開。
        yield AgentEvent（含 text chunk、tool call log、最終 session_id）
        Caller 需在 stream 結束後從最後一個 event 取 session_id 存回 SQLite。
        """
```

**`channel_context` 注入方式**：oneshot 模式下，runner 把 list 格式化成一段 context preamble，
接在真正的 user input 前面一起送進 `query()`，例：

```
[Channel recent messages (oldest → newest)]
alice: 有人推薦 Python web framework 嗎？
bob: 我推 FastAPI
alice: 為什麼不是 Django？

[User's current message]
@bot 我剛剛提到的那個東西是什麼意思
```

這樣 agent 能看到背景、但訊息主體仍是使用者當下那句。`ChannelMsg` 是簡單 dataclass
（`author: str, content: str, created_at: datetime`）。

**AgentEvent** 是 dataclass 封裝，最少包含：
- `type: Literal["text", "tool_start", "tool_result", "done"]`
- `text: str | None`（type=="text" 時使用）
- `session_id: str | None`（type=="done" 時必有）

### 4.2 `src/agent/session.py` — SessionStore

SQLite-based session 索引。對話內容由 agent 自己寫 `data/threads/{id}.md`；SQLite 只存索引與 `claude_session_id` 以便 resume。

```
Table sessions:
  discord_session_id TEXT PRIMARY KEY    -- "thread:123" | "dm:user_456"
  claude_session_id  TEXT                -- SDK 回傳的 id（resume 用）
  user_id            TEXT
  mode               TEXT                -- "chat" | "work" | "dm"
  created_at         TIMESTAMP
  last_active_at     TIMESTAMP
  metadata_json      TEXT                -- {thread_name, channel_id, ...}
```

公開介面：

```python
class SessionStore:
    async def get(self, discord_session_id: str) -> Session | None
    async def create(self, *, discord_session_id, user_id, mode, metadata) -> Session
    async def update_claude_session(self, discord_session_id, claude_session_id)
    async def touch(self, discord_session_id)  # 更新 last_active_at
    async def delete(self, discord_session_id)
```

`@mention` 不觸發 SessionStore，因為它不持久。

### 4.3 `src/agent/tools/` — 自訂 MCP tools

以 `claude_agent_sdk` 的 MCP server decorator 註冊。**每個 tool 一個檔，避免單檔爆炸。**

| 檔 | Tool | 說明 |
|---|---|---|
| `job_search_mcp.py` | `search_104_jobs(keyword, area, salary_range, education, sort_by, posted_within_days)` | 薄包裝 `src/core/job104.py`，自動處理中文 → 代碼轉換（複用 `src/core/mappings.py`） |
| `job_analysis_mcp.py` | `analyze_104_job(url_or_query)` | 搬舊 `src/workflow/job_analysis.py` 的 Playwright + 結構化提取邏輯 |
| `discord_mcp.py` | `fetch_channel_history(channel_id, limit=50)`<br>`send_embed(channel_id, title, fields, color)`<br>`react_to_message(channel_id, message_id, emoji)`<br>`get_member_info(user_id)` | Discord 原生能力包成 tool 供 agent 使用 |

Memory 操作不另外包 tool，agent 直接用內建 Read/Write/Edit 打 `data/` 即可。

### 4.4 `src/agent/prompt.py` — 系統提示管理

```python
def build_system_prompt(
    mode: Literal["oneshot", "chat", "work", "dm"],
    user_id: str,
    thread_id: str | None = None,
) -> str:
    sections = [RAPHTALIA_PROMPT]

    if mode == "work":
        sections.append(WORK_MODE_GUIDELINES)   # 強制使用 104 tools
    elif mode == "chat":
        sections.append(CHAT_MODE_GUIDELINES)
    elif mode == "dm":
        sections.append(DM_MODE_GUIDELINES)
    elif mode == "oneshot":
        sections.append(ONESHOT_GUIDELINES)     # 不寫檔、不開 thread

    sections.append(MEMBER_MEMORY_GUIDELINE.format(user_id=user_id))

    if thread_id:
        sections.append(THREAD_MEMORY_GUIDELINE.format(thread_id=thread_id))

    sections.append(DISCORD_FORMAT_GUIDELINE)

    return "\n\n---\n\n".join(sections)
```

**關鍵 prompt 片段：**

```python
MEMBER_MEMORY_GUIDELINE = """
這位使用者的 Discord ID 是 {user_id}。
若有需要了解他的背景、偏好、過去互動，請讀 data/members/{user_id}.md。

判斷原則：
- 第一次遇到這位使用者 → 檔案可能不存在，不用特地去讀
- 對話中需要個人化建議、或不確定對方狀況時 → 主動讀
- 學到新的個人資訊（工作領域、偏好、狀態）→ 寫入或更新檔案
- 不要為了例行問候去讀，浪費 token
"""

THREAD_MEMORY_GUIDELINE = """
這個 thread 的長期備註在 data/threads/{thread_id}.md。
- 對話起步不必讀（最近訊息已在 SDK resume context 裡）
- thread 很長或主題切換時，在重點段落結束後寫摘要進去
- resume 回到很久以前的 thread，先讀一次備註當快速定位點
"""

WORK_MODE_GUIDELINES = """
這個 thread 是主人用來找工作 / 分析職缺的專屬空間。

**工具使用原則：**
1. 搜尋台灣職缺 → **必須**用 `search_104_jobs` MCP tool，不要只靠 WebSearch
2. 分析特定 104 職缺（含 URL 或公司+職位）→ **必須**用 `analyze_104_job`
3. WebSearch 只在：查公司新聞、Glassdoor/PTT 評價、產業趨勢時使用
4. 找到結果後主動提問釐清偏好（地點、薪資、產業）

**目標**：給具體、可用的職缺清單與分析，不要空泛建議。
"""

DISCORD_FORMAT_GUIDELINE = """
你的回應會送到 Discord，請遵守：
- 單則訊息上限 2000 字元；超過時分段，在段落邊界切開
- 可使用 markdown：**粗體**、*斜體*、`code`、```code block```、> 引用、- 列表
- 適度使用 emoji 增添情感（符合拉芙塔莉雅的溫柔氣質）
- 結構化資料優先用 send_embed tool 而非純文字
- 呼叫 tool 時不要中斷敘述太久，必要時說一句「我查一下喔～」
"""
```

### 4.5 `src/agent/config.py` — AgentConfig

```python
@dataclass(frozen=True)
class AgentConfig:
    data_dir: Path                    # "data/"
    db_path: Path                     # "src/db/sessions.sqlite"
    model: str = "claude-sonnet-4-6"  # 可被 env ANTHROPIC_MODEL 覆寫
    max_turns: int = 20               # 單次 query 最大 tool-use 輪數
    timeout_seconds: int = 60

ALLOWED_TOOLS = [
    "Read", "Write", "Edit", "Glob", "Grep",
    "WebSearch", "WebFetch",
    # Bash 禁用
    # 自訂 MCP tools 由 SDK 自動加入
]

# SDK permissions 白名單
ALLOWED_PATHS = ["data/"]
DISALLOWED_PATHS = ["src/", "bot.py", ".env", "pyproject.toml", "uv.lock"]
```

### 4.6 `src/bot/cogs/chat.py` — Discord 事件分流

```python
class ChatCog(commands.Cog):
    def __init__(self, bot, runner: AgentRunner, session_store: SessionStore):
        self.bot = bot
        self.runner = runner
        self.sessions = session_store

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        # DM
        if isinstance(message.channel, discord.DMChannel):
            await self._handle_stateful(message, mode="dm",
                                        discord_session_id=f"dm:{message.author.id}")
            return

        # Thread: bot 開的
        if isinstance(message.channel, discord.Thread):
            session = await self.sessions.get(f"thread:{message.channel.id}")
            if session:
                await self._handle_stateful(message, mode=session.mode,
                                            discord_session_id=session.discord_session_id)
                return
            # 非 bot thread，忽略

        # @mention: 一次性
        if self.bot.user in message.mentions:
            await self._handle_oneshot(message)
            return

    async def _handle_oneshot(self, message):
        history = [m async for m in message.channel.history(limit=10)]
        async with message.channel.typing():
            streamer = DiscordStreamer(message.channel, reply_to=message)
            async for event in self.runner.run(
                user_input=message.content,
                mode="oneshot",
                user_id=str(message.author.id),
                channel_context=history,
            ):
                await streamer.handle(event)
            await streamer.finalize()

    async def _handle_stateful(self, message, *, mode, discord_session_id):
        session = await self.sessions.get(discord_session_id)
        if not session:
            session = await self.sessions.create(
                discord_session_id=discord_session_id,
                user_id=str(message.author.id),
                mode=mode,
                metadata={"channel_id": message.channel.id},
            )
        async with message.channel.typing():
            streamer = DiscordStreamer(message.channel)
            final_session_id = None
            async for event in self.runner.run(
                user_input=message.content,
                mode=mode,
                user_id=str(message.author.id),
                resume=session.claude_session_id,
                thread_id=str(message.channel.id) if isinstance(message.channel, discord.Thread) else None,
            ):
                await streamer.handle(event)
                if event.type == "done":
                    final_session_id = event.session_id
            await streamer.finalize()
            if final_session_id and final_session_id != session.claude_session_id:
                await self.sessions.update_claude_session(
                    discord_session_id, final_session_id,
                )
        await self.sessions.touch(discord_session_id)

    @app_commands.command(name="chat", description="開一個私人 thread 與 bot 對話")
    async def chat_cmd(self, interaction):
        thread = await interaction.channel.create_thread(
            name=f"Chat with {interaction.user.display_name}",
            type=discord.ChannelType.private_thread,
        )
        await self.sessions.create(
            discord_session_id=f"thread:{thread.id}",
            user_id=str(interaction.user.id),
            mode="chat",
            metadata={"thread_name": thread.name, "channel_id": interaction.channel.id},
        )
        await interaction.response.send_message(f"在 {thread.mention} 等你～", ephemeral=True)
        await thread.send(f"{interaction.user.mention} 主人～我們開始聊吧 💕")

    @app_commands.command(name="work", description="開一個 thread 討論工作相關")
    async def work_cmd(self, interaction):
        thread = await interaction.channel.create_thread(
            name=f"找工作 - {interaction.user.display_name}",
            type=discord.ChannelType.private_thread,
        )
        await self.sessions.create(
            discord_session_id=f"thread:{thread.id}",
            user_id=str(interaction.user.id),
            mode="work",
            metadata={"thread_name": thread.name, "channel_id": interaction.channel.id},
        )
        await interaction.response.send_message(f"{thread.mention} 我們去找工作～", ephemeral=True)
        await thread.send(f"{interaction.user.mention} 主人想找什麼樣的工作呢？告訴我地點、職類、薪資期待就好～")
```

### 4.7 `src/bot/streamer.py` — DiscordStreamer

負責把 agent streaming 的 text chunk 以「每 ~1 秒編輯一次 Discord 訊息」的節奏送出；超過 2000 字元時在段落邊界切分、送後續訊息。

```python
class DiscordStreamer:
    FLUSH_INTERVAL = 1.0
    MAX_LEN = 2000

    def __init__(self, channel, reply_to: discord.Message | None = None): ...
    async def handle(self, event: AgentEvent): ...
    async def finalize(self): ...
```

---

## 5. 資料流

### 5.1 `@mention` 單次對話

```
User: "@bot 我剛剛提到的那個東西是什麼意思"
  ↓
on_message → 偵測 mention
  ↓
fetch 頻道近 10 則訊息
  ↓
AgentRunner.run(user_input, mode="oneshot", channel_context=history)
  ↓
SDK query() → Claude subprocess
  ↓ streaming chunks
DiscordStreamer 每 1s 編輯同一則 reply 訊息
  ↓ (完成)
[若 agent 自行決定讀 / 寫 members/{id}.md，已透過 Read/Write 完成]
```

### 5.2 `/work` 多輪對話

```
User: /work
  ↓
create_thread → SessionStore.create("thread:{id}", mode="work")
  ↓ (之後每則訊息)
User: "幫我找台北後端工程師，薪水5萬以上"
  ↓
on_message → 認出是 bot thread → 取 session（mode=work）
  ↓
AgentRunner.run(input, mode="work", resume=claude_session_id)
  ↓
SDK 組 prompt（含 WORK_MODE_GUIDELINES 強制用 104 工具）
  ↓
Agent 呼叫 search_104_jobs MCP tool
  ↓ streaming
DiscordStreamer 分段送
  ↓ (完成)
SessionStore.update_claude_session(new_session_id)
Agent 可能自行更新 data/threads/{id}.md 做摘要
```

### 5.3 Bot 重啟後續接

```
Bot 重啟 → SQLite 仍在
  ↓
User 在舊 thread 發言
  ↓
on_message → SessionStore.get("thread:{id}") 拿到 claude_session_id
  ↓
AgentRunner.run(..., resume=claude_session_id)
  ↓
SDK 後端自動恢復對話歷史
```

---

## 6. 錯誤處理

| 情況 | 處理 |
|---|---|
| `claude` CLI 未登入 / auth 失敗 | 啟動時 healthcheck；錯誤時回 Discord「主人，我還沒準備好呢…」並 log |
| SDK subprocess timeout (>60s) | AbortController 中止，回用戶「思考太久了，可以再說一次嗎？」 |
| MCP tool 例外（104 網站掛掉、Playwright 崩潰） | Tool 回 `{error: "..."}`，Agent 自行判斷要不要重試或換方式 |
| Discord 分段送訊息其中一段失敗 | `try/except` 包一段，跳過失敗段落繼續後面 |
| `resume` session 失效（SDK 端過期） | 偵測後清掉 SQLite 的 `claude_session_id`，改新開並通知「之前的記憶可能不在了」 |
| 使用者 input 觸發 agent 亂寫檔 | SDK `permissions` 白名單只開 `data/`；agent 想動 `src/` 會被拒 |
| 2000 字元超限 | `DiscordStreamer` 在段落邊界切；code block 特殊處理不切中間 |
| Agent 無限循環呼叫 tool | `AgentConfig.max_turns=20` 硬上限 |

---

## 7. 設定檔變更

### `.env`

**移除：**
- `LLM_API_KEY`
- `LLM_API_URL`
- `LLM_MODEL`
- `API_HOST`, `API_PORT`, `DISCORD_BOT_API_KEY`, `DISCORD_DEFAULT_CHANNEL_ID`

**新增 / 保留：**
- `DISCORD_TOKEN`（保留）
- `DISCORD_COMMAND_PREFIX`（保留）
- `ANTHROPIC_MODEL`（選填，預設 `claude-sonnet-4-6`）
- `DATA_DIR`（選填，預設 `./data`）
- `DB_PATH`（選填，預設 `./src/db/sessions.sqlite`）

### `.gitignore`

新增：
```
data/
src/db/*.sqlite
```

### `pyproject.toml`

**新增：** `claude-agent-sdk`, `aiosqlite`
**移除：** `openai`, `fastapi`, `uvicorn`, `requests`（若無他用）
**保留：** `discord.py`, `beautifulsoup4`, `playwright`, `python-dotenv`

---

## 8. 測試策略

1. **單元測試**（pytest）
   - `src/agent/session.py` SQLite CRUD
   - `src/agent/tools/*` 個別 tool 功能（`search_104_jobs` 代碼轉換、`analyze_104_job` 用 mock Playwright）
   - `src/agent/prompt.py` 各 mode 的 prompt 組裝
   - `src/bot/streamer.py` 分段邏輯（2000 字元、code block 邊界）

2. **整合測試**（pytest + 假 SDK）
   - Mock `claude_agent_sdk.query` 回傳預定 event 序列
   - 驗證 Discord cog 正確處理 streaming、分段、error
   - 驗證 SessionStore 正確存 / 取 claude_session_id

3. **手動 smoke test**（驗證 checklist）
   - [ ] `@bot 你好` → 回拉芙塔莉雅口吻
   - [ ] `/chat` → 開 thread，連續問 3 題，第 3 題能指涉第 1 題內容（resume 生效）
   - [ ] `/work` → 問「台北 Python 後端」，確認 agent 呼叫 `search_104_jobs` 而非僅 WebSearch
   - [ ] Bot 重啟 → 回到舊 thread 再問，對話延續
   - [ ] DM → 多輪對話，不受 thread 干擾
   - [ ] 彩蛋指令 `/peak`、`/dean` 仍正常回應
   - [ ] Agent 嘗試寫 `src/` 下檔案 → 被 permissions 拒絕

---

## 9. 遷移步驟

（細節讓 writing-plans 展開，此處列高層次順序）

1. **清理舊模組**
   - 刪 `src/api/`、`src/llm/`、`src/workflow/`
   - 從 `bot.py` 移除 FastAPI 啟動邏輯
   - 從 `src/bot/commands.py` 移除 `/找工作`、`/分析工作`
2. **新增相依**
   - `uv add claude-agent-sdk aiosqlite`
   - `uv remove openai fastapi uvicorn`
3. **建立骨架**
   - `src/agent/` 新資料夾：`runner.py`、`session.py`、`prompt.py`、`config.py`、`tools/`
   - `src/bot/cogs/`：將 `commands.py` 拆為 `fun.py`（彩蛋）、`chat.py`（agent 對話）
   - `src/bot/streamer.py`
   - `.gitignore` 加 `data/`、`src/db/*.sqlite`
4. **實作 MCP tools**
   - `job_search_mcp.py`（搬 `src/llm/tools.py` 的轉碼邏輯 + 複用 `src/core/`）
   - `job_analysis_mcp.py`（搬 `src/workflow/job_analysis.py` 的 Playwright 與結構化提取）
   - `discord_mcp.py`
5. **實作 Runner + SessionStore + Prompt + Streamer**
6. **改 `bot.py`**：載入 cogs、初始化 `AgentRunner` 與 `SessionStore`、注入到 Cog
7. **更新 `src/config.py`**：移除 LLM 相關、新增 `ANTHROPIC_MODEL` 等
8. **pytest 測試**
9. **手動 smoke test**

---

## 10. 開放項目 / 未來擴充

- **Skills 目錄** (`src/agent/skills/`) 目前預留空，未來若 prompt 過長可將 mode 的 guidelines 拆成 skill
- **Idle 清理**：SQLite 上的 session 目前不清理；未來可加「超過 90 天無活動的 session 標記封存」
- **Member profile 結構**：目前完全交給 agent 自由書寫；若未來需要穩定 schema（給其他系統讀）可加結構化 guideline
- **多使用者共享 knowledge**：目前 `data/knowledge/` 預留，需要時再定設計
- **串流 event 的 tool-use 視覺化**：可選擇性把 `tool_start` event 轉為 Discord typing indicator 或暫時 embed
