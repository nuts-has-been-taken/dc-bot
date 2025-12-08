# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Discord bot integrated with 104 job search functionality and LLM capabilities. The bot can search Taiwan's 104.com.tw job listings and provide intelligent responses using LLM function calling.

## Development Commands

### Dependency Management
```bash
# Install/sync all dependencies
uv sync

# Install a new package
uv pip install <package-name>
```

### Running the Bot
```bash
# Start the Discord bot
python bot.py

# Note: Requires DISCORD_TOKEN and LLM_API_KEY in .env
```

## Architecture

### Module Organization

The project uses standard Python module imports (not sys.path manipulation):

```
src/
├── config.py           # Environment config for LLM and Discord
├── bot/               # Discord bot implementation
│   ├── client.py      # DiscordBot class (extends commands.Bot)
│   └── commands.py    # Command Cogs (ping, hello, info)
├── core/              # 104 job search core
│   ├── job104.py      # search_104_jobs() main function
│   └── mappings.py    # All parameter mappings for 104 API
├── llm/               # LLM integration layer
│   ├── client.py      # call_llm(), extract_tool_calls()
│   └── tools.py       # JOB_SEARCH_TOOL definition
└── workflow/          # Example workflows
```

### Key Integration Points

**Discord Bot → LLM → Job Search Flow:**
1. Discord bot receives user command/message
2. LLM processes natural language query with function calling
3. `execute_job_search_tool()` calls `search_104_jobs()`
4. Results formatted and returned to Discord

**Configuration Hierarchy:**
- `Config` class in `config.py` manages both LLM and Discord settings
- Uses `python-dotenv` for environment variables
- Validation happens before bot startup

### 104 Job Search Integration

The `search_104_jobs()` function supports Chinese parameter names that auto-convert to API codes via mapping dictionaries in `mappings.py`. For example:
- Area: "台北市" → area code
- Job type: "軟體工程師" → category code
- Salary, education, experience all have mapping tables

### Discord Bot Extension System

Commands are organized as Cogs using discord.py's extension system:
- Extensions loaded via `bot.load_extension("src.bot.commands")`
- Each Cog must have an async `setup(bot)` function
- Use `@commands.command()` decorator for prefix commands

### LLM Tool Calling

The LLM client supports OpenAI-compatible function calling:
- Tools defined in `src/llm/tools.py` using OpenAI schema format
- `call_llm()` automatically includes tools in the request
- `extract_tool_calls()` parses tool calls from LLM response
- Tool execution happens in application code, not automatically

## Configuration Requirements

Required environment variables in `.env`:
```
LLM_API_KEY=<your-key>
LLM_API_URL=<openai-compatible-endpoint>
LLM_MODEL=<model-name>
DISCORD_TOKEN=<bot-token>
DISCORD_COMMAND_PREFIX=<prefix>  # default: /
```

## Using Context7 for discord.py Documentation

This project has access to the Context7 MCP server for fetching up-to-date library documentation. When working with discord.py features:

### Step 1: Resolve Library ID
```
Use mcp__context7__resolve-library-id with libraryName: "discord.py"
```

This returns multiple discord.py documentation sources. Select based on:
- **Benchmark Score**: Higher is better (look for 70+)
- **Code Snippets**: More snippets = more examples
- **Source Reputation**: Prefer "High"

Recommended library IDs:
- `/websites/discordpy_readthedocs_io_en_stable` - Official Python discord.py docs (best for Python code)
- `/discordjs/guide` - Discord.js guide (useful for Discord concepts, but JavaScript)

### Step 2: Fetch Documentation
```
Use mcp__context7__get-library-docs with:
- context7CompatibleLibraryID: "/websites/discordpy_readthedocs_io_en_stable"
- topic: "your search topic" (e.g., "bot setup", "commands", "events", "cogs")
- mode: "code" (for API references and examples) or "info" (for conceptual guides)
```

### Example Usage
When adding new Discord features like slash commands, events, or voice support:
1. Resolve discord.py library ID
2. Fetch docs with relevant topic (e.g., "slash commands", "voice channels")
3. Use the code examples provided to implement the feature

## Discord Bot Setup

To get the bot running:
1. Create bot at https://discord.com/developers/applications
2. Enable "Message Content Intent" and "Server Members Intent" in Privileged Gateway Intents
3. Copy bot token to `.env` as `DISCORD_TOKEN`
4. Generate invite URL with `bot` and `applications.commands` scopes
5. Run `python bot.py`
