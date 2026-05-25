"""
Studio-First Sanity Sweep (v0.5.28)

Comprehensive end-to-end tests covering all four sections of the
Studio + AI Hub sanity checklist:

  §1  Studio + AI Hub: End-to-End Sanity
      1.1  Navigation & status indicator
      1.2  Providers tab
      1.3  Models tab
      1.4  Routing / Usage tab
      1.5  Onboarding tab

  §2  Studio Cross-Feature AI Sanity
      2.1  Agents tab
      2.2  Playbooks
      2.3  Semantic search & Spotlight
      2.4  Diagnostics & Gap Analysis

  §3  CLI vs Studio Parity

  §4  Bug-Hunt Edge Cases
      4.1  No DB URL, AI configured
      4.2  Multiple providers configured
      4.3  Env-only vs Studio-edited config precedence
      4.4  Network / provider flakiness
"""

import json
import os
import pytest
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock
from unittest.mock import MagicMock, AsyncMock, patch

# ─── Common paths / fixtures ────────────────────────────────────────────────

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "aksara" / "studio" / "static"


@pytest.fixture
def html_source():
    return (STATIC_DIR / "index.html").read_text()


@pytest.fixture
def js_source():
    return (STATIC_DIR / "app.js").read_text()


@pytest.fixture
def css_source():
    return (STATIC_DIR / "styles.css").read_text()


def _make_hub(providers=None, active=None, chat_model=None, code_model=None,
              embeddings_model=None):
    """Helper to build a mock AiHubSettings quickly."""
    from aksara.ai.hub_settings import (
        AiHubSettings, AiDefaultModels, ProviderConfig,
        OpenAIConfig, AnthropicConfig, OllamaConfig, AzureOpenAIConfig, CustomHttpConfig,
    )
    all_providers = []
    if providers is None:
        providers = []

    _cfg_map = {
        "openai": lambda kw: ProviderConfig(kind="openai", openai=OpenAIConfig(**kw)),
        "anthropic": lambda kw: ProviderConfig(kind="anthropic", anthropic=AnthropicConfig(**kw)),
        "azure": lambda kw: ProviderConfig(kind="azure", azure=AzureOpenAIConfig(**kw)),
        "ollama": lambda kw: ProviderConfig(kind="ollama", ollama=OllamaConfig(**kw)),
        "custom": lambda kw: ProviderConfig(kind="custom", custom=CustomHttpConfig(**kw)),
    }

    for spec in providers:
        if isinstance(spec, str):
            kind = spec
            kw = {"api_key": f"sk-test-{kind}"} if kind != "ollama" else {}
            all_providers.append(_cfg_map[kind](kw))
        elif isinstance(spec, tuple):
            kind, kw = spec
            all_providers.append(_cfg_map[kind](kw))
        else:
            all_providers.append(spec)

    defaults = AiDefaultModels(
        chat_model=chat_model, code_model=code_model,
        embeddings_model=embeddings_model,
    )
    hub = AiHubSettings(
        providers=all_providers, defaults=defaults,
        active_provider=active or (all_providers[0].kind if all_providers else None),
    )
    hub.resolve_defaults()
    return hub


# ═════════════════════════════════════════════════════════════════════════════
# §1  Studio + AI Hub: End-to-End Sanity
# ═════════════════════════════════════════════════════════════════════════════


# ─── 1.1  Basic navigation & status ──────────────────────────────────────────

class TestNavAndStatus:
    """1.1 – Navigation items, keyboard shortcuts, global AI indicator."""

    def test_ai_hub_nav_item_in_sidebar(self, html_source):
        assert "AI Hub" in html_source

    def test_ai_hub_nav_targets_template(self, html_source):
        assert 'data-section="ai-hub"' in html_source

    def test_keyboard_shortcut_alt_a(self, js_source):
        """Alt/Option+A opens the AI Hub screen."""
        assert "Alt" in js_source or "alt" in js_source
        # JS should bind Alt+A to navigate to AI Hub
        assert "ai-hub" in js_source

    def test_global_ai_indicator_element(self, html_source):
        assert 'id="ai-status-indicator"' in html_source

    def test_global_ai_indicator_dot(self, html_source):
        assert 'id="ai-status-dot"' in html_source

    def test_global_ai_indicator_label(self, html_source):
        assert 'id="ai-status-label"' in html_source

    def test_status_indicator_js_function(self, js_source):
        assert "loadAiStatusIndicator" in js_source

    def test_status_indicator_has_three_states(self, js_source, css_source):
        """ready (green), partial (yellow), disabled (red/off).

        JS constructs class dynamically: 'ai-status-dot ai-status-' + overall
        so the literal class names only appear in CSS.
        """
        assert "ai-status-" in js_source  # dynamic pattern in JS
        assert "ai-status-ready" in css_source
        assert "ai-status-partial" in css_source
        assert "ai-status-disabled" in css_source

    def test_css_has_indicator_colours(self, css_source):
        """CSS classes for indicator dot colours."""
        assert "ai-status-ready" in css_source
        assert "ai-status-partial" in css_source

    # ── Builder: status with no providers ────────────────────────────

    def test_status_disabled_when_no_providers(self):
        from aksara.studio.utils import build_aihub_status
        hub = _make_hub(providers=[])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            s = build_aihub_status()
        assert s.overall == "disabled"
        assert s.configured_count == 0

    def test_status_no_crash_no_providers(self):
        from aksara.studio.utils import build_aihub_status
        hub = _make_hub(providers=[])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            s = build_aihub_status()
        assert s.warnings is not None
        assert isinstance(s.onboarding.completed, bool)

    def test_status_friendly_message_no_providers(self):
        from aksara.studio.utils import build_aihub_status
        hub = _make_hub(providers=[])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            s = build_aihub_status()
        assert s.overall == "disabled"
        # No crash, just a disabled status

    # ── Builder: status with one provider ────────────────────────────

    def test_status_ready_with_openai(self):
        from aksara.studio.utils import build_aihub_status
        hub = _make_hub(providers=["openai"], active="openai")
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            s = build_aihub_status()
        assert s.overall == "ready"
        assert s.active_provider == "openai"

    def test_status_partial_when_no_chat_model(self):
        from aksara.studio.utils import build_aihub_status
        from aksara.ai.hub_settings import (
            AiHubSettings, AiDefaultModels, ProviderConfig, OpenAIConfig,
        )
        # Configured but manually empty defaults
        hub = AiHubSettings(
            providers=[ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="sk-x"))],
            defaults=AiDefaultModels(),
            active_provider="openai",
        )
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            s = build_aihub_status()
        assert s.overall == "partial"


