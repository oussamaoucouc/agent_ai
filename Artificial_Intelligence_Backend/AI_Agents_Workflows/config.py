"""
Configuration settings for the AI Assistant application.
"""
import os
import sys
import json
import re
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from agno.models.openai import OpenAIChat

# Ensure parent directory is in path for Docker
import sys
from pathlib import Path
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from . import model_factory
except ImportError:
    from AI_Agents_Workflows import model_factory

# Ollama configuration
# Use OLLAMA_BASE_URL from environment, with fallback to localhost for local development
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_HOST = OLLAMA_BASE_URL


# OpenAI-compatible configuration
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://host.docker.internal:12434/engines/llama.cpp/v1")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = ""  # Loaded from config_state.json, not environment
OPENROUTER_API_KEY = ""  # Loaded from config_state.json, not environment
AGNO_API_KEY = ""  # Loaded from config_state.json, not environment
GEMINI_SEARCH_ENABLED = False  # Global toggle for Gemini Search tool

def get_openai_base_url() -> str:
    try:
        return str(OPENAI_BASE_URL).strip()
    except Exception:
        return OPENAI_BASE_URL

# Use the model that's actually pulled in docker-compose
#MODEL_ID = "ai_teacher_qwen" # Use the model without thinking capabilities
MODEL_ID = "ai/granite-4.0-h-tiny:7B" # Use the model without thinking capabilities

# Dynamic configuration variables for runtime changes
_current_model_id = MODEL_ID
_current_voice = "af_sky"

# MCP runtime-configurable settings
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "streamable-http").strip()
MCP_SERVER_URL = "http://mcp-gateway:8080/mcp"  # Docker MCP Gateway (no auth needed)
MCP_STDIO_COMMAND = os.getenv("MCP_STDIO_COMMAND", "").strip()
_MCP_STDIO_ARGS_RAW = os.getenv("MCP_STDIO_ARGS", "").strip()
_MCP_STDIO_COMMANDS_RAW = os.getenv("MCP_STDIO_COMMANDS", "").strip()

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
    
    # Ensure Google API key is loaded if selecting Gemini
    if new_model_id.startswith("gemini") and not GOOGLE_API_KEY:
        print("Google API key missing for Gemini. Attempting to reload from config_state.json...")
        try:
            state = _load_config_state()
            if state.get("google_api_key"):
                set_google_api_key(state["google_api_key"])
        except Exception as e:
            print(f"Error reloading config state: {e}")
    
    # Ensure OpenRouter API key is loaded if selecting OpenRouter
    if new_model_id.startswith("openrouter/") and not OPENROUTER_API_KEY:
        print("OpenRouter API key missing. Attempting to reload from config_state.json...")
        try:
            state = _load_config_state()
            if state.get("openrouter_api_key"):
                set_openrouter_api_key(state["openrouter_api_key"])
        except Exception as e:
            print(f"Error reloading config state: {e}")

    # Debug logging for API keys
    google_key_set = bool(GOOGLE_API_KEY and GOOGLE_API_KEY.strip())
    openrouter_key_set = bool(OPENROUTER_API_KEY and OPENROUTER_API_KEY.strip())
    
    if new_model_id.startswith("openrouter/"):
        print(f"DEBUG: OpenRouter Key present: {openrouter_key_set}")
        if openrouter_key_set:
            print(f"DEBUG: OpenRouter Key length: {len(OPENROUTER_API_KEY)}")
            print(f"DEBUG: OpenRouter Key start: {OPENROUTER_API_KEY[:10]}...")
        else:
            print("DEBUG: OpenRouter Key is EMPTY or None")
            
    print(f"Setting model to {new_model_id}. Google API Key set: {google_key_set}, OpenRouter API Key set: {openrouter_key_set}")
    
    MODEL = model_factory.create_model(
        model_id=new_model_id,
        openai_api_key=OPENAI_API_KEY,
        google_api_key=GOOGLE_API_KEY,
        openrouter_api_key=OPENROUTER_API_KEY,
        ollama_base_url=OLLAMA_BASE_URL,
        openai_base_url=OPENAI_BASE_URL,
        gemini_search_enabled=GEMINI_SEARCH_ENABLED
    )
    print(f"Model changed to: {new_model_id}")

