# ==========================================
# Stage 1: Builder - Install dependencies
# ==========================================
FROM python:3.13-slim AS builder

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv sync (no project install needed for apps)
RUN uv sync --frozen --no-install-project

# ==========================================
# Stage 2: Runtime - Final minimal image
# ==========================================
FROM python:3.13-slim

# Install runtime dependencies for Playwright
RUN apt-get update && apt-get install -y \
    # Playwright browser dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Install uv in runtime image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash botuser

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=botuser:botuser /app/.venv /app/.venv

# Copy dependency files (needed for uv run)
COPY --chown=botuser:botuser pyproject.toml uv.lock ./

# Copy application code
COPY --chown=botuser:botuser bot.py ./
COPY --chown=botuser:botuser src ./src

# Switch to non-root user
USER botuser

# Install Playwright browsers using uv
RUN uv run playwright install chromium

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD uv run python -c "import sys; sys.exit(0)"

# Run the bot using uv
CMD ["uv", "run", "python", "bot.py"]
