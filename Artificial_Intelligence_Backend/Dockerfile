# =============================================================================
# CUDA-ENABLED BASE IMAGE for GPU acceleration (Docling, PyTorch)
# Using CUDA 12.4 + cuDNN 9 for best compatibility with modern GPUs
# =============================================================================
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

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
# CUDA environment variables
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# =============================================================================
# Install Python 3.11 and system dependencies (single layer, cleaned for smaller image)
# DEBIAN_FRONTEND=noninteractive prevents interactive prompts (like timezone)
# =============================================================================
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    tzdata \
    && ln -fs /usr/share/zoneinfo/UTC /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    wget \
    unzip \
    build-essential \
    libasound2-dev \
    portaudio19-dev \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# Install pip for Python 3.11
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

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
# CRITICAL: Install PyTorch with CUDA support AFTER uv sync
# This ensures we get the GPU-accelerated version
# Using 'uv pip' since uv-managed venvs may not have pip in standard location
# =============================================================================
RUN uv pip install --no-cache \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# =============================================================================
# OPTIMIZATION: Pre-create directories for Docker volumes
# This ensures correct permissions when Docker mounts volumes later
# =============================================================================
RUN mkdir -p /app/data /app/tts_cache

# Copy application code (this layer changes most frequently)
COPY . .

# =============================================================================
# CRITICAL: Add the virtual environment to PATH early
# This ensures subsequent RUN commands use the venv
# =============================================================================
ENV PATH="/app/.venv/bin:$PATH"

# =============================================================================
# SETUP: Runtime Download
# Models will be downloaded at runtime if using volumes (keeps image light)
# =============================================================================
# RUN uv run python setup_tts.py

# Expose port
EXPOSE 8000

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
CMD ["uv", "run", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "200", "--timeout-keep-alive", "30"]