def set_google_api_key(key: str) -> None:
    """Set Google API key for Gemini models."""
    global GOOGLE_API_KEY
    GOOGLE_API_KEY = str(key).strip()
    print("GOOGLE_API_KEY updated (value hidden)")

def set_gemini_search_enabled(enabled: bool) -> None:
    """Set global Gemini Search toggle."""
    global GEMINI_SEARCH_ENABLED
    GEMINI_SEARCH_ENABLED = bool(enabled)
    print(f"Gemini Search enabled: {GEMINI_SEARCH_ENABLED}")

# --- OpenRouter API Key Management ---
def set_openrouter_api_key(key: str) -> None:
    """Set OpenRouter API key for OpenRouter models."""
    global OPENROUTER_API_KEY
    OPENROUTER_API_KEY = str(key).strip()
    os.environ["OPENROUTER_API_KEY"] = OPENROUTER_API_KEY
    print("OPENROUTER_API_KEY updated (value hidden)")

# --- AGNO API Key Management ---
def set_agno_api_key(key: str) -> None:
    """Set AGNO API key for agent monitoring."""
    global AGNO_API_KEY
    AGNO_API_KEY = str(key).strip()
    os.environ["AGNO_API_KEY"] = AGNO_API_KEY
    print("AGNO_API_KEY updated (value hidden)")

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
USER_PPTX_ROOT = DOCS_BASE_DIR / "pptx"
USER_IMAGES_ROOT = DOCS_BASE_DIR / "images"
os.makedirs(USER_PDFS_ROOT, exist_ok=True)
os.makedirs(USER_DOCX_ROOT, exist_ok=True)
os.makedirs(USER_TEXT_ROOT, exist_ok=True)
os.makedirs(USER_CSV_ROOT, exist_ok=True)
os.makedirs(USER_PPTX_ROOT, exist_ok=True)
os.makedirs(USER_IMAGES_ROOT, exist_ok=True)

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

def _parse_stdio_commands(raw: str) -> list[str]:
    try:
        if raw and raw.startswith("["):
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
            return [str(parsed).strip()]
        elif raw:
            # Semicolon or newline separated list fallback
            parts = [p.strip() for p in re.split(r"[\n;]", raw) if p and p.strip()]
            return parts
        else:
            return []
    except Exception:
        return [p.strip() for p in re.split(r"[\n;]", raw) if p and p.strip()]

# Catalogs and lists persisted across restarts

# Catalogs and lists persisted across restarts
_available_models: list[str] = [_current_model_id]
_available_models_labeled: list[dict] = []
# Try to load available voices from voices.json if it exists
_available_voices: list[str] = [_current_voice]
try:
    _voices_path = Path(__file__).parent.parent / "models" / "kokoro" / "voices.json"
    if _voices_path.exists():
        with open(_voices_path, "r") as _f:
            _v_data = json.load(_f)
            _loaded_voices = sorted(list(_v_data.keys()))
            if _loaded_voices:
                _available_voices = _loaded_voices
except Exception as e:
    print(f"Failed to load voices.json: {e}")

_available_voices_labeled: list[dict] = []
_mcp_servers: list[dict] = [{"label": "Default MCP", "url": MCP_SERVER_URL}]
_mcp_stdio_commands: list[str] = _parse_stdio_commands(_MCP_STDIO_COMMANDS_RAW)
_mcp_stdio_tools: list[dict] = []

