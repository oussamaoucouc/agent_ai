"""
Model factory for creating AI models from different providers.
"""
from typing import Optional, Any
from agno.models.openai import OpenAIChat
from agno.models.google import Gemini
from agno.models.openrouter import OpenRouter
from agno.models.ollama import Ollama

def create_model(
    model_id: str,
    openai_api_key: Optional[str] = None,
    google_api_key: Optional[str] = None,
    openrouter_api_key: Optional[str] = None,
    ollama_base_url: str = "http://host.docker.internal:11434",
    openai_base_url: str = "http://host.docker.internal:12434/engines/llama.cpp/v1",
    gemini_search_enabled: bool = False
) -> Any:
    """
    Create a model instance based on the model ID and provider.
    
    Args:
        model_id: The model identifier (e.g., "gpt-4", "gemini-2.0-flash-exp", "openrouter/gpt-4o", "gpt/granite-4.0-h-tiny:7B")
        openai_api_key: OpenAI API key (optional)
        google_api_key: Google API key for Gemini models (optional)
        openrouter_api_key: OpenRouter API key (optional)
        ollama_base_url: Base URL for Ollama models
        openai_base_url: Base URL for OpenAI-compatible models
        gemini_search_enabled: Whether to enable Google Search tool for Gemini models
    
    Returns:
        Model instance (OpenAIChat, Gemini, or OpenRouter)
    """
    # Determine provider from model_id
    if model_id.startswith("gemini"):
        # Google Gemini model
        return Gemini(
            id=model_id.replace("gemini/", ""),
            api_key=google_api_key,
            search=gemini_search_enabled,
            generation_config={"response_mime_type": None}
        )
    
    elif model_id.startswith("openrouter/"):
        # OpenRouter model - MUST come before OpenAI check
        return OpenRouter(
            id=model_id.replace("openrouter/", ""),
            api_key=openrouter_api_key
        )
    
    elif model_id.startswith("gpt/"):
        # OpenAI-compatible model (local)
        return OpenAIChat(
            id=model_id.replace("gpt/", ""),
            base_url=openai_base_url,
            api_key="anything"
        )
    elif model_id.startswith("openai/"):
        # OpenAI-compatible model (local)
        return OpenAIChat(
            id=model_id.replace("openai/", ""),
            api_key=openai_api_key
        )
    
    else:
        # Ollama model (default fallback)
        # Performance optimizations: force GPU layers and lock model in memory
        return Ollama(
            id=model_id,
            host=ollama_base_url,
            options={
                "num_gpu": 999,      # Offload all layers to GPU for max speed
                "use_mlock": True,   # Lock model in RAM to prevent swapping
            }
        )


def get_provider_from_model_id(model_id: str) -> str:
    """
    Determine the provider from a model ID.
    
    Args:
        model_id: The model identifier
    
    Returns:
        Provider name: "google", "openrouter", "openai", or "ollama"
    """
    if model_id.startswith("gemini"):
        return "google"
    elif model_id.startswith("openrouter/"):
        return "openrouter"
    elif model_id.startswith("gpt/"):
        return "openai"
    elif model_id.startswith("openai/"):
        return "openai"
    else:
        return "ollama"
