"""
Tests for Harness Engineering Phase 1 (v0.5.43)

Covers:
- Conversational handler patterns (greet, identity, help)
- LLM freeform fallback with NO_PROVIDER sentinel
- _handle_conversational() unit tests
- _llm_freeform_fallback() unit tests
"""

from __future__ import annotations

import pytest


# =============================================================================
# TestConversationalPatterns — unit tests for _handle_conversational()
# =============================================================================


class TestConversationalPatterns:
    def test_greet_hi(self):
        from aksara.ai.console_engine import _handle_conversational

        result = _handle_conversational("hi", 0.0)
        assert result is not None
        assert result["ok"] is True
        assert result["intent"] == "greet"

    def test_greet_hello(self):
        from aksara.ai.console_engine import _handle_conversational

        result = _handle_conversational("Hello!", 0.0)
        assert result is not None
        assert result["intent"] == "greet"

    def test_greet_hey(self):
        from aksara.ai.console_engine import _handle_conversational

        result = _handle_conversational("hey there", 0.0)
        assert result is not None
        assert result["intent"] == "greet"

    def test_greet_howdy(self):
        from aksara.ai.console_engine import _handle_conversational

        result = _handle_conversational("Howdy", 0.0)
        assert result is not None
        assert result["intent"] == "greet"

    def test_greet_good_morning(self):
        from aksara.ai.console_engine import _handle_conversational

        result = _handle_conversational("Good morning", 0.0)
        assert result is not None
        assert result["intent"] == "greet"

    def test_identity_who_are_you(self):
        from aksara.ai.console_engine import _handle_conversational

        result = _handle_conversational("who are you?", 0.0)
        assert result is not None
        assert result["intent"] == "identity"

    def test_identity_what_are_you(self):
        from aksara.ai.console_engine import _handle_conversational

        result = _handle_conversational("what are you?", 0.0)
        assert result is not None
        assert result["intent"] == "identity"

    def test_identity_introduce_yourself(self):
        from aksara.ai.console_engine import _handle_conversational

        result = _handle_conversational("introduce yourself", 0.0)
        assert result is not None
        assert result["intent"] == "identity"

    def test_identity_what_can_you_do(self):
        from aksara.ai.console_engine import _handle_conversational

        result = _handle_conversational("what can you do", 0.0)
        assert result is not None
        assert result["intent"] == "identity"

    def test_help_bare(self):
        from aksara.ai.console_engine import _handle_conversational

        result = _handle_conversational("help", 0.0)
        assert result is not None
        assert result["intent"] == "help"

    def test_help_commands(self):
        from aksara.ai.console_engine import _handle_conversational

        result = _handle_conversational("commands", 0.0)
        assert result is not None
        assert result["intent"] == "help"

    def test_help_list_commands(self):
        from aksara.ai.console_engine import _handle_conversational

        result = _handle_conversational("list commands", 0.0)
        assert result is not None
        assert result["intent"] == "help"

    def test_no_match_returns_none(self):
        from aksara.ai.console_engine import _handle_conversational

        # A real structured query should not match conversational patterns
        assert _handle_conversational("explain the User model", 0.0) is None
        assert _handle_conversational("architecture review", 0.0) is None
        assert _handle_conversational("xyzzy foo bar", 0.0) is None

    def test_conversational_response_shape(self):
        """Conversational responses must include standard pipeline keys."""
        from aksara.ai.console_engine import _handle_conversational

        result = _handle_conversational("hi", 0.0)
        assert result is not None
        required_keys = {
            "ok", "intent", "flow_type", "action_key", "confidence",
            "extracted_context", "prompt_pack", "execution",
            "suggestions", "elapsed_ms", "error", "error_code", "conversational",
        }
        assert required_keys.issubset(result.keys())

    def test_conversational_flow_type(self):
        from aksara.ai.console_engine import _handle_conversational

        for msg in ("hi", "who are you?", "help"):
            result = _handle_conversational(msg, 0.0)
            assert result is not None
            assert result["flow_type"] == "conversational"
            assert result["conversational"] is True

    def test_help_text_content(self):
        """Help response must mention key command categories."""
        from aksara.ai.console_engine import _handle_conversational

        result = _handle_conversational("help", 0.0)
        assert result is not None
        text = result["execution"]["response"]
        assert "explain" in text.lower()
        assert "architecture" in text.lower()
        assert "investigate" in text.lower()


# =============================================================================
# TestConversationalIntegration — run_console_query() end-to-end
# =============================================================================


