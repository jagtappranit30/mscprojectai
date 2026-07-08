import asyncio
import re
from typing import Optional
from .base import BaseLLMClient

class GroqClient(BaseLLMClient):
    """
    Groq API client wrapper implementing BaseLLMClient interface.
    Preserves exact retry and backoff logic for rate limits.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.enabled = bool(api_key) and api_key not in ("placeholder", "")
        self.client = None
        if self.enabled:
            try:
                from groq import Groq  # type: ignore
                self.client = Groq(api_key=api_key)
            except Exception as exc:
                print(f"Failed to initialise Groq client: {exc}")
                self.enabled = False

    def _call_groq(self, prompt: str) -> str:
        """Synchronous Groq API call. Returns raw response text."""
        if not self.enabled or not self.client:
            raise RuntimeError("Groq API key is missing or client is disabled.")
        
        response = self.client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()

    async def _call_groq_async(self, prompt: str) -> str:
        """Asynchronous execution wrapper with rate-limit retry support."""
        for attempt in range(4):
            try:
                return await asyncio.to_thread(self._call_groq, prompt)
            except Exception as exc:
                is_rate_limit = False
                if getattr(exc, "status_code", None) == 429:
                    is_rate_limit = True
                elif "429" in str(exc) or "rate limit" in str(exc).lower():
                    is_rate_limit = True

                if is_rate_limit and attempt < 3:
                    wait_time = 4.0 * (2 ** attempt)
                    match = re.search(r"try again in ([\d\.]+)s", str(exc))
                    if match:
                        wait_time = float(match.group(1)) + 0.5

                    print(f"Groq Rate Limit (429) encountered. Retrying in {wait_time:.2f}s (attempt {attempt + 1}/4)...")
                    await asyncio.sleep(wait_time)
                else:
                    raise exc

        raise RuntimeError("Failed to complete Groq call after retries")

    async def extract(self, prompt: str) -> dict:
        """Main entry point to execute the prompt and return parsed JSON."""
        raw_response = await self._call_groq_async(prompt)
        return self._parse_json(raw_response)