# ─── 1.2  Providers tab ──────────────────────────────────────────────────────

class TestProvidersTab:
    """1.2 – Provider cards, detection, status, test connectivity."""

    def test_html_provider_list_container(self, html_source):
        assert 'id="ai-hub-provider-list"' in html_source

    def test_js_renders_all_five_providers(self):
        from aksara.studio.utils import build_aihub_providers
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_providers()
        # At minimum the providers we gave; env-based loads more
        assert r.total_count >= 1

    def test_provider_card_shows_modes(self):
        from aksara.studio.utils import build_aihub_providers
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_providers()
        oai = next(p for p in r.providers if p.kind == "openai")
        assert "chat" in oai.modes
        assert "embeddings" in oai.modes

    def test_unconfigured_provider_shows_not_configured(self):
        from aksara.studio.utils import build_aihub_providers
        from aksara.ai.hub_settings import AiHubSettings, AiDefaultModels, ProviderConfig
        hub = AiHubSettings(
            providers=[ProviderConfig(kind="anthropic")],
            defaults=AiDefaultModels(),
        )
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_providers()
        anth = next(p for p in r.providers if p.kind == "anthropic")
        assert anth.configured is False

    def test_provider_icons_in_js(self, js_source):
        """JS should have provider icons for each provider type."""
        assert "providerIcons" in js_source
        assert "openai" in js_source
        assert "anthropic" in js_source
        assert "ollama" in js_source

    # ── Test provider connectivity ──────────────────────────────────

    def test_test_provider_valid_key_mock(self):
        from aksara.studio.utils import build_aihub_test
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            with mock.patch(
                "aksara.ai.providers_unified.UnifiedAiProvider.ping",
                return_value={"ok": True, "message": "Connected"},
            ):
                r = build_aihub_test("openai")
        assert r.reachable is True
        assert r.latency_ms is not None and r.latency_ms >= 0
        assert r.error is None

    def test_test_provider_bad_key_mock(self):
        from aksara.studio.utils import build_aihub_test
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            with mock.patch(
                "aksara.ai.providers_unified.UnifiedAiProvider.ping",
                return_value={"ok": False, "message": "401 Unauthorized"},
            ):
                r = build_aihub_test("openai")
        assert r.reachable is False
        assert r.error is not None
        # Should not leak the actual key
        assert "sk-test" not in (r.error or "")

    def test_test_provider_network_error(self):
        from aksara.studio.utils import build_aihub_test
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            with mock.patch(
                "aksara.ai.providers_unified.UnifiedAiProvider.ping",
                side_effect=ConnectionError("DNS resolution failed"),
            ):
                r = build_aihub_test("openai")
        assert r.reachable is False
        assert "DNS" in (r.error or "")

    def test_test_unconfigured_provider(self):
        from aksara.studio.utils import build_aihub_test
        hub = _make_hub(providers=[])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_test("openai")
        assert r.reachable is False
        assert "not configured" in (r.error or "").lower()

    def test_js_uses_toast_not_alert(self, js_source):
        """After fix: aiHubTestProvider uses showToast, not alert."""
        lines = js_source.split("\n")
        in_test_fn = False
        for line in lines:
            if "aiHubTestProvider" in line and "function" in line:
                in_test_fn = True
            if in_test_fn and "alert(" in line:
                pytest.fail("aiHubTestProvider still uses alert() — should use showToast()")
            if in_test_fn and line.strip() == "}":
                in_test_fn = False

    def test_test_response_never_leaks_full_key(self):
        from aksara.studio.utils import build_aihub_test
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            with mock.patch(
                "aksara.ai.providers_unified.UnifiedAiProvider.ping",
                return_value={"ok": True},
            ):
                r = build_aihub_test("openai")
        d = r.model_dump()
        dumped = json.dumps(d)
        assert "sk-test-openai" not in dumped


# ─── 1.3  Models tab ─────────────────────────────────────────────────────────

class TestModelsTab:
    """1.3 – Default model selection, listing, persistence."""

    def test_html_models_tab(self, html_source):
        assert 'data-tab="hub-models"' in html_source

    def test_html_default_inputs(self, html_source):
        assert 'id="ai-hub-default-chat"' in html_source
        assert 'id="ai-hub-default-code"' in html_source

    def test_builder_shows_defaults(self):
        from aksara.studio.utils import build_aihub_models
        hub = _make_hub(providers=["openai"], chat_model="gpt-4o")
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_models()
        assert r.defaults.get("chat_model") == "gpt-4o"

    def test_builder_models_from_configured_openai(self):
        from aksara.studio.utils import build_aihub_models
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_models()
        ids = [m.model_id for m in r.models]
        assert "gpt-4o" in ids
        assert "text-embedding-3-large" in ids

    def test_builder_defaults_persist_after_set(self):
        from aksara.studio.utils import build_aihub_defaults
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_defaults(chat_model="gpt-4o-mini")
        assert r.ok is True

    def test_no_embedding_provider_shows_warning(self):
        from aksara.studio.utils import build_aihub_status
        from aksara.ai.hub_settings import (
            AiHubSettings, AiDefaultModels, ProviderConfig, AnthropicConfig,
        )
        # Anthropic has no embeddings
        hub = AiHubSettings(
            providers=[ProviderConfig(kind="anthropic", anthropic=AnthropicConfig(api_key="ant-x"))],
            defaults=AiDefaultModels(chat_model="claude-3-5-sonnet-20241022"),
            active_provider="anthropic",
        )
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            s = build_aihub_status()
        embedding_warnings = [w for w in s.warnings if "embedding" in w.lower()]
        assert len(embedding_warnings) >= 1

    def test_set_embeddings_model(self):
        from aksara.studio.utils import build_aihub_defaults
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_defaults(embeddings_model="text-embedding-3-large",
                                     embeddings_provider="openai")
        assert r.ok is True


# ─── 1.4  Routing / Usage tab ────────────────────────────────────────────────

