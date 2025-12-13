# DC-Bot

A Discord bot integrated with Taiwan's 104 job search platform and LLM capabilities. This bot enables users to search job listings from 104.com.tw directly through Discord using natural language, powered by intelligent LLM function calling.

## Features

- **104 Job Search Integration**: Search Taiwan job market directly from Discord
- **Natural Language Processing**: Use LLM to understand user queries in natural language
- **Function Calling**: Intelligent parameter extraction and job search execution
- **Discord Commands**: Extensible command system using discord.py Cogs
- **Configurable**: Easy configuration through environment variables

## Tech Stack

- **Python**: 3.13+
- **Package Manager**: [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
- **Discord**: discord.py 2.4+
- **LLM**: OpenAI-compatible API support
- **Web Scraping**: BeautifulSoup4, Playwright

## Prerequisites

- Python 3.13 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Discord Bot Token
- OpenAI-compatible LLM API access

## Setup

### 1. Install uv (if not already installed)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Clone and Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd dc-bot

# Install dependencies using uv
uv sync
```

### 3. Configure Environment Variables

Copy `.env_example` to `.env` and fill in your credentials:

```bash
cp .env_example .env
```

Required environment variables:
```env
# LLM Configuration
LLM_API_KEY=your-api-key-here
LLM_API_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4

# Discord Configuration
DISCORD_TOKEN=your-discord-bot-token
DISCORD_COMMAND_PREFIX=/
```

### 4. Discord Bot Setup

1. Create a bot at [Discord Developer Portal](https://discord.com/developers/applications)
2. Enable the following Privileged Gateway Intents:
   - Message Content Intent
   - Server Members Intent
3. Copy the bot token to `.env` as `DISCORD_TOKEN`
4. Generate an invite URL with `bot` and `applications.commands` scopes
5. Invite the bot to your server

## Running the Bot

### Using uv (Recommended)

```bash
uv run python bot.py
```

### Alternative (Direct Python)

```bash
# Activate the virtual environment first
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate     # Windows

python bot.py
```

## Development

### Package Management with uv

```bash
# Install a new package
uv add <package-name>

# Install a dev dependency
uv add --dev <package-name>

# Remove a package
uv remove <package-name>

# Update dependencies
uv sync

# Show installed packages
uv pip list
```

### Project Structure

```
dc-bot/
├── bot.py                 # Main entry point
├── src/
│   ├── config.py          # Configuration management
│   ├── bot/               # Discord bot implementation
│   │   ├── client.py      # DiscordBot class
│   │   └── commands.py    # Command Cogs
│   ├── core/              # 104 job search core
│   │   ├── job104.py      # Job search functions
│   │   └── mappings.py    # 104 API parameter mappings
│   ├── llm/               # LLM integration
│   │   ├── client.py      # LLM client and tool execution
│   │   ├── tools.py       # Function calling tool definitions
│   │   └── prompt/        # LLM prompts
│   └── workflow/          # Application workflows
│       ├── job_search.py  # Job search workflow
│       ├── job_analysis.py # Job analysis workflow
│       └── prompt/        # Workflow prompts
├── pyproject.toml         # Project metadata and dependencies
├── uv.lock                # Locked dependencies
└── .env                   # Environment variables (not in git)
```

## Usage

Once the bot is running and invited to your server:

```
/ping        - Check if bot is responsive
/hello       - Get a greeting
/info        - Show bot information
```

You can also send natural language messages to search for jobs:

```
幫我找台北的軟體工程師工作
搜尋月薪 50000 以上的工作
```

## Docker Support

```bash
# Build the image
docker build -t dc-bot .

# Run the container
docker run -d --env-file .env dc-bot
```

## Contributing

1. Make sure to use `uv` for all dependency management
2. Follow the existing code structure
3. Test your changes before committing
4. Update documentation if needed

## License

[Your License Here]

## Links

- [discord.py Documentation](https://discordpy.readthedocs.io/)
- [uv Documentation](https://github.com/astral-sh/uv)
- [104 Job Search](https://www.104.com.tw/)
