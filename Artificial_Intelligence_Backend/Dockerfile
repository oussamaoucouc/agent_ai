FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    build-essential \
    libasound2-dev \
    portaudio19-dev \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-cache

# Download Vosk model
RUN mkdir -p /app/model && \
    wget -qO /tmp/vosk-model.zip https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip && \
    unzip /tmp/vosk-model.zip -d /app/model/ && \
    rm /tmp/vosk-model.zip

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uv", "run", "main.py"]
