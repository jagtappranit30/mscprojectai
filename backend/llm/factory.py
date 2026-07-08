import os
from .base import BaseLLMClient
from .groq_client import GroqClient
from .ollama_client import OllamaClient
from ..utils.config import settings

class LLMClientFactory:
    """
    Factory class to instantiate the appropriate LLM client
    based on the configured provider.
    """

    @staticmethod
    def get_client() -> BaseLLMClient:
        provider = getattr(settings, "LLM_PROVIDER", os.getenv("LLM_PROVIDER", "groq")).lower().strip()

        if provider == "ollama":
            base_url = getattr(settings, "OLLAMA_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"))
            model_name = getattr(settings, "OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", "qwen2.5:7b"))
            return OllamaClient(base_url=base_url, model_name=model_name)
        
        # Default to Groq
        api_key = getattr(settings, "GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))
        return GroqClient(api_key=api_key)
