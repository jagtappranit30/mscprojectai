import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import httpx

from backend.llm.factory import LLMClientFactory
from backend.llm.groq_client import GroqClient
from backend.llm.ollama_client import OllamaClient


# ── 1. Factory Tests ──────────────────────────────────────────

def test_factory_provider_selection():
    # Test Groq selection
    with patch("backend.llm.factory.settings") as mock_settings:
        mock_settings.LLM_PROVIDER = "groq"
        mock_settings.GROQ_API_KEY = "test_key"
        client = LLMClientFactory.get_client()
        assert isinstance(client, GroqClient)

    # Test Ollama selection
    with patch("backend.llm.factory.settings") as mock_settings:
        mock_settings.LLM_PROVIDER = "ollama"
        mock_settings.OLLAMA_BASE_URL = "http://localhost:11434/v1"
        mock_settings.OLLAMA_MODEL = "qwen2.5:7b"
        client = LLMClientFactory.get_client()
        assert isinstance(client, OllamaClient)
        assert client.base_url == "http://localhost:11434/v1"
        assert client.model_name == "qwen2.5:7b"


# ── 2. Groq Client Tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_groq_client_success():
    client = GroqClient(api_key="test_key")
    client.client = MagicMock()
    
    mock_choice = MagicMock()
    mock_choice.message.content = '{"metric_name": "revenue", "value": 1000.0, "unit": "£", "confidence": 0.9, "source_quote": "rev 1000"}'
    client.client.chat.completions.create.return_value.choices = [mock_choice]

    result = await client.extract("prompt")
    assert result["metric_name"] == "revenue"
    assert result["value"] == 1000.0


@pytest.mark.asyncio
async def test_groq_client_retry():
    client = GroqClient(api_key="test_key")
    client.client = MagicMock()

    # First call raises a 429 rate limit exception, second succeeds
    mock_err = Exception("Rate limit error 429 - please try again in 0.01s.")
    setattr(mock_err, "status_code", 429)
    
    mock_choice = MagicMock()
    mock_choice.message.content = '{"metric_name": "headcount", "value": 5.0, "unit": "", "confidence": 1.0, "source_quote": ""}'

    client.client.chat.completions.create.side_effect = [mock_err, MagicMock(choices=[mock_choice])]

    # Use patch to speed up sleep during test retry
    with patch("asyncio.sleep", return_value=None):
        result = await client.extract("prompt")
        assert result["metric_name"] == "headcount"
        assert result["value"] == 5.0


# ── 3. Ollama Client Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_ollama_client_success():
    client = OllamaClient(base_url="http://localhost:11434/v1", model_name="qwen2.5:7b")

    mock_resp = httpx.Response(
        status_code=200,
        json={
            "choices": [{
                "message": {
                    "content": '{"metric_name": "revenue", "value": 500000.0, "unit": "£", "confidence": 0.8, "source_quote": ""}'
                }
            }]
        }
    )

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        result = await client.extract("prompt")
        assert result["metric_name"] == "revenue"
        assert result["value"] == 500000.0


@pytest.mark.asyncio
async def test_ollama_client_offline():
    client = OllamaClient(base_url="http://localhost:11434/v1", model_name="qwen2.5:7b")

    # Mock connection error
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(RuntimeError) as exc_info:
            await client.extract("prompt")
        assert "Ollama server is not available. Start it using: ollama serve" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ollama_client_model_missing():
    client = OllamaClient(base_url="http://localhost:11434/v1", model_name="qwen2.5:7b")

    mock_resp = httpx.Response(
        status_code=404,
        text="model 'qwen2.5:7b' not found, try pulling it first"
    )

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        with pytest.raises(RuntimeError) as exc_info:
            await client.extract("prompt")
        assert "Requested Ollama model not found. Run ollama pull qwen2.5:7b" in str(exc_info.value)
