"""
Configuration settings for the AI Teacher Assistant application.
"""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from agno.models.ollama import Ollama

# Ollama configuration
# Use OLLAMA_BASE_URL from environment, with fallback to localhost for local development
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_HOST = OLLAMA_BASE_URL

# Use the model that's actually pulled in docker-compose
#MODEL_ID = "ai_teacher_qwen" # Use the model without thinking capabilities
MODEL_ID = "granite4:tiny-h" # Use the model without thinking capabilities

# Dynamic configuration variables for runtime changes
_current_model_id = MODEL_ID
_current_voice = "af_sky"

# Initialize the model
MODEL = Ollama(id=MODEL_ID, host=OLLAMA_BASE_URL)

def get_current_model():
    """Get the current model instance."""
    return MODEL

def get_current_model_id():
    """Get the current model ID."""
    return _current_model_id

def set_model_id(new_model_id: str):
    """Set a new model ID and update the MODEL instance."""
    global _current_model_id, MODEL
    _current_model_id = new_model_id
    MODEL = Ollama(id=new_model_id, host=OLLAMA_BASE_URL)
    print(f"Model changed to: {new_model_id}")

def get_current_voice():
    """Get the current voice setting."""
    return _current_voice

def set_voice(new_voice: str):
    """Set a new voice for TTS."""
    global _current_voice
    _current_voice = new_voice
    # Update the KOKORO_TTS_CONFIG with the new voice
    KOKORO_TTS_CONFIG["voice"] = new_voice
    print(f"Voice changed to: {new_voice}")



# Export OLLAMA_BASE_URL for use in other modules
__all__ = [
    'MODEL', 'DB_URL', 'DATA_DIR', 'OLLAMA_BASE_URL',
    'VOSK_MODEL_PATH', 'TTS_CACHE_DIR', 'KOKORO_TTS_URL', 'KOKORO_TTS_CONFIG',
    'KOKORO_TTS_HEADERS', 'KOKORO_TTS_TIMEOUT', 'RHUBARB_PATH',
    'MCP_TRANSPORT', 'MCP_SERVER_URL', 'MCP_STDIO_COMMAND', 'MCP_STDIO_ARGS',
    'get_current_model', 'get_current_model_id', 'set_model_id', 
    'get_current_voice', 'set_voice'
]

# Database configuration
# Use DATABASE_URL from environment, default to localhost for non-Docker runs.
# The Dockerfile sets DATABASE_URL to postgresql://ai:ai@postgres:5432/ai
DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://ai:ai@localhost:5532/ai")

# Path configurations
BASE_DIR = Path(__file__).parent.parent

# Determine Rhubarb executable path based on the operating system
if sys.platform == "win32":
    RHUBARB_PATH = BASE_DIR / "rhubarb" / "Rhubarb-Lip-Sync-1.13.0-Windows" / "rhubarb.exe"
else:
    # Path for the Linux executable, nested inside its directory
    RHUBARB_PATH = BASE_DIR / "rhubarb" / "Rhubarb-Lip-Sync-1.13.0-Linux" / "rhubarb"

DATA_DIR = BASE_DIR / "data" / "pdfs"
# Ensure the data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# STT configuration
# Use environment variable for Vosk model path, with fallback
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "../model/vosk-model-en-us-0.22")

# TTS configuration
TTS_CACHE_DIR = BASE_DIR / "tts_cache"
os.makedirs(TTS_CACHE_DIR, exist_ok=True)

# Kokoro TTS configuration
# Use KOKORO_TTS_URL from environment, default to localhost for non-Docker runs.
# The Dockerfile sets KOKORO_TTS_URL to http://kokoro-tts:8880
# The path /v1/audio/speech is appended in tts_helper.py
KOKORO_TTS_URL = os.getenv("KOKORO_TTS_URL", "http://localhost:8880/v1/audio/speech")
KOKORO_TTS_CONFIG = {
    "model": "kokoro",
    "voice": "af_sky",
    "response_format": "wav"
}

# Headers for Kokoro TTS requests
KOKORO_TTS_HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'audio/wav'
}

# Timeout for Kokoro TTS requests (in seconds)
KOKORO_TTS_TIMEOUT = 120

# Debug logging for configuration
print(f"Ollama URL: {OLLAMA_BASE_URL}")
print(f"Model ID: {MODEL_ID}")
print(f"Database URL: {DB_URL}")
print(f"Vosk Model Path: {VOSK_MODEL_PATH}")
print(f"Kokoro TTS URL: {KOKORO_TTS_URL}")

# MCP configuration
# Choose transport: 'streamable-http' (remote HTTP) or 'stdio' (local subprocess)
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "streamable-http").strip()

# Remote MCP server URL (hardcoded per user request).
# NOTE: Embedding API keys in code is insecure; prefer environment variables for production.
MCP_SERVER_URL = "https://server.smithery.ai/@Aas-ee/open-websearch/mcp?api_key=b5bc0f84-3f07-4e49-8821-969da7852f1a&profile=fascinating-dingo-CYbPI1"

# Local stdio MCP server command and args (used when MCP_TRANSPORT='stdio').
MCP_STDIO_COMMAND = os.getenv("MCP_STDIO_COMMAND", "").strip()
_MCP_STDIO_ARGS_RAW = os.getenv("MCP_STDIO_ARGS", "").strip()

def _parse_stdio_args(raw: str):
    try:
        if raw and raw.startswith("["):
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
            return [str(parsed)]
        elif raw:
            return [s for s in raw.split(" ") if s]
        else:
            return []
    except Exception:
        return [s for s in raw.split(" ") if s]

MCP_STDIO_ARGS = _parse_stdio_args(_MCP_STDIO_ARGS_RAW)