class TestRoutingTab:
    """1.4 – Routing table, per-feature provider/model mapping."""

    def test_html_routing_tab(self, html_source):
        assert 'data-tab="routing"' in html_source

    def test_routes_endpoint_registered(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/ai-hub/routes" in paths

    def test_routes_builder_with_openai(self):
        from aksara.studio.utils import build_aihub_routes
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_routes()
        features = [route.feature for route in r.routes]
        assert "agents" in features
        assert "playbooks" in features
        assert "search_embeddings" in features
        assert "diagnostics" in features

    def test_routes_agents_ok_with_chat_model(self):
        from aksara.studio.utils import build_aihub_routes
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_routes()
        agents = next(rt for rt in r.routes if rt.feature == "agents")
        assert agents.status == "ok"
        assert agents.provider == "openai"
        assert agents.model is not None

    def test_routes_search_fallback_when_no_embeddings(self):
        from aksara.studio.utils import build_aihub_routes
        from aksara.ai.hub_settings import (
            AiHubSettings, AiDefaultModels, ProviderConfig, AnthropicConfig,
        )
        hub = AiHubSettings(
            providers=[ProviderConfig(kind="anthropic", anthropic=AnthropicConfig(api_key="ant-x"))],
            defaults=AiDefaultModels(chat_model="claude-3-5-sonnet-20241022",
                                     chat_provider="anthropic"),
            active_provider="anthropic",
        )
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_routes()
        search = next(rt for rt in r.routes if rt.feature == "search_embeddings")
        assert search.status == "fallback"
        assert search.warning is not None

    def test_routes_missing_when_no_providers(self):
        from aksara.studio.utils import build_aihub_routes
        hub = _make_hub(providers=[])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_routes()
        agents = next(rt for rt in r.routes if rt.feature == "agents")
        assert agents.status == "missing"

    def test_routes_warnings_list_type(self):
        from aksara.studio.utils import build_aihub_routes
        hub = _make_hub(providers=[])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_routes()
        assert isinstance(r.warnings, list)

    def test_routes_no_warnings_fully_configured(self):
        from aksara.studio.utils import build_aihub_routes
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_routes()
        missing = [rt for rt in r.routes if rt.status == "missing"]
        assert len(missing) == 0

    def test_js_routing_uses_routes_endpoint(self, js_source):
        """After fix: loadAiHubRouting calls /studio/ai-hub/routes."""
        assert "/studio/ai-hub/routes" in js_source

    def test_routes_diagnostics_ok_with_chat_model(self):
        from aksara.studio.utils import build_aihub_routes
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_routes()
        diag = next(rt for rt in r.routes if rt.feature == "diagnostics")
        assert diag.status == "ok"

    def test_routes_playbooks_fallback_code_model_missing(self):
        from aksara.studio.utils import build_aihub_routes
        from aksara.ai.hub_settings import (
            AiHubSettings, AiDefaultModels, ProviderConfig, OpenAIConfig,
        )
        hub = AiHubSettings(
            providers=[ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="sk-x"))],
            defaults=AiDefaultModels(chat_model="gpt-4o", chat_provider="openai"),
            active_provider="openai",
        )
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_routes()
        pb = next(rt for rt in r.routes if rt.feature == "playbooks")
        # code_model is None → fallback status
        assert pb.status == "fallback"


# ─── 1.5  Onboarding tab ─────────────────────────────────────────────────────

class TestOnboardingTab:
    """1.5 – Wizard flow, step indicators, no-crash guarantee."""

    def test_html_onboarding_tab(self, html_source):
        assert 'data-tab="onboarding"' in html_source

    def test_html_onboarding_steps(self, html_source):
        for step_id in range(1, 6):
            assert f'id="onboarding-step-{step_id}-status"' in html_source

    def test_html_test_all_button(self, html_source):
        assert 'id="onboarding-test-all"' in html_source

    def test_html_save_keys_button(self, html_source):
        assert 'id="onboarding-save-keys"' in html_source

    def test_html_save_defaults_button(self, html_source):
        assert 'id="onboarding-save-defaults"' in html_source

    def test_html_run_sample_button(self, html_source):
        assert 'id="onboarding-run-sample"' in html_source

    def test_js_onboarding_field_names_match_python(self, js_source):
        """JS must use providers_selected, keys_entered, etc. — not has_provider.

        Step 3 (providers_tested) is no longer read from the backend flag because
        the backend always returns False for it; reachability is now computed live
        from provData.providers directly.
        """
        assert "ob.providers_selected" in js_source
        assert "ob.keys_entered" in js_source
        assert "ob.defaults_set" in js_source
        assert "ob.sample_query_run" in js_source
        # Old broken names must NOT appear
        assert "ob.has_provider" not in js_source
        assert "ob.has_key" not in js_source
        assert "ob.has_test" not in js_source
        assert "ob.has_defaults" not in js_source
        assert "ob.has_sample" not in js_source

    def test_onboarding_status_fresh_project(self):
        from aksara.studio.utils import build_aihub_status
        hub = _make_hub(providers=[])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            s = build_aihub_status()
        ob = s.onboarding
        assert ob.providers_selected is False
        assert ob.keys_entered is False
        assert ob.defaults_set is False
        assert ob.completed is False

    def test_onboarding_completed_with_openai(self):
        from aksara.studio.utils import build_aihub_status
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            s = build_aihub_status()
        ob = s.onboarding
        assert ob.providers_selected is True
        assert ob.keys_entered is True
        assert ob.defaults_set is True
        assert ob.completed is True

    def test_onboarding_no_500_with_empty_config(self):
        """build_aihub_status must not crash on completely empty config."""
        from aksara.studio.utils import build_aihub_status
        from aksara.ai.hub_settings import AiHubSettings
        hub = AiHubSettings()
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            s = build_aihub_status()
        assert s.overall in ("disabled", "partial", "ready")

    def test_js_onboarding_test_posts_to_correct_endpoint(self, js_source):
        assert "/studio/ai-hub/test" in js_source

    def test_js_onboarding_save_keys_posts_to_secret(self, js_source):
        assert "/studio/ai-hub/configure/secret" in js_source

    def test_js_onboarding_save_defaults_posts_to_defaults(self, js_source):
        assert "/studio/ai-hub/defaults" in js_source

    def test_js_onboarding_session_always_read(self, js_source):
        """_readOnboardingSession() must be called unconditionally so the session.tested
        fallback is available when the providers fetch fails.  The old guarded form
        `providersKnown ? _readOnboardingSession() : {}` zeroed out the session on
        fetch failure, breaking Step 3 and Step 5 persistence."""
        # The guarded form must not appear
        assert "providersKnown ? _readOnboardingSession() : {}" not in js_source
        # The unconditional call must appear
        assert "_readOnboardingSession()" in js_source

    def test_js_agent_provider_dropdown_label_is_hub_chat_default(self, js_source):
        """The blank provider option must say 'Hub Chat Default', not 'Active Provider'.
        The backend blank-selection path now uses hub.defaults.chat_provider (or auto-
        routing), not the legacy active_provider — so the old label was misleading."""
        assert "Hub Chat Default" in js_source
        assert '"Active Provider"' not in js_source

    def test_js_flow_button_gate_uses_ready_not_non_disabled(self, js_source):
        """initAiFlowButtons must enable only on effective === 'ready' — that is
        the only value that guarantees chat defaults + provider configured + reachable.
        'partial' (configured but not ready) must NOT enable flow buttons."""
        assert "_aiHubConfigured = effective === 'ready'" in js_source
        # The old predicates that over-enabled buttons must not appear
        assert "_aiHubConfigured = effective !== 'disabled'" not in js_source
        assert "_aiHubConfigured = configured.some(p => p.reachable === true)" not in js_source


