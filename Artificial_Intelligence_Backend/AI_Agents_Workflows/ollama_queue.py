"""
Rate limiting for local LLM providers (Ollama, Docker Model Runner).

Uses asyncio.Semaphore to limit concurrent requests to local GPU-based models,
while allowing cloud provider requests (OpenRouter, Gemini, OpenAI) to bypass.
"""
import asyncio
import os
import logging
import contextlib


# Max concurrent requests to local LLM providers (matches OLLAMA_NUM_PARALLEL)
MAX_CONCURRENT_LOCAL_LLM = int(os.getenv("MAX_CONCURRENT_LOCAL_LLM", "2"))

# Global semaphore instance
_local_llm_semaphore: asyncio.Semaphore | None = None


def _is_local_model(model_id: str) -> bool:
    """
    Check if a model uses local VRAM (Ollama or Docker Model Runner).
    
    Cloud providers have explicit prefixes:
    - openrouter/ -> OpenRouter cloud
    - openai/ -> OpenAI cloud API
    - gemini -> Google Gemini cloud
    
    Everything else (including gpt/ for Docker Model Runner) uses local GPU.
    """
    cloud_prefixes = ("openrouter/", "openai/", "gemini")
    return not any(model_id.startswith(prefix) for prefix in cloud_prefixes)


def get_local_llm_semaphore() -> asyncio.Semaphore:
    """Get or create the global semaphore for local LLM rate limiting."""
    global _local_llm_semaphore
    if _local_llm_semaphore is None:
        _local_llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LOCAL_LLM)
        logging.info(f"Local LLM semaphore initialized with {MAX_CONCURRENT_LOCAL_LLM} concurrent slots")
    return _local_llm_semaphore


@contextlib.asynccontextmanager
async def local_llm_rate_limit(model_id: str):
    """
    Async context manager for rate limiting local LLM requests.
    
    Only acquires semaphore for local providers (Ollama, Docker Model Runner).
    Cloud providers bypass the semaphore entirely.
    
    Usage:
        async with local_llm_rate_limit(model_id):
            response = await agent.run(query)
    """
    if _is_local_model(model_id):
        semaphore = get_local_llm_semaphore()
        logging.info(f"Waiting for local LLM slot for model: {model_id}")
        async with semaphore:
            logging.info(f"Acquired local LLM slot for model: {model_id}")
            try:
                yield
            finally:
                logging.info(f"Released local LLM slot for model: {model_id}")
    else:
        # Cloud provider - no rate limiting needed
        logging.info(f"Cloud model {model_id} - bypassing rate limit")
        yield