def _load_config_state() -> Dict[str, Any]:
    # Prefer new location
    # Prefer new location
    if CONFIG_STATE_PATH.exists():
        try:
            print(f"Loading config state from: {CONFIG_STATE_PATH}")
            with open(CONFIG_STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                key_present = bool(data.get("google_api_key"))
                print(f"Config loaded. Google API key present: {key_present}")
                return data
        except Exception as e:
            print(f"Error loading config state: {e}")
            return {}
    else:
        print(f"Config state file not found at: {CONFIG_STATE_PATH}")
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
# Load Google API key from config
if _state.get("google_api_key"):
    try:
        set_google_api_key(_state["google_api_key"])
    except Exception as e:
        print(f"Failed to apply persisted Google API key: {e}")

# Load OpenRouter API key from config
if _state.get("openrouter_api_key"):
    try:
        set_openrouter_api_key(_state["openrouter_api_key"])
    except Exception as e:
        print(f"Failed to apply persisted OpenRouter API key: {e}")

# Load AGNO API key from config
if _state.get("agno_api_key"):
    try:
        set_agno_api_key(_state["agno_api_key"])
    except Exception as e:
        print(f"Failed to apply persisted AGNO API key: {e}")

# Load Gemini search toggle
if "gemini_search_enabled" in _state:
    try:
        set_gemini_search_enabled(_state["gemini_search_enabled"])
    except Exception as e:
        print(f"Failed to apply persisted Gemini search setting: {e}")

try:
    am = _state.get("available_models")
    default_model_from_list = None
    if isinstance(am, list) and len(am) > 0 and str(am[0]).strip():
        default_model_from_list = str(am[0]).strip()
    default_model = default_model_from_list or _state.get("model_id") or _current_model_id
    set_model_id(default_model)
except Exception as e:
    print(f"Failed to determine startup model; using current default. err={e}")
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
if _state.get("mcp_stdio_commands"):
    try:
        cmds_val = _state.get("mcp_stdio_commands")
        if isinstance(cmds_val, list):
            _mcp_stdio_commands = [str(x).strip() for x in cmds_val if str(x).strip()] or _mcp_stdio_commands
        elif isinstance(cmds_val, str):
            _mcp_stdio_commands = _parse_stdio_commands(cmds_val) or _mcp_stdio_commands
    except Exception:
        pass
if _state.get("available_models"):
    try:
        am = _state.get("available_models")
        if isinstance(am, list):
            _available_models = [str(x) for x in am if str(x)] or _available_models
    except Exception:
        pass
# Optional labeled models
if _state.get("available_models_labeled"):
    try:
        aml = _state.get("available_models_labeled")
        if isinstance(aml, list):
            _available_models_labeled = [
                {
                    "label": str(item.get("label", "Model")), 
                    "id": str(item.get("id", "")).strip(), 
                    "provider": str(item.get("provider", "")),
                    "supports_images": bool(item.get("supports_images", False)),
                    "supports_audio": bool(item.get("supports_audio", False)),
                    "supports_videos": bool(item.get("supports_videos", False))
                }
                for item in aml if isinstance(item, dict) and str(item.get("id", "")).strip()
            ] or _available_models_labeled
            if not _available_models:
                _available_models = [m["id"] for m in _available_models_labeled]
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
# Optional labeled voices
if _state.get("available_voices_labeled"):
    try:
        avl = _state.get("available_voices_labeled")
        if isinstance(avl, list):
            _available_voices_labeled = [
                {"label": str(item.get("label", "Voice")), "id": str(item.get("id", "")).strip()}
                for item in avl if isinstance(item, dict) and str(item.get("id", "")).strip()
            ] or _available_voices_labeled
            if not _available_voices:
                _available_voices = [v["id"] for v in _available_voices_labeled]
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
if _state.get("mcp_stdio_tools"):
    try:
        st = _state.get("mcp_stdio_tools")
        if isinstance(st, list):
            _mcp_stdio_tools = [
                {"label": str(item.get("label", "Command")), "command": str(item.get("command", "")).strip()}
                for item in st
                if isinstance(item, dict) and str(item.get("command", "")).strip()
            ] or _mcp_stdio_tools
    except Exception:
        pass

# --- Provider Lookup Functions ---
def get_provider_for_model(model_id: str) -> str | None:
    """Lookup provider for a model from metadata.
    
    Args:
        model_id: The model ID to lookup
    
    Returns:
        Provider string ("openai", "gemini", "ollama") or None if not found
    """
    try:
        for model in _available_models_labeled:
            if isinstance(model, dict) and model.get("id") == model_id:
                return model.get("provider")
    except Exception:
        pass
    return None

def get_model_metadata(model_id: str) -> dict | None:
    """Get full metadata for a model.
    
    Args:
        model_id: The model ID to lookup
    
    Returns:
        Model metadata dict or None if not found
    """
    try:
        for model in _available_models_labeled:
            if isinstance(model, dict) and model.get("id") == model_id:
                return model.copy()
    except Exception:
        pass
    return None

def get_model_multimodal_capabilities(model_id: str) -> dict:
    """Get multimodal capabilities for a model from metadata.
    
    Args:
        model_id: The model ID to lookup
    
    Returns:
        dict with supports_images, supports_audio, supports_videos (all default to False)
    """
    meta = get_model_metadata(model_id)
    if meta:
        return {
            'supports_images': meta.get('supports_images', False),
            'supports_audio': meta.get('supports_audio', False),
            'supports_videos': meta.get('supports_videos', False)
        }
    return {
        'supports_images': False,
        'supports_audio': False,
        'supports_videos': False
    }

def get_runtime_config() -> Dict[str, Any]:
    return {
        "model": _current_model_id,
        "voice": _current_voice,
        "ollama_base_url": OLLAMA_BASE_URL,
        "openai_base_url": OPENAI_BASE_URL,
        "openai_api_key_set": bool(OPENAI_API_KEY),
        "google_api_key_set": bool(GOOGLE_API_KEY),
        "openrouter_api_key_set": bool(OPENROUTER_API_KEY),
        "agno_api_key_set": bool(AGNO_API_KEY),
        "gemini_search_enabled": GEMINI_SEARCH_ENABLED,
        "mcp_transport": MCP_TRANSPORT,
        "mcp_server_url": MCP_SERVER_URL,
        "mcp_stdio_command": MCP_STDIO_COMMAND,
        "mcp_stdio_args": MCP_STDIO_ARGS,
        "mcp_stdio_commands": _mcp_stdio_commands,
        "mcp_stdio_tools": _mcp_stdio_tools,
        "available_models": _available_models,
        "available_models_labeled": _available_models_labeled,
        "available_voices": _available_voices,
        "available_voices_labeled": _available_voices_labeled,
        "mcp_servers": _mcp_servers,
    }

def set_ollama_base_url(new_url: str):
    global OLLAMA_BASE_URL, OLLAMA_HOST, MODEL
    OLLAMA_BASE_URL = new_url
    OLLAMA_HOST = new_url
    MODEL = model_factory.create_model(
        model_id=_current_model_id,
        openai_api_key=OPENAI_API_KEY,
        google_api_key=GOOGLE_API_KEY,
        openrouter_api_key=OPENROUTER_API_KEY,
        ollama_base_url=OLLAMA_BASE_URL,
        openai_base_url=OPENAI_BASE_URL,
        gemini_search_enabled=GEMINI_SEARCH_ENABLED
    )
    print(f"OLLAMA_BASE_URL changed to: {new_url}")

def set_openai_base_url(new_url: str):
    global OPENAI_BASE_URL, MODEL
    OPENAI_BASE_URL = new_url
    MODEL = model_factory.create_model(
        model_id=_current_model_id,
        openai_api_key=OPENAI_API_KEY,
        google_api_key=GOOGLE_API_KEY,
        openrouter_api_key=OPENROUTER_API_KEY,
        ollama_base_url=OLLAMA_BASE_URL,
        openai_base_url=OPENAI_BASE_URL,
        gemini_search_enabled=GEMINI_SEARCH_ENABLED
    )
    print(f"OPENAI_BASE_URL changed to: {new_url}")


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

def set_mcp_stdio_commands(cmds: List[str] | str) -> None:
    global _mcp_stdio_commands
    if isinstance(cmds, list):
        _mcp_stdio_commands = [str(c).strip() for c in cmds if str(c).strip()]
    elif isinstance(cmds, str):
        _mcp_stdio_commands = _parse_stdio_commands(cmds)
    else:
        raise ValueError("mcp_stdio_commands must be a list or string")
    print(f"MCP stdio commands changed to: {_mcp_stdio_commands}")

def set_mcp_stdio_tools(tools: List[Dict[str, str]]) -> None:
    global _mcp_stdio_tools
    cleaned: list[dict] = []
    for t in tools or []:
        if isinstance(t, dict):
            label = str(t.get("label", "Command")).strip() or "Command"
            command = str(t.get("command", "")).strip()
            if command:
                cleaned.append({"label": label, "command": command})
    if cleaned:
        _mcp_stdio_tools = cleaned
    print(f"MCP stdio tools changed: {len(_mcp_stdio_tools)} item(s)")

def update_runtime_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    # Apply changes
    if "model" in cfg and cfg["model"]:
        set_model_id(str(cfg["model"]))
    if "voice" in cfg and cfg["voice"]:
        set_voice(str(cfg["voice"]))
    if "ollama_base_url" in cfg and cfg["ollama_base_url"]:
        set_ollama_base_url(str(cfg["ollama_base_url"]))
    if "openai_base_url" in cfg and cfg["openai_base_url"]:
        set_openai_base_url(str(cfg["openai_base_url"]))
    if "openai_api_key" in cfg and cfg["openai_api_key"]:
        try:
            set_openai_api_key(str(cfg["openai_api_key"]))
        except Exception:
            pass
    if "google_api_key" in cfg and cfg["google_api_key"]:
        try:
            set_google_api_key(str(cfg["google_api_key"]))
        except Exception:
            pass
    if "openrouter_api_key" in cfg and cfg["openrouter_api_key"]:
        try:
            set_openrouter_api_key(str(cfg["openrouter_api_key"]))
        except Exception:
            pass
    if "agno_api_key" in cfg and cfg["agno_api_key"]:
        try:
            set_agno_api_key(str(cfg["agno_api_key"]))
        except Exception:
            pass
    if "gemini_search_enabled" in cfg and cfg["gemini_search_enabled"] is not None:
        set_gemini_search_enabled(bool(cfg["gemini_search_enabled"]))
    if "mcp_transport" in cfg and cfg["mcp_transport"]:
        set_mcp_transport(str(cfg["mcp_transport"]))
    if "mcp_server_url" in cfg and cfg["mcp_server_url"] is not None:
        set_mcp_server_url(str(cfg["mcp_server_url"]))
    if "mcp_stdio_command" in cfg and cfg["mcp_stdio_command"] is not None:
        set_mcp_stdio_command(str(cfg["mcp_stdio_command"]))
    if "mcp_stdio_args" in cfg and cfg["mcp_stdio_args"] is not None:
        set_mcp_stdio_args(cfg["mcp_stdio_args"])  # accepts list or string
    if "mcp_stdio_commands" in cfg and cfg["mcp_stdio_commands"] is not None:
        set_mcp_stdio_commands(cfg["mcp_stdio_commands"])  # accepts list or string
    if "mcp_stdio_tools" in cfg and cfg["mcp_stdio_tools"] is not None:
        try:
            tools = cfg["mcp_stdio_tools"]
            if isinstance(tools, list):
                set_mcp_stdio_tools(tools)
        except Exception:
            pass

    # Optional lists management
    global _available_models, _available_models_labeled, _mcp_servers
    if "available_models" in cfg and cfg["available_models"] is not None:
        try:
            models = cfg["available_models"]
            if isinstance(models, list):
                _available_models = [str(m) for m in models if str(m)] or _available_models
        except Exception:
            pass
    if "available_models_labeled" in cfg and cfg["available_models_labeled"] is not None:
        try:
            aml = cfg["available_models_labeled"]
            if isinstance(aml, list):
                cleaned = []
                for item in aml:
                    if isinstance(item, dict):
                        label = str(item.get("label", "Model")).strip() or "Model"
                        mid = str(item.get("id", "")).strip()
                        provider = str(item.get("provider", "")).strip()
                        # Preserve multimodal capabilities
                        supports_images = bool(item.get("supports_images", False))
                        supports_audio = bool(item.get("supports_audio", False))
                        supports_videos = bool(item.get("supports_videos", False))
                        if mid:
                            cleaned.append({
                                "label": label,
                                "id": mid,
                                "provider": provider,
                                "supports_images": supports_images,
                                "supports_audio": supports_audio,
                                "supports_videos": supports_videos
                            })
                if cleaned:
                    _available_models_labeled = cleaned
                    _available_models = [m["id"] for m in cleaned]
        except Exception:
            pass
    # Optional voices list management
    global _available_voices, _available_voices_labeled
    if "available_voices" in cfg and cfg["available_voices"] is not None:
        try:
            voices = cfg["available_voices"]
            if isinstance(voices, list):
                _available_voices = [str(v) for v in voices if str(v)] or _available_voices
        except Exception:
            pass
    if "available_voices_labeled" in cfg and cfg["available_voices_labeled"] is not None:
        try:
            avl = cfg["available_voices_labeled"]
            if isinstance(avl, list):
                cleaned_v = []
                for item in avl:
                    if isinstance(item, dict):
                        label = str(item.get("label", "Voice")).strip() or "Voice"
                        vid = str(item.get("id", "")).strip()
                        if vid:
                            cleaned_v.append({"label": label, "id": vid})
                if cleaned_v:
                    _available_voices_labeled = cleaned_v
                    _available_voices = [v["id"] for v in cleaned_v]
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
        "openai_base_url": OPENAI_BASE_URL,
        "openai_api_key_set": bool(OPENAI_API_KEY),
        "google_api_key": GOOGLE_API_KEY,
        "openrouter_api_key": OPENROUTER_API_KEY,
        "agno_api_key": AGNO_API_KEY,
        "gemini_search_enabled": GEMINI_SEARCH_ENABLED,
        "mcp_transport": MCP_TRANSPORT,
        "mcp_server_url": MCP_SERVER_URL,
        "mcp_stdio_command": MCP_STDIO_COMMAND,
        "mcp_stdio_args": MCP_STDIO_ARGS,
        "mcp_stdio_commands": _mcp_stdio_commands,
        "mcp_stdio_tools": _mcp_stdio_tools,
        "available_models": _available_models,
        "available_models_labeled": _available_models_labeled,
        "available_voices": _available_voices,
        "available_voices_labeled": _available_voices_labeled,
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
    'get_current_voice', 'get_default_voice', 'set_voice', 'get_user_pdf_dir', 'get_user_docx_dir', 'get_user_text_dir', 'get_user_csv_dir', 'get_user_pptx_dir', 'get_user_images_dir',
    'get_runtime_config', 'update_runtime_config', 'set_ollama_base_url', 'set_openai_base_url',
    'set_mcp_transport', 'set_mcp_server_url', 'set_mcp_stdio_command', 'set_mcp_stdio_args', 'set_mcp_stdio_commands'
    , 'set_mcp_stdio_tools'
]

# Database configuration
# Use DATABASE_URL from environment, default to localhost for non-Docker runs.
# The Dockerfile sets DATABASE_URL to postgresql://ai:ai@postgres:5432/ai
# Added search_path=ai to ensure all tables are created in the 'ai' schema by default
DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://ai:ai@localhost:5532/ai?options=-csearch_path%3Dai,rag")
VECTOR_DB_URL = os.getenv("VECTOR_DB_URL", "postgresql+psycopg://ai:ai@localhost:5532/ai?options=-csearch_path%3Dai,rag")

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

def get_user_pptx_dir(user_id: str) -> Path:
    """Return the per-user PPTX directory and ensure it exists."""
    user_dir = USER_PPTX_ROOT / str(user_id)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def get_user_images_dir(user_id: str) -> Path:
    """Return the per-user images directory and ensure it exists."""
    user_dir = USER_IMAGES_ROOT / str(user_id)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

# STT configuration
# Use environment variable for Vosk model path, with fallback
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "../../model/vosk-model-en-us-0.22")

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
