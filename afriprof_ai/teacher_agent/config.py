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
from agno.models.openai import OpenAIChat
from urllib.parse import urlparse

# Ollama configuration
# Use OLLAMA_BASE_URL from environment, with fallback to localhost for local development
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:12434")
OLLAMA_HOST = OLLAMA_BASE_URL

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

def get_openai_base_url() -> str:
    try:
        p = urlparse(OLLAMA_BASE_URL)
        base = f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else OLLAMA_BASE_URL
        path = (p.path or "").strip()
        if path.startswith("/engines/"):
            parts = [seg for seg in path.split('/') if seg]
            if len(parts) >= 3 and parts[0] == 'engines' and parts[2] == 'v1':
                return base + f"/engines/{parts[1]}/v1/"
            if 'v1' in parts:
                v1_index = parts.index('v1')
                return base + '/' + '/'.join(parts[:v1_index+1]) + '/'
            return base + '/engines/llama.cpp/v1/'
        if path.startswith('/v1'):
            return base + '/v1/'
        return base + '/engines/llama.cpp/v1/'
    except Exception:
        return OLLAMA_BASE_URL

# Use the model that's actually pulled in docker-compose
#MODEL_ID = "ai_teacher_qwen" # Use the model without thinking capabilities
MODEL_ID = "ai/granite-4.0-h-tiny:7B" # Use the model without thinking capabilities

# Dynamic configuration variables for runtime changes
_current_model_id = MODEL_ID
_current_voice = "af_sky"

# MCP runtime-configurable settings
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "streamable-http").strip()
MCP_SERVER_URL = "https://server.smithery.ai/@Aas-ee/open-websearch/mcp?api_key=b5bc0f84-3f07-4e49-8821-969da7852f1a&profile=fascinating-dingo-CYbPI1"
MCP_STDIO_COMMAND = os.getenv("MCP_STDIO_COMMAND", "").strip()
_MCP_STDIO_ARGS_RAW = os.getenv("MCP_STDIO_ARGS", "").strip()

# Initialize the model
MODEL = OpenAIChat(id=MODEL_ID, base_url=get_openai_base_url(), api_key=OPENAI_API_KEY or "anything")

def get_current_model():
    """Get the current model instance."""
    return MODEL

def get_current_model_id():
    """Get the current model ID."""
    return _current_model_id

def get_default_model_id() -> str:
    """Return the default model id, preferring the first available model if present."""
    try:
        if isinstance(_available_models, list) and len(_available_models) > 0 and str(_available_models[0]).strip():
            return str(_available_models[0]).strip()
    except Exception:
        pass
    return _current_model_id

def set_model_id(new_model_id: str):
    """Set a new model ID and update the MODEL instance."""
    global _current_model_id, MODEL
    _current_model_id = new_model_id
    MODEL = OpenAIChat(id=new_model_id, base_url=get_openai_base_url(), api_key=OPENAI_API_KEY or "anything")
    print(f"Model changed to: {new_model_id}")

def get_current_voice():
    """Get the current voice setting."""
    return _current_voice

def get_default_voice() -> str:
    try:
        if isinstance(_available_voices, list) and len(_available_voices) > 0 and str(_available_voices[0]).strip():
            return str(_available_voices[0]).strip()
    except Exception:
        pass
    return _current_voice

def set_voice(new_voice: str):
    """Set a new voice for TTS."""
    global _current_voice
    _current_voice = new_voice
    # Update the KOKORO_TTS_CONFIG with the new voice
    try:
        if 'KOKORO_TTS_CONFIG' in globals() and isinstance(KOKORO_TTS_CONFIG, dict):
            KOKORO_TTS_CONFIG["voice"] = new_voice
    except Exception:
        pass
    print(f"Voice changed to: {new_voice}")

# --- Runtime config persistence ---
from typing import Any, Dict, List

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "pdfs"
# Ensure the data directory exists
os.makedirs(DATA_DIR, exist_ok=True)
DOCS_BASE_DIR = BASE_DIR / "data"
USER_PDFS_ROOT = DOCS_BASE_DIR / "pdfs"
USER_DOCX_ROOT = DOCS_BASE_DIR / "docs"
USER_TEXT_ROOT = DOCS_BASE_DIR / "texts"
USER_CSV_ROOT = DOCS_BASE_DIR / "csv"
os.makedirs(USER_PDFS_ROOT, exist_ok=True)
os.makedirs(USER_DOCX_ROOT, exist_ok=True)
os.makedirs(USER_TEXT_ROOT, exist_ok=True)
os.makedirs(USER_CSV_ROOT, exist_ok=True)

