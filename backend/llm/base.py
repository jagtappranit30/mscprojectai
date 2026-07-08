import re
import json
from abc import ABC, abstractmethod

class BaseLLMClient(ABC):
    """
    Abstract Base Class for LLM clients.
    All interchangeable providers (e.g. Groq, Ollama) must implement this interface.
    """

    @abstractmethod
    async def extract(self, prompt: str) -> dict:
        """
        Sends the extraction prompt to the LLM backend,
        and returns the parsed response as a JSON dictionary.
        """
        pass

    def _parse_json(self, raw_text: str) -> dict:
        """
        Helper method to strip markdown wrappers and extract a JSON dictionary.
        Keeps parsing logic unified across all LLM clients.
        """
        clean = raw_text.strip()
        if clean.startswith("```"):
            parts = clean.split("```")
            clean = parts[1].strip()
            if clean.startswith("json"):
                clean = clean[4:].strip()

        # Extract the first JSON object if surrounded by noise
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            clean = match.group(0)

        return json.loads(clean)