class TestConversationalIntegration:
    @pytest.mark.asyncio
    async def test_run_greet(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("hi")
        assert result["ok"] is True
        assert result["intent"] == "greet"
        assert result["flow_type"] == "conversational"
        assert result["conversational"] is True

    @pytest.mark.asyncio
    async def test_run_hello(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("Hello!")
        assert result["ok"] is True
        assert result["intent"] == "greet"

    @pytest.mark.asyncio
    async def test_run_who_are_you(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("who are you?")
        assert result["ok"] is True
        assert result["intent"] == "identity"

    @pytest.mark.asyncio
    async def test_run_what_can_you_do(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("what can you do")
        assert result["ok"] is True
        assert result["intent"] == "identity"

    @pytest.mark.asyncio
    async def test_run_help(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("help")
        assert result["ok"] is True
        assert result["intent"] == "help"
        response = result["execution"]["response"]
        assert "Available Commands" in response

    @pytest.mark.asyncio
    async def test_run_commands(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("commands")
        assert result["ok"] is True
        assert result["intent"] == "help"


# =============================================================================
# TestFreeformFallback — _llm_freeform_fallback() unit tests
# =============================================================================


from unittest.mock import patch, PropertyMock

class TestFreeformFallback:
    @pytest.fixture(autouse=True)
    def _mock_unconfigured(self):
        with patch("aksara.ai.hub_settings.ProviderConfig.is_configured", new_callable=PropertyMock, return_value=False):
            yield

    def test_no_provider_returns_error(self):
        """Without an AI provider configured, freeform returns NO_PROVIDER."""
        from aksara.ai.console_engine import _llm_freeform_fallback

        result = _llm_freeform_fallback("xyzzy plugh nothing", None, None, 0.0)
        assert result["ok"] is False
        assert result["error_code"] == "NO_PROVIDER"

    def test_no_provider_includes_message_in_error(self):
        from aksara.ai.console_engine import _llm_freeform_fallback

        msg = "tell me about zork adventures"
        result = _llm_freeform_fallback(msg, None, None, 0.0)
        assert result["ok"] is False
        assert msg in result["error"]

    def test_no_provider_suggests_env_vars(self):
        """NO_PROVIDER error text must mention how to configure a provider."""
        from aksara.ai.console_engine import _llm_freeform_fallback

        result = _llm_freeform_fallback("foo bar", None, None, 0.0)
        error_text = result["error"]
        # At least one env var hint should appear
        assert any(
            hint in error_text
            for hint in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OLLAMA_BASE_URL")
        )

    def test_freeform_fallback_respects_auto_routing(self):
        """Freeform fallback should use effective chat provider and not execute against disabled providers."""
        from aksara.ai.console_engine import _llm_freeform_fallback
        from aksara.ai.hub_settings import load_aihub_settings

        hub = load_aihub_settings()
        
        for p in hub.providers:
            p.enabled = False
            
        anthropic_pc = hub.get_provider("anthropic")
        anthropic_pc.enabled = True
        
        hub.defaults.chat_provider = None  # auto-routing
        hub.active_provider = "openai"     # Legacy active_provider that should be ignored
        
        with patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            with patch("aksara.ai.hub_settings.ProviderConfig.is_configured", new_callable=PropertyMock, return_value=True):
                with patch("aksara.ai.providers_unified.UnifiedAiProvider.is_configured", return_value=True):
                    
                    def mock_get_llm_client(unified_self):
                        assert unified_self.provider == "anthropic"
                        from unittest.mock import MagicMock
                        m = MagicMock()
                        m.generate.return_value = "Mock Response"
                        return m
                        
                    with patch("aksara.ai.providers_unified.UnifiedAiProvider.get_llm_client", autospec=True, side_effect=mock_get_llm_client):
                        result = _llm_freeform_fallback("test message", None, None, 0.0)
                        
                        assert result["ok"] is True

    def test_freeform_result_shape(self):
        """NO_PROVIDER response must include all standard pipeline keys."""
        from aksara.ai.console_engine import _llm_freeform_fallback

        result = _llm_freeform_fallback("something weird", None, None, 0.0)
        required_keys = {
            "ok", "intent", "confidence", "error", "error_code",
            "elapsed_ms",
        }
        assert required_keys.issubset(result.keys())


# =============================================================================
# TestFreeformFallbackIntegration — run_console_query() with gibberish input
# =============================================================================


class TestFreeformFallbackIntegration:
    @pytest.fixture(autouse=True)
    def _mock_unconfigured(self):
        with patch("aksara.ai.hub_settings.ProviderConfig.is_configured", new_callable=PropertyMock, return_value=False):
            yield

    @pytest.mark.asyncio
    async def test_unknown_input_no_provider(self):
        """Gibberish that matches no intent returns NO_PROVIDER (not UNKNOWN_INTENT)."""
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("xyzzy foo bar baz")
        assert result["ok"] is False
        assert result["error_code"] == "NO_PROVIDER"

    @pytest.mark.asyncio
    async def test_unknown_input_error_code_not_unknown_intent(self):
        """UNKNOWN_INTENT error code must no longer be produced."""
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("zzz totally random gibberish plugh 12345")
        assert result.get("error_code") != "UNKNOWN_INTENT"

    @pytest.mark.asyncio
    async def test_unknown_input_error_message_helpful(self):
        """NO_PROVIDER error message must include actionable guidance."""
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("frobulate the quux")
        assert result["ok"] is False
        error_text = result.get("error", "")
        assert any(
            phrase in error_text
            for phrase in ("explain", "architecture", "investigate", "help")
        )
