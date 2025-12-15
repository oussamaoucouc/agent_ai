FROM python:3.11-slim

WORKDIR /app

# =============================================================================
# OPTIMIZATION: Environment variables for Python performance
# =============================================================================
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc bytecode files
# PYTHONUNBUFFERED: Ensures output is sent straight to logs (important for Docker)
# UV_PROJECT_ENVIRONMENT: Tells uv where to create the virtual environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

# =============================================================================
# Install system dependencies (single layer, cleaned for smaller image)
# =============================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    build-essential \
    libasound2-dev \
    portaudio19-dev \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install uv (no cache for smaller image)
RUN pip install --no-cache-dir uv

# =============================================================================
# OPTIMIZATION: Copy dependency files FIRST for Docker layer caching
# This means if only code changes (not dependencies), Docker reuses this layer
# =============================================================================
COPY pyproject.toml uv.lock ./

# Install dependencies into a persistent virtualenv inside the container
RUN uv sync --frozen --no-cache

# =============================================================================
# OPTIMIZATION: Pre-create directories for Docker volumes
# This ensures correct permissions when Docker mounts volumes later
# =============================================================================
RUN mkdir -p /app/data /app/tts_cache

# Copy application code (this layer changes most frequently)
COPY . .

# Expose port
EXPOSE 8000

# =============================================================================
# CRITICAL: Add the virtual environment to PATH
# This ensures the container uses the venv that uv just created
# =============================================================================
ENV PATH="/app/.venv/bin:$PATH"

# =============================================================================
# PRODUCTION RUNNER: Direct uvicorn command
# 
# Why NOT "uv run main.py":
#   - Creates nested processes (uv -> python -> uvicorn)
#   - Slower signal handling (Docker SIGTERM takes longer)
#   - Uses more RAM (~100-200MB extra)
#
# Why "uvicorn api:app" directly:
#   - Single process, cleaner shutdown
#   - Better Docker signal handling (fast graceful stop)
#   - Less RAM usage
#
# Options explained:
#   --host 0.0.0.0          : Accept connections from outside container
#   --port 8000             : Listen on port 8000
#   --limit-concurrency 100 : Max 100 concurrent connections (prevents OOM)
#   --timeout-keep-alive 30 : Close idle connections after 30 seconds
# =============================================================================
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "200", "--timeout-keep-alive", "30"]
