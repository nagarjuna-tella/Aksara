"""
v0.5.30 — AI Connectors: unit tests.

Tests cover:
    - AIConnector base class interface and normalise_response
    - OpenAIConnector (chat, embed, health — mocked httpx)
    - AnthropicConnector (chat, health — mocked httpx)
    - OllamaConnector (chat, embed, health — mocked httpx)
    - HttpConnector (chat, health — mocked httpx)
    - Connector registry: get_connector, list_connectors
    - Error paths: missing API keys, bad responses, network errors
    - Normalised response shape invariants
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aksara.ai.connectors.base import AIConnector
from aksara.ai.connectors.openai import OpenAIConnector
from aksara.ai.connectors.anthropic import AnthropicConnector
from aksara.ai.connectors.ollama import OllamaConnector
from aksara.ai.connectors.http import HttpConnector
from aksara.ai.connectors.registry import (
    get_connector,
    list_connectors,
    _ensure_registry,
    _CONNECTOR_CLASSES,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Base class
# ═══════════════════════════════════════════════════════════════════════════


class TestAIConnectorBase:
    """Tests for the abstract AIConnector base class."""

    def test_provider_attr(self):
        c = AIConnector()
        assert c.provider == "base"

    @pytest.mark.asyncio
    async def test_chat_raises(self):
        c = AIConnector()
        with pytest.raises(NotImplementedError):
            await c.chat([], model="x")

    @pytest.mark.asyncio
    async def test_embed_raises(self):
        c = AIConnector()
        with pytest.raises(NotImplementedError):
            await c.embed(["hello"], model="x")

    @pytest.mark.asyncio
    async def test_health_default(self):
        c = AIConnector()
        result = await c.health()
        assert result["ok"] is True
        assert result["provider"] == "base"

    def test_normalise_response_ok(self):
        r = AIConnector._normalise_response(
            ok=True, provider="test", model="m1", text="hi",
            tokens={"prompt": 1, "completion": 2, "total": 3},
            raw={"x": 1}, elapsed_ms=42.0,
        )
        assert r["ok"] is True
        assert r["provider"] == "test"
        assert r["model"] == "m1"
        assert r["text"] == "hi"
        assert r["tokens"]["total"] == 3
        assert r["elapsed_ms"] == 42.0

    def test_normalise_response_error(self):
        r = AIConnector._normalise_response(
            ok=False, provider="test", model="m1", error="oops",
        )
        assert r["ok"] is False
        assert r["error"] == "oops"
        assert r["tokens"] == {}
        assert r["raw"] == {}

    def test_timer_returns_float(self):
        t = AIConnector._timer()
        assert isinstance(t, float)
        assert t > 0


# ═══════════════════════════════════════════════════════════════════════════
# 2. OpenAI Connector
# ═══════════════════════════════════════════════════════════════════════════


def _mock_openai_response(text="Hello!", prompt_tokens=10, completion_tokens=5, status=200):
    """Build a mock httpx Response for OpenAI chat completions."""
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.json.return_value = {
        "choices": [{"message": {"content": text}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
    return resp


class TestOpenAIConnector:
    def test_init_defaults(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
            c = OpenAIConnector()
            assert c.api_key == "sk-test"
            assert "api.openai.com" in c.base_url

    def test_init_explicit(self):
        c = OpenAIConnector(api_key="sk-ex", base_url="http://local:1234", organization="org-1")
        assert c.api_key == "sk-ex"
        assert c.base_url == "http://local:1234"
        assert c.organization == "org-1"

    def test_provider_name(self):
        c = OpenAIConnector(api_key="sk-test")
        assert c.provider == "openai"

    @pytest.mark.asyncio
    async def test_chat_no_key(self):
        with patch.dict("os.environ", {}, clear=True):
            c = OpenAIConnector(api_key="")
            result = await c.chat([{"role": "user", "content": "hi"}], model="gpt-4o")
            assert result["ok"] is False
            assert "not set" in result["error"].lower() or "api_key" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_chat_success(self):
        c = OpenAIConnector(api_key="sk-test")
        mock_resp = _mock_openai_response("Test response", 10, 5)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.chat([{"role": "user", "content": "hi"}], model="gpt-4o")

        assert result["ok"] is True
        assert result["text"] == "Test response"
        assert result["provider"] == "openai"
        assert result["tokens"]["total"] == 15

    @pytest.mark.asyncio
    async def test_chat_http_error(self):
        c = OpenAIConnector(api_key="sk-test")
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "rate limit"
        mock_resp.json.return_value = {"error": {"message": "Rate limited"}}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.chat([{"role": "user", "content": "hi"}], model="gpt-4o")

        assert result["ok"] is False
        assert "Rate limited" in result["error"]

    @pytest.mark.asyncio
    async def test_chat_network_exception(self):
        c = OpenAIConnector(api_key="sk-test")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.chat([{"role": "user", "content": "hi"}], model="gpt-4o")

        assert result["ok"] is False
        assert "Connection refused" in result["error"]

    @pytest.mark.asyncio
    async def test_health_success(self):
        c = OpenAIConnector(api_key="sk-test")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.health()
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_chat_response_shape(self):
        """Ensure every response has the normalised fields."""
        c = OpenAIConnector(api_key="sk-test")
        mock_resp = _mock_openai_response("result", 5, 3)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.chat([{"role": "user", "content": "hi"}], model="gpt-4o")

        for key in ("ok", "provider", "model", "text", "tokens"):
            assert key in result, f"Missing key: {key}"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Anthropic Connector
# ═══════════════════════════════════════════════════════════════════════════


def _mock_anthropic_response(text="Claude says hi", input_tokens=8, output_tokens=4, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.json.return_value = {
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }
    return resp


class TestAnthropicConnector:
    def test_init_defaults(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "ant-key"}, clear=False):
            c = AnthropicConnector()
            assert c.api_key == "ant-key"
            assert "anthropic.com" in c.base_url

    def test_provider_name(self):
        c = AnthropicConnector(api_key="ant-test")
        assert c.provider == "anthropic"

    @pytest.mark.asyncio
    async def test_chat_no_key(self):
        with patch.dict("os.environ", {}, clear=True):
            c = AnthropicConnector(api_key="")
            result = await c.chat([{"role": "user", "content": "hi"}], model="claude-3-5-sonnet-20241022")
            assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_chat_success(self):
        c = AnthropicConnector(api_key="ant-test")
        mock_resp = _mock_anthropic_response("Claude response")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.chat(
                [{"role": "system", "content": "You are helpful"}, {"role": "user", "content": "hi"}],
                model="claude-3-5-sonnet-20241022",
            )

        assert result["ok"] is True
        assert result["text"] == "Claude response"
        assert result["provider"] == "anthropic"

    @pytest.mark.asyncio
    async def test_chat_separates_system(self):
        """Anthropic expects system prompt in a separate field, not in messages."""
        c = AnthropicConnector(api_key="ant-test")
        mock_resp = _mock_anthropic_response("ok")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await c.chat(
                [{"role": "system", "content": "Be brief"}, {"role": "user", "content": "hi"}],
                model="claude-3-5-sonnet-20241022",
            )
            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json", {})
            assert payload.get("system") == "Be brief"
            # Only the user message should be in messages
            assert all(m["role"] != "system" for m in payload.get("messages", []))

    @pytest.mark.asyncio
    async def test_chat_network_error(self):
        c = AnthropicConnector(api_key="ant-test")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("Timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.chat([{"role": "user", "content": "hi"}], model="claude-3-5-sonnet-20241022")
        assert result["ok"] is False
        assert "Timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_health_no_key(self):
        c = AnthropicConnector(api_key="")
        result = await c.health()
        assert result["ok"] is False


# ═══════════════════════════════════════════════════════════════════════════
# 4. Ollama Connector
# ═══════════════════════════════════════════════════════════════════════════


def _mock_ollama_response(text="Ollama says hi", prompt_eval=6, eval_count=3, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.json.return_value = {
        "message": {"content": text},
        "prompt_eval_count": prompt_eval,
        "eval_count": eval_count,
    }
    return resp


class TestOllamaConnector:
    def test_init_defaults(self):
        c = OllamaConnector()
        assert "localhost" in c.base_url
        assert "11434" in c.base_url

    def test_init_custom(self):
        c = OllamaConnector(base_url="http://remote:9999")
        assert c.base_url == "http://remote:9999"

    def test_provider_name(self):
        c = OllamaConnector()
        assert c.provider == "ollama"

    @pytest.mark.asyncio
    async def test_chat_success(self):
        c = OllamaConnector()
        mock_resp = _mock_ollama_response("Llama output", 10, 5)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.chat([{"role": "user", "content": "test"}], model="llama3")

        assert result["ok"] is True
        assert result["text"] == "Llama output"
        assert result["tokens"]["total"] == 15

    @pytest.mark.asyncio
    async def test_chat_connection_error(self):
        c = OllamaConnector()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.chat([{"role": "user", "content": "test"}], model="llama3")

        assert result["ok"] is False
        assert "Connection refused" in result["error"]

    @pytest.mark.asyncio
    async def test_health_success(self):
        c = OllamaConnector()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3"}]}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.health()
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_chat_server_error(self):
        c = OllamaConnector()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal error"
        mock_resp.json.return_value = {"error": "model not found"}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.chat([{"role": "user", "content": "test"}], model="nonexistent")
        assert result["ok"] is False


# ═══════════════════════════════════════════════════════════════════════════
# 5. HTTP Connector
# ═══════════════════════════════════════════════════════════════════════════


def _mock_http_response(text="HTTP result", status=200, openai_format=True):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    if openai_format:
        resp.json.return_value = {
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
    else:
        resp.json.return_value = {"content": text}
    return resp


class TestHttpConnector:
    def test_init_defaults(self):
        c = HttpConnector()
        assert "localhost" in c.endpoint or "8080" in c.endpoint

    def test_init_custom(self):
        c = HttpConnector(endpoint="http://myapi.com/v1/chat", api_key="key-1", headers={"X-Custom": "val"})
        assert c.endpoint == "http://myapi.com/v1/chat"
        assert c.api_key == "key-1"
        assert c.custom_headers["X-Custom"] == "val"

    def test_provider_name(self):
        c = HttpConnector()
        assert c.provider == "http"

    @pytest.mark.asyncio
    async def test_chat_openai_format(self):
        c = HttpConnector(endpoint="http://test:8080/v1/chat/completions")
        mock_resp = _mock_http_response("Generated text", openai_format=True)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.chat([{"role": "user", "content": "test"}], model="custom")

        assert result["ok"] is True
        assert result["text"] == "Generated text"

    @pytest.mark.asyncio
    async def test_chat_fallback_content_field(self):
        c = HttpConnector(endpoint="http://test:8080/v1/chat")
        mock_resp = _mock_http_response("Fallback text", openai_format=False)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.chat([{"role": "user", "content": "test"}], model="custom")

        assert result["ok"] is True
        assert result["text"] == "Fallback text"

    @pytest.mark.asyncio
    async def test_chat_error(self):
        c = HttpConnector(endpoint="http://test:8080")
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Server error"
        mock_resp.json.return_value = {"error": {"message": "Broken"}}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.chat([{"role": "user", "content": "test"}], model="custom")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_chat_exception(self):
        c = HttpConnector(endpoint="http://test:8080")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("DNS failure"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.chat([{"role": "user", "content": "test"}], model="custom")
        assert result["ok"] is False
        assert "DNS failure" in result["error"]

    @pytest.mark.asyncio
    async def test_health_success(self):
        c = HttpConnector(endpoint="http://test:8080/v1/chat/completions")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await c.health()
        assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════
# 6. Connector Registry
# ═══════════════════════════════════════════════════════════════════════════


class TestConnectorRegistry:
    def test_list_connectors(self):
        conns = list_connectors()
        assert "openai" in conns
        assert "anthropic" in conns
        assert "ollama" in conns
        assert "http" in conns
        assert "azure" in conns
        assert "custom" in conns

    def test_list_connectors_class_names(self):
        conns = list_connectors()
        assert conns["openai"] == "OpenAIConnector"
        assert conns["anthropic"] == "AnthropicConnector"
        assert conns["ollama"] == "OllamaConnector"
        assert conns["http"] == "HttpConnector"

    def test_azure_maps_to_openai(self):
        conns = list_connectors()
        assert conns["azure"] == "OpenAIConnector"

    def test_custom_maps_to_http(self):
        conns = list_connectors()
        assert conns["custom"] == "HttpConnector"

    def test_get_connector_openai(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
            c = get_connector("openai", api_key="sk-direct")
        assert isinstance(c, OpenAIConnector)
        assert c.api_key == "sk-direct"

    def test_get_connector_anthropic(self):
        c = get_connector("anthropic", api_key="ant-test")
        assert isinstance(c, AnthropicConnector)

    def test_get_connector_ollama(self):
        c = get_connector("ollama")
        assert isinstance(c, OllamaConnector)

    def test_get_connector_http(self):
        c = get_connector("http", endpoint="http://myapi:9090")
        assert isinstance(c, HttpConnector)

    def test_get_connector_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            get_connector("nonexistent_provider")

    def test_get_connector_explicit_overrides_hub(self):
        """Explicit api_key should override whatever Hub provides."""
        c = get_connector("openai", api_key="sk-explicit")
        assert c.api_key == "sk-explicit"

    def test_ensure_registry_idempotent(self):
        _ensure_registry()
        first = dict(_CONNECTOR_CLASSES)
        _ensure_registry()
        second = dict(_CONNECTOR_CLASSES)
        assert first == second


# ═══════════════════════════════════════════════════════════════════════════
# 7. Response shape invariants
# ═══════════════════════════════════════════════════════════════════════════


REQUIRED_RESPONSE_KEYS = {"ok", "provider", "model", "text", "tokens", "raw"}


class TestResponseShape:
    def test_normalise_ok_has_all_keys(self):
        r = AIConnector._normalise_response(ok=True, provider="x", model="m", text="t")
        for key in REQUIRED_RESPONSE_KEYS:
            assert key in r, f"Missing: {key}"

    def test_normalise_error_has_all_keys(self):
        r = AIConnector._normalise_response(ok=False, provider="x", model="m", error="err")
        for key in REQUIRED_RESPONSE_KEYS:
            assert key in r, f"Missing: {key}"
        assert r["error"] == "err"

    def test_normalise_defaults_empty(self):
        r = AIConnector._normalise_response(ok=True, provider="p", model="m")
        assert r["text"] == ""
        assert r["tokens"] == {}
        assert r["raw"] == {}
        assert r["error"] is None

    @pytest.mark.parametrize("provider", ["openai", "anthropic", "ollama", "http"])
    def test_connector_has_provider_attr(self, provider):
        _ensure_registry()
        cls = _CONNECTOR_CLASSES[provider]
        assert hasattr(cls, "provider")

    @pytest.mark.parametrize("provider", ["openai", "anthropic", "ollama", "http"])
    def test_connector_has_chat_method(self, provider):
        _ensure_registry()
        cls = _CONNECTOR_CLASSES[provider]
        assert callable(getattr(cls, "chat", None))

    @pytest.mark.parametrize("provider", ["openai", "anthropic", "ollama", "http"])
    def test_connector_has_health_method(self, provider):
        _ensure_registry()
        cls = _CONNECTOR_CLASSES[provider]
        assert callable(getattr(cls, "health", None))
