"""
Model factory for creating AI models from different providers.
"""
from typing import Optional, Any
from agno.models.openai import OpenAIChat
from agno.models.google import Gemini

def create_model(
    model_id: str,
    openai_api_key: Optional[str] = None,
    google_api_key: Optional[str] = None,
    ollama_base_url: str = "http://localhost:12434",
    gemini_search_enabled: bool = False
) -> Any:
    """
    Create a model instance based on the model ID and provider.
    
    Args:
        model_id: The model identifier (e.g., "gpt-4", "gemini-2.0-flash-exp", "ai/granite-4.0-h-tiny:7B")
        openai_api_key: OpenAI API key (optional)
        google_api_key: Google API key for Gemini models (optional)
        ollama_base_url: Base URL for Ollama models
        gemini_search_enabled: Whether to enable Google Search tool for Gemini models
    
    Returns:
        Model instance (OpenAIChat or Gemini)
    """
    # Determine provider from model_id
    if model_id.startswith("gemini"):
        # Google Gemini model
        return Gemini(
            id=model_id,
            api_key=google_api_key,
            search=gemini_search_enabled
        )
    
    elif model_id.startswith("gpt-") or model_id.startswith("o1-") or model_id.startswith("o3-"):
        # OpenAI model
        return OpenAIChat(
            id=model_id,
            api_key=openai_api_key or "anything"
        )
    
    else:
        # Ollama model (default fallback)
        return OpenAIChat(
            id=model_id,
            base_url=ollama_base_url,
            api_key=openai_api_key or "anything"
        )


def get_provider_from_model_id(model_id: str) -> str:
    """
    Determine the provider from a model ID.
    
    Args:
        model_id: The model identifier
    
    Returns:
        Provider name: "google", "openai", or "ollama"
    """
    if model_id.startswith("gemini"):
        return "google"
    elif model_id.startswith("gpt-") or model_id.startswith("o1-") or model_id.startswith("o3-"):
        return "openai"
    else:
        return "ollama"
