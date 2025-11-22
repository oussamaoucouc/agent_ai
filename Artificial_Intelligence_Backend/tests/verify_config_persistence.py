import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Mock agno module
import sys
from unittest.mock import MagicMock

mock_agno = MagicMock()
sys.modules["agno"] = mock_agno
sys.modules["agno.models"] = mock_agno
sys.modules["agno.models.openai"] = mock_agno
sys.modules["agno.models.google"] = mock_agno
sys.modules["agno.models.openrouter"] = mock_agno
mock_agno.OpenAIChat = MagicMock()
mock_agno.Gemini = MagicMock()
mock_agno.OpenRouter = MagicMock()

from Artificial_Intelligence_Backend.AI_Agents_Workflows import config

def test_config_persistence():
    print("Testing Config Persistence...")
    
    # 1. Test update_runtime_config with new fields
    new_config = {
        "ollama_base_url": "http://test-ollama:11434",
        "openai_base_url": "https://test-openai.com/v1",
        "gemini_search_enabled": True,
        "available_models_labeled": [
            {"label": "Test Model", "id": "test-model", "provider": "ollama"},
            {"label": "GPT-4", "id": "gpt-4", "provider": "openai"}
        ]
    }
    
    config.update_runtime_config(new_config)
    
    # 2. Verify in-memory values
    print(f"OLLAMA_BASE_URL: {config.OLLAMA_BASE_URL}")
    assert config.OLLAMA_BASE_URL == "http://test-ollama:11434"
    

    
    print(f"GEMINI_SEARCH_ENABLED: {config.GEMINI_SEARCH_ENABLED}")
    assert config.GEMINI_SEARCH_ENABLED is True
    
    # 3. Verify available models labeled
    runtime_conf = config.get_runtime_config()
    models = runtime_conf["available_models_labeled"]
    print(f"Models: {models}")
    assert len(models) == 2
    assert models[0]["provider"] == "ollama"
    assert models[1]["provider"] == "openai"
    
    # 4. Verify persistence to file
    config_path = config.CONFIG_STATE_PATH
    with open(config_path, "r") as f:
        saved_state = json.load(f)
    
    print(f"Saved State: {saved_state}")
    assert saved_state["ollama_base_url"] == "http://test-ollama:11434"

    assert saved_state["gemini_search_enabled"] is True
    assert saved_state["available_models_labeled"][0]["provider"] == "ollama"
    
    print("Config Persistence Test Passed!")

if __name__ == "__main__":
    test_config_persistence()