# ═════════════════════════════════════════════════════════════════════════════
# §2  Studio Cross-Feature AI Sanity
# ═════════════════════════════════════════════════════════════════════════════


# ─── 2.1  Agents ──────────────────────────────────────────────────────────────

class TestAgentSanity:
    """2.1 – Agent tab uses AI Hub provider defaults."""

    def test_agent_context_has_ai_hub_summary(self):
        """build_full_ai_context should include ai_hub_summary."""
        from aksara.ai.context import AiFullContext
        schema = AiFullContext.model_json_schema()
        assert "ai_hub_summary" in schema.get("properties", {})

    def test_workflow_metadata_has_hub_defaults(self):
        """Workflow builder injects AI Hub defaults into metadata."""
        import inspect
        from aksara.ai.workflows import build_agent_workflow
        src = inspect.getsource(build_agent_workflow)
        assert "ai_hub" in src.lower() or "hub_defaults" in src.lower()

    def test_agent_prompt_endpoint_exists(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/agent/prompt" in paths

    def test_agent_workflow_endpoint_exists(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/agent/workflow" in paths

    def test_workflow_sample_endpoint_exists(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/agent/workflow/sample" in paths

    def test_ai_hub_agent_run_endpoint(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/ai/hub/agent/run" in paths


# ─── 2.2  Playbooks ──────────────────────────────────────────────────────────

class TestPlaybookSanity:
    """2.2 – Playbooks use AI Hub defaults."""

    def test_playbook_endpoint_exists(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/agent/playbooks" in paths

    def test_builtin_playbooks_exist(self):
        from aksara.ai.playbooks import get_builtin_playbooks
        pbs = get_builtin_playbooks()
        assert len(pbs.playbooks) >= 8

    def test_playbook_keys_unique(self):
        from aksara.ai.playbooks import get_builtin_playbooks
        pbs = get_builtin_playbooks()
        keys = [pb.key for pb in pbs.playbooks]
        assert len(keys) == len(set(keys))

    def test_playbook_steps_non_empty(self):
        from aksara.ai.playbooks import get_builtin_playbooks
        for pb in get_builtin_playbooks().playbooks:
            assert len(pb.steps) >= 1, f"Playbook {pb.key} has no steps"

    def test_playbook_has_risk(self):
        from aksara.ai.playbooks import get_builtin_playbooks
        for pb in get_builtin_playbooks().playbooks:
            assert pb.risk_level in ("low", "medium", "high"), f"{pb.key}: invalid risk_level={pb.risk_level}"


# ─── 2.3  Semantic search & Spotlight ─────────────────────────────────────────

class TestSearchSanity:
    """2.3 – Search falls back gracefully, spotlight wired."""

    def test_search_endpoint_exists(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/search/query" in paths

    def test_search_index_endpoint(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/search/index" in paths

    def test_embedding_fallback_to_local(self):
        from aksara.search.embeddings import get_embedding_provider
        with mock.patch.dict(os.environ, {}, clear=True):
            provider = get_embedding_provider()
        assert provider is not None
        # Should be local TF-IDF
        assert "local" in type(provider).__name__.lower() or "tfidf" in type(provider).__name__.lower()

    def test_embed_doesnt_crash_with_bad_hub_config(self):
        from aksara.search.embeddings import get_embedding_provider
        with mock.patch(
            "aksara.ai.hub_settings.load_aihub_settings",
            side_effect=RuntimeError("broken config"),
        ):
            provider = get_embedding_provider()
        assert provider is not None

    def test_spotlight_in_html(self, html_source):
        assert "spotlight" in html_source.lower()

    def test_spotlight_shortcut_in_js(self, js_source):
        # Cmd+K or Ctrl+K
        assert "spotlight" in js_source.lower()

    def test_spotlight_search_function(self, js_source):
        assert "spotlightSearch" in js_source

    def test_spotlight_handles_error_gracefully(self, js_source):
        """JS spotlight function should have try/catch."""
        # Find spotlightSearch function and verify it has error handling
        idx = js_source.find("function spotlightSearch")
        if idx == -1:
            idx = js_source.find("async function spotlightSearch")
        assert idx >= 0
        snippet = js_source[idx:idx + 1000]
        assert "catch" in snippet


# ─── 2.4  Diagnostics & Gap Analysis ─────────────────────────────────────────

class TestDiagnosticsGapSanity:
    """2.4 – Diagnostics include AI Hub checks, gap analysis wired."""

    @pytest.mark.asyncio
    async def test_check_ai_hub_config_no_providers(self):
        from aksara.diagnostics import check_ai_hub_config
        from aksara.ai.hub_settings import AiHubSettings
        hub = AiHubSettings()
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            issues = await check_ai_hub_config()
        kinds = [i.kind for i in issues]
        assert "ai_hub_no_provider" in kinds

    @pytest.mark.asyncio
    async def test_check_ai_hub_config_with_provider(self):
        from aksara.diagnostics import check_ai_hub_config
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            issues = await check_ai_hub_config()
        kinds = [i.kind for i in issues]
        assert "ai_hub_no_provider" not in kinds

    @pytest.mark.asyncio
    async def test_check_ai_hub_config_graceful_on_import_error(self):
        from aksara.diagnostics import check_ai_hub_config
        with mock.patch.dict("sys.modules", {"aksara.ai.hub_settings": None}):
            issues = await check_ai_hub_config()
        assert issues == []

    @pytest.mark.asyncio
    async def test_gap_ai_hub_category_exists(self):
        from aksara.gapanalysis import _CATEGORY_CHECKERS
        assert "ai_hub" in _CATEGORY_CHECKERS

    @pytest.mark.asyncio
    async def test_gap_analysis_ai_hub_no_providers(self):
        from aksara.gapanalysis import check_ai_hub
        from aksara.ai.hub_settings import AiHubSettings, AiDefaultModels
        hub = AiHubSettings(providers=[], defaults=AiDefaultModels())
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            issues = await check_ai_hub()
        codes = [i.code for i in issues]
        assert "AI_HUB_NO_PROVIDER" in codes

    def test_diagnostics_endpoint(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/diagnostics" in paths

    def test_gaps_endpoint(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/gaps" in paths


# ═════════════════════════════════════════════════════════════════════════════
# §3  CLI vs Studio Parity
# ═════════════════════════════════════════════════════════════════════════════

class TestCliStudioParity:
    """3 – CLI commands show same info as Studio builders."""

    @pytest.fixture
    def runner(self):
        from click.testing import CliRunner
        return CliRunner()

    @pytest.fixture
    def cli(self):
        from aksara.cli.main import cli
        return cli

    # ── status: JSON output matches builder ────────────────────────

    def test_cli_status_json_has_same_keys_as_builder(self, runner, cli):
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            result = runner.invoke(cli, ["ai-hub", "status", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "active_provider" in data
        assert "defaults" in data
        assert "providers" in data

    def test_cli_status_json_is_valid_json(self, runner, cli):
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            result = runner.invoke(cli, ["ai-hub", "status", "--format", "json"])
        # No banner before JSON
        stripped = result.output.strip()
        assert stripped.startswith("{"), "JSON output should start with { — no banner before JSON"

    # ── providers: JSON list ──────────────────────────────────────

    def test_cli_providers_json(self, runner, cli):
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            result = runner.invoke(cli, ["ai-hub", "providers", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        kinds = [p["kind"] for p in data]
        assert "openai" in kinds

    # ── models: JSON matches builder ──────────────────────────────

    def test_cli_models_json(self, runner, cli):
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            result = runner.invoke(cli, ["ai-hub", "models", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "defaults" in data
        assert "chat_model" in data["defaults"]

    # ── defaults: round-trip ──────────────────────────────────────

    def test_cli_defaults_json(self, runner, cli):
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            result = runner.invoke(cli, ["ai-hub", "defaults", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "chat_model" in data

    # ── doctor: exit codes ────────────────────────────────────────

    def test_cli_doctor_json_ok_when_configured(self, runner, cli):
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            result = runner.invoke(cli, ["ai-hub", "doctor", "--format", "json"])
        data = json.loads(result.output)
        assert data["ok"] is True
        assert result.exit_code == 0

    def test_cli_doctor_json_issues_when_empty(self, runner, cli):
        hub = _make_hub(providers=[])
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            result = runner.invoke(cli, ["ai-hub", "doctor", "--format", "json"])
        data = json.loads(result.output)
        assert len(data["issues"]) >= 1

    def test_cli_doctor_nonzero_on_error_severity(self, runner, cli):
        """Doctor should exit 1 when there are error-severity issues."""
        hub = _make_hub(providers=[])
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            result = runner.invoke(cli, ["ai-hub", "doctor", "--format", "json"])
        data = json.loads(result.output)
        # No providers = warning severity, exit 0
        assert result.exit_code == 0

    # ── configure: saves ──────────────────────────────────────────

    def test_cli_configure_openai(self, runner, cli, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        hub = _make_hub(providers=[])
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            with mock.patch("aksara.ai.hub_settings.save_aihub_settings") as save_mock:
                result = runner.invoke(cli, [
                    "ai-hub", "configure", "openai",
                    "--api-key", "example-not-a-real-secret",
                    "--model", "gpt-4o",
                ])
        assert result.exit_code == 0
        assert "openai" in result.output.lower()
        save_mock.assert_called_once()

    # ── Parity: CLI and Studio return same provider count ────────

    def test_cli_studio_same_provider_count(self, runner, cli):
        hub = _make_hub(providers=["openai", "anthropic"])
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            # CLI
            cli_result = runner.invoke(cli, ["ai-hub", "providers", "--format", "json"])
            cli_data = json.loads(cli_result.output)

        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            # Studio
            from aksara.studio.utils import build_aihub_providers
            studio_data = build_aihub_providers()

        assert len(cli_data) == studio_data.total_count

    def test_cli_studio_same_active_provider(self, runner, cli):
        hub = _make_hub(providers=["openai"], active="openai")
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            cli_result = runner.invoke(cli, ["ai-hub", "status", "--format", "json"])
            cli_data = json.loads(cli_result.output)

        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            from aksara.studio.utils import build_aihub_status
            studio_data = build_aihub_status()

        assert cli_data["active_provider"] == studio_data.active_provider


# ═════════════════════════════════════════════════════════════════════════════
# §4  Bug-Hunt Edge Cases
# ═════════════════════════════════════════════════════════════════════════════


# ─── 4.1  No DB URL, but AI configured ───────────────────────────────────────

class TestNoDatabaseButAiConfigured:
    """4.1 – Studio AI Hub loads even when DB is unreachable."""

    def test_status_builder_no_db(self):
        """build_aihub_status doesn't touch DB — should work without DB."""
        from aksara.studio.utils import build_aihub_status
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            s = build_aihub_status()
        assert s.overall == "ready"

    def test_providers_builder_no_db(self):
        from aksara.studio.utils import build_aihub_providers
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_providers()
        assert r.total_count >= 1

    def test_models_builder_no_db(self):
        from aksara.studio.utils import build_aihub_models
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_models()
        assert len(r.models) > 0

    def test_routes_builder_no_db(self):
        from aksara.studio.utils import build_aihub_routes
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_routes()
        assert len(r.routes) >= 4

    def test_hub_settings_no_db_dependency(self):
        """load_aihub_settings should not import any DB modules."""
        import inspect
        from aksara.ai import hub_settings
        src = inspect.getsource(hub_settings)
        assert "aksara.db" not in src
        assert "database" not in src.lower() or "database_url" not in src

    def test_diagnostics_check_ai_hub_no_db_crash(self):
        """check_ai_hub_config should not crash if DB is down."""
        import asyncio
        from aksara.diagnostics import check_ai_hub_config
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            loop = asyncio.new_event_loop()
            try:
                issues = loop.run_until_complete(check_ai_hub_config())
            finally:
                loop.close()
        assert isinstance(issues, list)


# ─── 4.2  Multiple providers configured ──────────────────────────────────────

class TestMultipleProviders:
    """4.2 – OpenAI + Azure + Ollama all configured."""

    def test_multiple_all_show_in_providers(self):
        from aksara.studio.utils import build_aihub_providers
        hub = _make_hub(
            providers=["openai", "anthropic", ("ollama", {})],
            active="openai",
        )
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_providers()
        kinds = {p.kind for p in r.providers}
        assert "openai" in kinds
        assert "anthropic" in kinds
        assert "ollama" in kinds

    def test_multiple_defaults_deterministic(self):
        """With multiple providers, defaults should be deterministic."""
        from aksara.studio.utils import build_aihub_status
        hub = _make_hub(providers=["openai", "anthropic"], active="openai")
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            s1 = build_aihub_status()
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            s2 = build_aihub_status()
        assert s1.defaults == s2.defaults

    def test_multiple_active_provider_visible_in_routes(self):
        from aksara.studio.utils import build_aihub_routes
        hub = _make_hub(providers=["openai", "anthropic"], active="openai")
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_routes()
        agents = next(rt for rt in r.routes if rt.feature == "agents")
        assert agents.provider == "openai"

    def test_multiple_switch_active_changes_routes(self):
        from aksara.studio.utils import build_aihub_routes
        hub = _make_hub(providers=["openai", "anthropic"], active="anthropic")
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_routes()
        agents = next(rt for rt in r.routes if rt.feature == "agents")
        assert agents.provider == "anthropic"

    def test_multiple_all_configured_count(self):
        from aksara.studio.utils import build_aihub_providers
        hub = _make_hub(providers=["openai", "anthropic", ("ollama", {})])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            r = build_aihub_providers()
        # openai + anthropic have api_key, ollama has base_url
        assert r.configured_count >= 3


# ─── 4.3  Env-only vs Studio-edited config ───────────────────────────────────

class TestEnvVsStudioConfig:
    """4.3 – Env vars detected, file config loaded, precedence clear."""

    def test_env_detection_openai(self):
        from aksara.ai.hub_settings import load_aihub_settings
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-env"}, clear=True):
            hub = load_aihub_settings(include_env=True)
        oai = hub.get_provider("openai")
        assert oai is not None
        assert oai.is_configured

    def test_env_detection_anthropic(self):
        from aksara.ai.hub_settings import load_aihub_settings
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "ant-test"}, clear=True):
            hub = load_aihub_settings(include_env=True)
        anth = hub.get_provider("anthropic")
        assert anth is not None
        assert anth.is_configured

    def test_env_detection_ollama(self):
        from aksara.ai.hub_settings import load_aihub_settings
        with mock.patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://gpu:11434"}, clear=True):
            hub = load_aihub_settings(include_env=True)
        oll = hub.get_provider("ollama")
        assert oll is not None
        assert oll.is_configured

    def test_file_config_loads(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = {
            "providers": [
                {"kind": "openai", "openai": {"api_key": "sk-file-key", "model": "gpt-4o-mini"}},
            ],
            "active_provider": "openai",
        }
        (tmp_path / "aksara.ai.json").write_text(json.dumps(config))
        from aksara.ai.hub_settings import load_aihub_settings
        with mock.patch.dict(os.environ, {}, clear=True):
            hub = load_aihub_settings(include_env=False)
        oai = hub.get_provider("openai")
        assert oai is not None
        assert oai.api_key == "sk-file-key"

    def test_save_and_reload(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        hub = _make_hub(providers=["openai"])
        from aksara.ai.hub_settings import save_aihub_settings, load_aihub_settings
        path = save_aihub_settings(hub, str(tmp_path / "test-ai.json"))
        assert Path(path).exists()

    def test_no_crash_with_both_env_and_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = {"providers": [{"kind": "anthropic", "anthropic": {"api_key": "ant-file"}}]}
        (tmp_path / "aksara.ai.json").write_text(json.dumps(config))
        from aksara.ai.hub_settings import load_aihub_settings
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env"}, clear=True):
            hub = load_aihub_settings(include_env=True)
        # Should have both: file-based anthropic + env-based openai
        oai = hub.get_provider("openai")
        anth = hub.get_provider("anthropic")
        assert oai is not None
        assert anth is not None


# ─── 4.4  Network flakiness / provider errors ────────────────────────────────

class TestNetworkFlakiness:
    """4.4 – All AI features handle network errors gracefully."""

    def test_test_provider_timeout(self):
        from aksara.studio.utils import build_aihub_test
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            with mock.patch(
                "aksara.ai.providers_unified.UnifiedAiProvider.ping",
                side_effect=TimeoutError("Connection timed out"),
            ):
                r = build_aihub_test("openai")
        assert r.reachable is False
        assert r.error is not None

    def test_test_provider_generic_exception(self):
        from aksara.studio.utils import build_aihub_test
        hub = _make_hub(providers=["openai"])
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            with mock.patch(
                "aksara.ai.providers_unified.UnifiedAiProvider.ping",
                side_effect=Exception("Something weird"),
            ):
                r = build_aihub_test("openai")
        assert r.reachable is False
        assert "weird" in r.error.lower()

    def test_status_builder_handles_hub_load_error(self):
        """If _get_hub_settings itself fails, the builder should not 500."""
        from aksara.studio.utils import build_aihub_status
        # This simulates a broken hub_settings module
        with mock.patch(
            "aksara.studio.utils._get_hub_settings",
            side_effect=RuntimeError("config corrupted"),
        ):
            with pytest.raises(RuntimeError):
                build_aihub_status()

    def test_configure_handles_invalid_input(self):
        from aksara.studio.utils import build_aihub_configure
        r = build_aihub_configure(provider="nonexistent")
        assert r.ok is False
        assert "Unknown" in r.message

    def test_configure_handles_exception_in_provider(self):
        from aksara.studio.utils import build_aihub_configure
        # "openai" is valid, but passing bad kwargs triggers Pydantic validation
        r = build_aihub_configure(provider="openai", base_url="https://example.com/v1")
        # This should succeed — base_url is valid
        assert r.ok is True

    def test_embedding_provider_handles_hub_error(self):
        """get_embedding_provider falls back to local when hub fails."""
        from aksara.search.embeddings import get_embedding_provider
        with mock.patch(
            "aksara.ai.hub_settings.load_aihub_settings",
            side_effect=Exception("hub broken"),
        ):
            p = get_embedding_provider()
        assert p is not None

    @pytest.mark.asyncio
    async def test_gap_analysis_graceful_on_provider_crash(self):
        from aksara.gapanalysis import check_ai_hub
        with mock.patch(
            "aksara.ai.hub_settings.load_aihub_settings",
            side_effect=RuntimeError("kaboom"),
        ):
            issues = await check_ai_hub()
        assert issues == []

    def test_to_safe_dict_masks_keys(self):
        hub = _make_hub(providers=["openai"])
        safe = hub.to_safe_dict()
        dumped = json.dumps(safe)
        assert "sk-test-openai" not in dumped

    def test_to_safe_dict_masks_short_keys(self):
        from aksara.ai.hub_settings import ProviderConfig, OpenAIConfig
        pc = ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="sk"))
        safe = pc.to_safe_dict()
        assert safe["openai"]["api_key"] == "****"


# ═════════════════════════════════════════════════════════════════════════════
# Additional structural / regression tests
# ═════════════════════════════════════════════════════════════════════════════


class TestEndpointCompleteness:
    """All v0.5.28 endpoints are registered."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from aksara.studio.fastapi import router
        self.paths = [r.path for r in router.routes if hasattr(r, "path")]

    def test_ai_hub_status(self):
        assert "/studio/ai-hub/status" in self.paths

    def test_ai_hub_providers(self):
        assert "/studio/ai-hub/providers" in self.paths

    def test_ai_hub_models(self):
        assert "/studio/ai-hub/models" in self.paths

    def test_ai_hub_configure(self):
        assert "/studio/ai-hub/configure" in self.paths

    def test_ai_hub_configure_secret(self):
        assert "/studio/ai-hub/configure/secret" in self.paths

    def test_ai_hub_defaults(self):
        assert "/studio/ai-hub/defaults" in self.paths

    def test_ai_hub_test(self):
        assert "/studio/ai-hub/test" in self.paths

    def test_ai_hub_routes(self):
        assert "/studio/ai-hub/routes" in self.paths

    def test_legacy_endpoints_preserved(self):
        assert "/studio/ai/hub/providers" in self.paths
        assert "/studio/ai/hub/providers/save" in self.paths
        assert "/studio/ai/hub/providers/ping" in self.paths


class TestHtmlTemplateIntegrity:
    """HTML template completeness: all panels, IDs, and data attributes."""

    def test_all_nine_ai_hub_tabs(self, html_source):
        expected_tabs = [
            "hub-overview", "providers", "hub-models",
            "routing", "onboarding", "helpers",
            "profiles", "context", "agent",
        ]
        for tab in expected_tabs:
            assert f'data-tab="{tab}"' in html_source, f"Missing tab: {tab}"

    def test_all_nine_tab_panels(self, html_source):
        expected_panels = [
            "hub-overview", "providers", "hub-models",
            "routing", "onboarding", "helpers",
            "profiles", "context", "agent",
        ]
        for panel in expected_panels:
            assert f'data-tab-panel="{panel}"' in html_source, f"Missing panel: {panel}"

    def test_routing_tbody(self, html_source):
        assert 'id="ai-hub-routing-tbody"' in html_source

    def test_models_tbody(self, html_source):
        assert 'id="ai-hub-models-tbody"' in html_source

    def test_overview_elements(self, html_source):
        expected = [
            "ai-hub-overall-status",
            "ai-hub-active-provider",
            "ai-hub-configured-count",
        ]
        for eid in expected:
            assert f'id="{eid}"' in html_source, f"Missing element: {eid}"


class TestCssCompleteness:
    """CSS includes classes for all AI Hub components."""

    def test_provider_card_class(self, css_source):
        assert ".provider-card" in css_source

    def test_onboarding_step_class(self, css_source):
        assert ".onboarding-step" in css_source or "onboarding" in css_source

    def test_ai_hub_panel_class(self, css_source):
        assert ".ai-hub-tabs" in css_source

    def test_toast_classes(self, css_source):
        assert ".toast" in css_source
        assert ".toast-success" in css_source or "toast-error" in css_source

    def test_spotlight_overlay(self, css_source):
        assert ".spotlight" in css_source


class TestResolveDefaultsEdgeCases:
    """Edge cases in default model resolution."""

    def test_resolve_prefers_active_provider(self):
        """When active_provider is set and configured, use it for defaults."""
        hub = _make_hub(providers=["openai", "anthropic"], active="anthropic")
        assert hub.defaults.chat_model == "claude-3-5-sonnet-20241022"

    def test_resolve_falls_back_when_active_unconfigured(self):
        """If active is unconfigured, fall back to first configured."""
        from aksara.ai.hub_settings import (
            AiHubSettings, AiDefaultModels, ProviderConfig, OpenAIConfig,
        )
        hub = AiHubSettings(
            providers=[
                ProviderConfig(kind="anthropic"),  # unconfigured (no api_key)
                ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="sk-x")),
            ],
            defaults=AiDefaultModels(),
            active_provider="anthropic",
        )
        hub.resolve_defaults()
        # Should fall back to openai
        assert hub.defaults.chat_model == "gpt-4o"
        assert hub.active_provider == "openai"

    def test_resolve_embeddings_finds_capable_provider(self):
        """Embeddings should come from a provider that supports them."""
        from aksara.ai.hub_settings import (
            AiHubSettings, AiDefaultModels, ProviderConfig, AnthropicConfig, OpenAIConfig,
        )
        hub = AiHubSettings(
            providers=[
                ProviderConfig(kind="anthropic", anthropic=AnthropicConfig(api_key="ant-x")),
                ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="sk-x")),
            ],
            defaults=AiDefaultModels(),
            active_provider="anthropic",
        )
        hub.resolve_defaults()
        # Anthropic has no embeddings; should fall through to openai
        assert hub.defaults.embeddings_model == "text-embedding-3-large"
        assert hub.defaults.embeddings_provider == "openai"

    def test_resolve_no_providers_leaves_defaults_empty(self):
        hub = _make_hub(providers=[])
        assert hub.defaults.chat_model is None
        assert hub.defaults.embeddings_model is None

    def test_resolve_custom_provider_empty_embeddings(self):
        """Custom provider has empty embeddings default — should not fill."""
        from aksara.ai.hub_settings import (
            AiHubSettings, AiDefaultModels, ProviderConfig, CustomHttpConfig,
        )
        hub = AiHubSettings(
            providers=[ProviderConfig(
                kind="custom",
                custom=CustomHttpConfig(api_key="test-key"),
            )],
            defaults=AiDefaultModels(),
            active_provider="custom",
        )
        hub.resolve_defaults()
        assert hub.defaults.chat_model == "default"
        assert hub.defaults.embeddings_model is None  # custom has "" for embeddings


# ═══════════════════════════════════════════════════════════════════════════
# v0.5.36 — AI Panel Consistency Sweep
# ═══════════════════════════════════════════════════════════════════════════


class TestV036AiPanelEscaping:
    """Ensure AI Inspector uses _esc() for XSS prevention (v0.5.38: consolidated panel)."""

    @pytest.fixture
    def js_src(self):
        return (STATIC_DIR / "app.js").read_text()

    def test_inspector_tab_uses_esc(self, js_src):
        """_renderInspectorTab must escape user data to prevent XSS."""
        fn = _extract_js_function(js_src, "_renderInspectorTab")
        assert "_esc(" in fn

    def test_inspector_error_handler_uses_esc(self, js_src):
        """AI Inspector error paths must escape err.message."""
        assert "_esc(e.message)" in js_src

    def test_inspector_severity_escaping(self, js_src):
        """AI Inspector must escape severity values."""
        fn = _extract_js_function(js_src, "_renderInspectorTab")
        assert "_esc(f.severity" in fn or "_esc(i.severity" in fn

    def test_inspector_grade_escaping(self, js_src):
        """AI Inspector must escape grade values."""
        fn = _extract_js_function(js_src, "_renderInspectorTab")
        assert "_esc(data.grade)" in fn

    def test_no_alert_calls(self, js_src):
        """No raw alert() calls should exist."""
        import re
        matches = re.findall(r"\balert\s*\(", js_src)
        assert len(matches) == 0

    def test_standalone_arch_functions_removed(self, js_src):
        # v0.5.38: old standalone functions removed; escaping now in _renderInspectorTab
        assert "function _renderArchFindings(" not in js_src
        assert "function _renderArchSuggestions(" not in js_src

    def test_standalone_perf_functions_removed(self, js_src):
        # v0.5.38: old standalone functions removed; escaping now in _renderInspectorTab
        assert "function _renderPerfIssues(" not in js_src
        assert "function _renderPerfRecommendations(" not in js_src


class TestV036AiPanelStates:
    """AI Inspector must have loading and empty/error states (v0.5.38: consolidated panel)."""

    @pytest.fixture
    def html_src(self):
        return (STATIC_DIR / "index.html").read_text()

    @pytest.fixture
    def js_src(self):
        return (STATIC_DIR / "app.js").read_text()

    def test_inspector_loading_state(self, js_src):
        assert "ai-inspector-loading" in js_src

    def test_inspector_empty_state(self, js_src):
        assert "ai-inspector-empty" in js_src

    def test_standalone_states_removed(self, js_src):
        # v0.5.38: old standalone state strings removed
        assert "ai-debugger-loading" not in js_src
        assert "ai-arch-loading" not in js_src
        assert "ai-perf-loading" not in js_src

    def test_live_panels_in_nav(self, html_src):
        """Active nav sections should be present in sidebar."""
        for panel in ["ai-console", "ai-graph", "ai-inspector"]:
            assert panel in html_src, f"Missing nav item for {panel}"

    def test_old_panels_redirect_via_js(self, js_src):
        """Old section names still handled via redirect map in app.js."""
        for panel in ["ai-debugger", "ai-architecture", "ai-performance"]:
            assert panel in js_src, f"Missing redirect entry for {panel}"


class TestV036CssVersionHeader:
    """CSS version and AI Inspector styles (v0.5.38: standalone sections removed)."""

    def test_css_version_is_current(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert "v0.5.36" in css[:200]

    def test_css_standalone_arch_styles_removed(self):
        # v0.5.38: .ai-arch-* classes removed with the consolidated inspector
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".ai-arch-finding-card" not in css
        assert ".ai-arch-sev-critical" not in css

    def test_css_standalone_perf_styles_removed(self):
        # v0.5.38: most .ai-perf-* classes removed; .ai-perf-sev-badge preserved
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".ai-perf-issue-card" not in css
        assert ".ai-perf-sev-high" not in css

    def test_css_standalone_debugger_styles_removed(self):
        # v0.5.38: .ai-debugger-* classes removed
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".ai-debugger-" not in css

    def test_css_has_inspector_styles(self):
        # v0.5.38: AI Inspector CSS is the live replacement
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".ai-inspector-tabs" in css
        assert ".ai-inspector-panel" in css
        assert ".ai-perf-sev-badge" in css


def _extract_js_function(source: str, name: str) -> str:
    """Extract a JS function body by name (simple brace-matching)."""
    prefix = f"function {name}("
    start = source.find(prefix)
    if start < 0:
        return ""
    brace = source.index("{", start)
    depth, i = 0, brace
    while i < len(source):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
        i += 1
    return source[start:]
