# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install uv (Python package installer and resolver) and utilities for model download
# Also install build-essential for compiling packages, libasound2-dev for ALSA, portaudio19-dev for PortAudio, and ffmpeg
RUN apt-get update && apt-get install -y wget unzip build-essential libasound2-dev portaudio19-dev ffmpeg && \
    pip install uv && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy project dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
# --no-cache can help reduce image size by not storing uv's cache
RUN uv sync --no-cache

# Download and extract Vosk model
# Using vosk-model-en-us-0.22 as an example (approx 50MB zipped)
# The final path will be /app/model/vosk-model-en-us-0.22
RUN mkdir -p /app/model && \
    wget -qO /tmp/vosk-model.zip https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip && \
    unzip /tmp/vosk-model.zip -d /app/model/ && \
    rm /tmp/vosk-model.zip
    # Ensure the unzipped folder name matches VOSK_MODEL_PATH if it's not vosk-model-en-us-0.22

# Copy the rest of the application code into the container
COPY . .

# Copy PDF data into the image
COPY data/pdfs /app/data/pdfs

# Expose the port the app runs on (default 8000)
EXPOSE 8000

# Define environment variables. These can be overridden in docker-compose.yml.
# API_HOST=0.0.0.0 makes the server accessible from outside the container.
ENV API_HOST=0.0.0.0
ENV API_PORT=8000
# API_RELOAD=0 is critical for production.
ENV API_RELOAD=0
# URLs for dependent services will be set in docker-compose.prod.yml
# ENV OLLAMA_BASE_URL=http://ollama:11434 # Set in compose
# ENV KOKORO_TTS_URL=http://kokoro-tts:8880 # Set in compose
# ENV DATABASE_URL=postgresql://ai:ai@postgres:5432/ai # Set in compose
# Default path for Vosk model inside the container.
ENV VOSK_MODEL_PATH=/app/model/vosk-model-en-us-0.22

# Command to run the application using uv
CMD ["uv", "run", "main.py"]
