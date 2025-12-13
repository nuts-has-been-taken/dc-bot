# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL: Package Manager Information

**This project uses `uv` for package management, NOT pip, poetry, or pipenv.**

- Always use `uv` commands for dependency management
- Never use `pip install` directly
- All Python commands should be prefixed with `uv run` when appropriate
- The project has a `uv.lock` file that locks all dependencies

## Project Overview

This is a Discord bot integrated with 104 job search functionality and LLM capabilities. The bot can search Taiwan's 104.com.tw job listings and provide intelligent responses using LLM function calling.

**Key Technologies:**
- Python 3.13+
- discord.py for Discord integration
- OpenAI-compatible LLM API for natural language processing
- BeautifulSoup4 and Playwright for web scraping
- uv for fast, reliable package management

## Development Commands

### Dependency Management (IMPORTANT: Use uv)

```bash
# Install/sync all dependencies
uv sync

# Add a new package
uv add <package-name>

# Add a development dependency
uv add --dev <package-name>

# Remove a package
uv remove <package-name>

# Update dependencies
uv sync --upgrade

# List installed packages
uv pip list

# NEVER USE: pip install (wrong)
# ALWAYS USE: uv add (correct)
```

### Running the Bot

```bash
# Recommended: Run with uv
uv run python bot.py

# Alternative: Activate venv first
source .venv/bin/activate  # macOS/Linux
python bot.py

# Note: Requires DISCORD_TOKEN and LLM_API_KEY in .env
```

### Other Development Commands

```bash
# Run Python scripts
uv run python -m src.workflow.job_search

# Run with specific Python version
uv run --python 3.13 python bot.py

# Execute one-off commands
uv run <command>
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
│   ├── tools.py       # JOB_SEARCH_TOOL definition
│   └── prompt/        # LLM prompt templates
│       └── raphtalia.py
└── workflow/          # Application workflows
    ├── job_search.py  # Job search workflow
    ├── job_analysis.py # Job analysis workflow
    └── prompt/        # Workflow-specific prompts
        ├── job_detail_analysis.py
        ├── job_search_extract_params.py
        └── job_search_final_response.py
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

The bot supports natural language queries like:
- "幫我找台北的軟體工程師工作"
- "搜尋月薪 50000 以上的工作"

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

**Workflow System:**
- `workflow/job_search.py` - Handles job search queries
- `workflow/job_analysis.py` - Analyzes job details
- Prompts are modularized in `workflow/prompt/`

## Configuration Requirements

Required environment variables in `.env`:
```
LLM_API_KEY=<your-key>
LLM_API_URL=<openai-compatible-endpoint>
LLM_MODEL=<model-name>
DISCORD_TOKEN=<bot-token>
DISCORD_COMMAND_PREFIX=<prefix>  # default: /
```

Copy `.env_example` to `.env` and fill in your credentials.

## Package Management Best Practices

### When Adding Dependencies

1. **Never use pip directly**
   ```bash
   # WRONG
   pip install requests

   # CORRECT
   uv add requests
   ```

2. **Let uv manage the virtual environment**
   - uv automatically creates and manages `.venv/`
   - No need to manually create virtual environments

3. **Always sync after pulling changes**
   ```bash
   git pull
   uv sync  # Install any new dependencies
   ```

4. **Check for dependency conflicts**
   ```bash
   uv pip check
   ```

### uv.lock File

- The `uv.lock` file contains exact versions of all dependencies
- Should be committed to git
- Ensures reproducible builds across environments
- Automatically updated when you use `uv add` or `uv remove`

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
5. Run `uv sync` to install dependencies
6. Run `uv run python bot.py`

## Common Development Tasks

### Adding a New Command

1. Edit `src/bot/commands.py`
2. Add a new method with `@commands.command()` decorator
3. No need to restart if using hot reload (not currently implemented)
4. Test in Discord

### Adding a New Workflow

1. Create new file in `src/workflow/`
2. Add corresponding prompts in `src/workflow/prompt/`
3. Update LLM tools if needed in `src/llm/tools.py`
4. Test the workflow

### Debugging

```bash
# Run with debug logging
uv run python bot.py

# Check Discord bot logs in console
# Check LLM API responses in console
```

### Docker Deployment

The project includes a Dockerfile for containerized deployment:

```bash
# Build image
docker build -t dc-bot .

# Run container
docker run -d --env-file .env dc-bot
```

## Important Notes

1. **Always use `uv` for dependency management** - This cannot be stressed enough
2. **Python 3.13+** - Required for this project
3. **Virtual Environment** - Automatically managed by uv in `.venv/`
4. **Environment Variables** - Must be configured before running
5. **Discord Intents** - Required intents must be enabled in Discord Developer Portal
6. **Chinese Language Support** - Bot supports Traditional Chinese queries and responses

## Troubleshooting

### Bot won't start
- Check `.env` file exists and has required variables
- Verify Discord token is valid
- Ensure virtual environment is activated or using `uv run`

### Dependencies not found
```bash
# Reinstall dependencies
uv sync --reinstall
```

### Module import errors
- Ensure you're running from project root
- Use `uv run python bot.py` not just `python bot.py`

### LLM not responding
- Verify LLM_API_KEY and LLM_API_URL in `.env`
- Check API endpoint is accessible
- Review console logs for API errors
