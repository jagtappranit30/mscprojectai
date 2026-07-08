import httpx
from .base import BaseLLMClient

class OllamaClient(BaseLLMClient):
    """
    Ollama API client wrapper implementing BaseLLMClient interface.
    Uses the OpenAI-compatible local HTTP endpoint.
    """

    def __init__(self, base_url: str, model_name: str):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    async def extract(self, prompt: str) -> dict:
        """
        Sends prompt to Ollama, handles connection/model errors,
        and parses the response JSON.
        """
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 300,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise RuntimeError(
                "Ollama server is not available. Start it using: ollama serve"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Ollama connection failed: {exc}") from exc

        # Handle specific error codes or response states
        if response.status_code == 404 or "not found" in response.text.lower():
            # Check if it was a missing model error
            raise RuntimeError(
                f"Requested Ollama model not found. Run ollama pull {self.model_name}"
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"Ollama returned status code {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
            raw_text = data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            raise RuntimeError(
                f"Failed to parse Ollama response format: {response.text}"
            ) from exc

        return self._parse_json(raw_text)