# Persist non-secret runtime config in dedicated config directory
CONFIG_DIR = BASE_DIR / "config"
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_STATE_PATH = CONFIG_DIR / "config_state.json"
OLD_CONFIG_STATE_PATH = BASE_DIR / "data" / "config_state.json"

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

# Catalogs and lists persisted across restarts
_available_models: list[str] = [_current_model_id]
_available_voices: list[str] = [_current_voice]
_mcp_servers: list[dict] = [{"label": "Default MCP", "url": MCP_SERVER_URL}]

def _load_config_state() -> Dict[str, Any]:
    # Prefer new location
    if CONFIG_STATE_PATH.exists():
        try:
            with open(CONFIG_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    # Migrate from old location if present
    if OLD_CONFIG_STATE_PATH.exists():
        try:
            with open(OLD_CONFIG_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
            # Write to new path for future reads
            _save_config_state(state)
            return state
        except Exception:
            return {}
    return {}

def _save_config_state(state: Dict[str, Any]) -> None:
    try:
        with open(CONFIG_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Failed to persist config_state.json: {e}")

# Initialize runtime-config from persisted state if present
_state = _load_config_state()
try:
    am = _state.get("available_models")
    default_model_from_list = None
    if isinstance(am, list) and len(am) > 0 and str(am[0]).strip():
        default_model_from_list = str(am[0]).strip()
    default_model = default_model_from_list or _state.get("model_id") or _current_model_id
    set_model_id(default_model)
except Exception as e:
    print(f"Failed to determine startup model; using current default. err={e}")
if _state.get("voice"):
    try:
        set_voice(_state["voice"])
    except Exception as e:
        print(f"Failed to apply persisted voice: {e}")
if _state.get("ollama_base_url"):
    try:
        # Update Ollama host and reinitialize MODEL
        def set_ollama_base_url(new_url: str):
            global OLLAMA_BASE_URL, OLLAMA_HOST, MODEL
            OLLAMA_BASE_URL = new_url
            OLLAMA_HOST = new_url
            MODEL = Ollama(id=_current_model_id, host=OLLAMA_BASE_URL)
            print(f"OLLAMA_BASE_URL changed to: {new_url}")
        set_ollama_base_url(_state["ollama_base_url"])
    except Exception as e:
        print(f"Failed to apply persisted OLLAMA_BASE_URL: {e}")
if _state.get("mcp_transport"):
    MCP_TRANSPORT = _state.get("mcp_transport", MCP_TRANSPORT)
if _state.get("mcp_server_url"):
    MCP_SERVER_URL = _state.get("mcp_server_url", MCP_SERVER_URL)
if _state.get("mcp_stdio_command"):
    MCP_STDIO_COMMAND = _state.get("mcp_stdio_command", MCP_STDIO_COMMAND)
if _state.get("mcp_stdio_args"):
    try:
        args_val = _state.get("mcp_stdio_args")
        if isinstance(args_val, list):
            MCP_STDIO_ARGS = [str(x) for x in args_val]
        elif isinstance(args_val, str):
            MCP_STDIO_ARGS = _parse_stdio_args(args_val)
    except Exception:
        pass
if _state.get("available_models"):
    try:
        am = _state.get("available_models")
        if isinstance(am, list):
            _available_models = [str(x) for x in am if str(x)] or _available_models
    except Exception:
        pass
# Ensure voices catalog is loaded from persisted state
if _state.get("available_voices"):
    try:
        av = _state.get("available_voices")
        if isinstance(av, list):
            _available_voices = [str(v) for v in av if str(v)] or _available_voices
    except Exception:
        pass
if _state.get("mcp_servers"):
    try:
        ms = _state.get("mcp_servers")
        if isinstance(ms, list):
            _mcp_servers = [
                {"label": str(item.get("label", "Server")), "url": str(item.get("url", ""))}
                for item in ms
                if isinstance(item, dict) and str(item.get("url", ""))
            ] or _mcp_servers
    except Exception:
        pass

def get_runtime_config() -> Dict[str, Any]:
    return {
        "model": _current_model_id,
        "voice": _current_voice,
        "ollama_base_url": OLLAMA_BASE_URL,
        "openai_api_key_set": bool(OPENAI_API_KEY),
        "mcp_transport": MCP_TRANSPORT,
        "mcp_server_url": MCP_SERVER_URL,
        "mcp_stdio_command": MCP_STDIO_COMMAND,
        "mcp_stdio_args": MCP_STDIO_ARGS,
        "available_models": _available_models,
        "available_voices": _available_voices,
        "mcp_servers": _mcp_servers,
    }

def set_ollama_base_url(new_url: str) -> None:
    global OLLAMA_BASE_URL, OLLAMA_HOST, MODEL
    OLLAMA_BASE_URL = new_url
    OLLAMA_HOST = new_url
    MODEL = OpenAIChat(id=_current_model_id, base_url=get_openai_base_url(), api_key=OPENAI_API_KEY or "anything")
    print(f"OLLAMA_BASE_URL changed to: {new_url}")


def set_mcp_transport(new_transport: str) -> None:
    global MCP_TRANSPORT
    if new_transport not in ("streamable-http", "stdio"):
        raise ValueError("Invalid MCP transport. Use 'streamable-http' or 'stdio'.")
    MCP_TRANSPORT = new_transport.strip()
    print(f"MCP transport changed to: {MCP_TRANSPORT}")

def set_mcp_server_url(new_url: str) -> None:
    global MCP_SERVER_URL
    MCP_SERVER_URL = new_url.strip()
    print(f"MCP server URL changed to: {MCP_SERVER_URL}")

def set_mcp_stdio_command(cmd: str) -> None:
    global MCP_STDIO_COMMAND
    MCP_STDIO_COMMAND = cmd.strip()
    print(f"MCP stdio command changed to: {MCP_STDIO_COMMAND}")

def set_mcp_stdio_args(args: List[str] | str) -> None:
    global MCP_STDIO_ARGS
    if isinstance(args, list):
        MCP_STDIO_ARGS = [str(x) for x in args]
    elif isinstance(args, str):
        MCP_STDIO_ARGS = _parse_stdio_args(args)
    else:
        raise ValueError("mcp_stdio_args must be a list or string")
    print(f"MCP stdio args changed to: {MCP_STDIO_ARGS}")

def update_runtime_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    # Apply changes
    if "model" in cfg and cfg["model"]:
        set_model_id(str(cfg["model"]))
    if "voice" in cfg and cfg["voice"]:
        set_voice(str(cfg["voice"]))
    if "ollama_base_url" in cfg and cfg["ollama_base_url"]:
        set_ollama_base_url(str(cfg["ollama_base_url"]))
    if "openai_api_key" in cfg and cfg["openai_api_key"]:
        try:
            set_openai_api_key(str(cfg["openai_api_key"]))
        except Exception:
            pass
    if "mcp_transport" in cfg and cfg["mcp_transport"]:
        set_mcp_transport(str(cfg["mcp_transport"]))
    if "mcp_server_url" in cfg and cfg["mcp_server_url"] is not None:
        set_mcp_server_url(str(cfg["mcp_server_url"]))
    if "mcp_stdio_command" in cfg and cfg["mcp_stdio_command"] is not None:
        set_mcp_stdio_command(str(cfg["mcp_stdio_command"]))
    if "mcp_stdio_args" in cfg and cfg["mcp_stdio_args"] is not None:
        set_mcp_stdio_args(cfg["mcp_stdio_args"])  # accepts list or string

    # Optional lists management
    global _available_models, _mcp_servers
    if "available_models" in cfg and cfg["available_models"] is not None:
        try:
            models = cfg["available_models"]
            if isinstance(models, list):
                _available_models = [str(m) for m in models if str(m)] or _available_models
        except Exception:
            pass
    # Optional voices list management
    global _available_voices
    if "available_voices" in cfg and cfg["available_voices"] is not None:
        try:
            voices = cfg["available_voices"]
            if isinstance(voices, list):
                _available_voices = [str(v) for v in voices if str(v)] or _available_voices
        except Exception:
            pass
    if "mcp_servers" in cfg and cfg["mcp_servers"] is not None:
        try:
            servers = cfg["mcp_servers"]
            if isinstance(servers, list):
                cleaned = []
                for s in servers:
                    if isinstance(s, dict):
                        label = str(s.get("label", "Server")).strip()
                        url = str(s.get("url", "")).strip()
                        if url:
                            cleaned.append({"label": label or "Server", "url": url})
                if cleaned:
                    _mcp_servers = cleaned
        except Exception:
            pass

    # Persist state
    new_state = {
        "model_id": _current_model_id,
        "voice": _current_voice,
        "ollama_base_url": OLLAMA_BASE_URL,
        "openai_api_key_set": bool(OPENAI_API_KEY),
        "mcp_transport": MCP_TRANSPORT,
        "mcp_server_url": MCP_SERVER_URL,
        "mcp_stdio_command": MCP_STDIO_COMMAND,
        "mcp_stdio_args": MCP_STDIO_ARGS,
        "available_models": _available_models,
        "available_voices": _available_voices,
        "mcp_servers": _mcp_servers,
    }
    _save_config_state(new_state)
    return get_runtime_config()

def set_openai_api_key(key: str) -> None:
    global OPENAI_API_KEY
    OPENAI_API_KEY = str(key).strip()
    print("OPENAI_API_KEY updated (value hidden)")



# Export OLLAMA_BASE_URL and runtime config helpers for use in other modules
__all__ = [
    'MODEL', 'DB_URL', 'VECTOR_DB_URL', 'DATA_DIR', 'OLLAMA_BASE_URL',
    'VOSK_MODEL_PATH', 'TTS_CACHE_DIR', 'KOKORO_TTS_URL', 'KOKORO_TTS_CONFIG',
    'KOKORO_TTS_HEADERS', 'KOKORO_TTS_TIMEOUT', 'RHUBARB_PATH',
    'MCP_TRANSPORT', 'MCP_SERVER_URL', 'MCP_STDIO_COMMAND', 'MCP_STDIO_ARGS',
    'get_current_model', 'get_current_model_id', 'get_default_model_id', 'set_model_id', 
    'get_current_voice', 'get_default_voice', 'set_voice', 'get_user_pdf_dir', 'get_user_docx_dir', 'get_user_text_dir', 'get_user_csv_dir',
    'get_runtime_config', 'update_runtime_config', 'set_ollama_base_url',
    'set_mcp_transport', 'set_mcp_server_url', 'set_mcp_stdio_command', 'set_mcp_stdio_args'
]

# Database configuration
# Use DATABASE_URL from environment, default to localhost for non-Docker runs.
# The Dockerfile sets DATABASE_URL to postgresql://ai:ai@postgres:5432/ai
DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://ai:ai@localhost:5532/ai")
VECTOR_DB_URL = os.getenv("VECTOR_DB_URL", "postgresql+psycopg://ai:ai@localhost:5532/ai")

# Path configurations
# Determine Rhubarb executable path based on the operating system
if sys.platform == "win32":
    RHUBARB_PATH = BASE_DIR / "rhubarb" / "Rhubarb-Lip-Sync-1.13.0-Windows" / "rhubarb.exe"
else:
    # Path for the Linux executable, nested inside its directory
    RHUBARB_PATH = BASE_DIR / "rhubarb" / "Rhubarb-Lip-Sync-1.13.0-Linux" / "rhubarb"

def get_user_pdf_dir(user_id: str) -> Path:
    """Return the per-user PDF directory and ensure it exists."""
    user_dir = USER_PDFS_ROOT / str(user_id)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def get_user_docx_dir(user_id: str) -> Path:
    user_dir = USER_DOCX_ROOT / str(user_id)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def get_user_text_dir(user_id: str) -> Path:
    user_dir = USER_TEXT_ROOT / str(user_id)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def get_user_csv_dir(user_id: str) -> Path:
    user_dir = USER_CSV_ROOT / str(user_id)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

# STT configuration
# Use environment variable for Vosk model path, with fallback
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "../model/vosk-model-en-us-0.22")

# TTS configuration
TTS_CACHE_DIR = BASE_DIR / "tts_cache"
os.makedirs(TTS_CACHE_DIR, exist_ok=True)

# TTS cache cleanup policy (tunable via environment)
TTS_CACHE_KEEP_RECENT = int(os.getenv("TTS_CACHE_KEEP_RECENT", "50"))
TTS_CACHE_MAX_AGE_HOURS = int(os.getenv("TTS_CACHE_MAX_AGE_HOURS", "24"))
TTS_DELETE_AFTER_SERVE = os.getenv("TTS_DELETE_AFTER_SERVE", "true").lower() in ("1", "true", "yes", "y")
TTS_DELETE_DELAY_SECONDS = int(os.getenv("TTS_DELETE_DELAY_SECONDS", "120"))
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
print(f"Model ID: {_current_model_id}")
print(f"Database URL: {DB_URL}")
print(f"Vosk Model Path: {VOSK_MODEL_PATH}")
print(f"Kokoro TTS URL: {KOKORO_TTS_URL}")
