"""
Tests for AI Hub 2.0 — Studio UI.

v0.5.28: Tests for the new AI Hub 2.0 panel HTML, CSS, and JS integration.
Covers:
  - HTML template: new tabs (Overview, Models, Routing, Onboarding), global indicator
  - JavaScript: rendering functions, state, keyboard shortcut
  - CSS: new style classes
  - Endpoint wiring: new /studio/ai-hub/* endpoints
"""

import pytest
from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "aksara" / "studio" / "static"


# =============================================================================
# HTML Tests — Template Structure
# =============================================================================

class TestAiHubHtmlTemplate:
    """Tests for the AI Hub template in index.html."""

    def test_template_exists(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="template-ai-hub"' in html

    def test_section_header(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert "AI Hub" in html
        assert "Unified AI provider management" in html

    def test_tab_overview_exists(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-tab="hub-overview"' in html

    def test_tab_providers_exists(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-tab="providers"' in html

    def test_tab_models_exists(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-tab="hub-models"' in html

    def test_tab_routing_exists(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-tab="routing"' in html

    def test_tab_onboarding_exists(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-tab="onboarding"' in html

    def test_tab_helpers_preserved(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-tab="helpers"' in html

    def test_tab_profiles_preserved(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-tab="profiles"' in html

    def test_tab_context_preserved(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-tab="context"' in html

    def test_tab_agent_preserved(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-tab="agent"' in html

    def test_overview_is_default_active(self):
        html = (STATIC_DIR / "index.html").read_text()
        # hub-overview tab should have 'active' class
        assert 'ai-hub-tab active" data-tab="hub-overview"' in html


class TestAiHubHtmlOverviewPanel:
    """Tests for the Overview panel HTML."""

    def test_overview_panel_exists(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-tab-panel="hub-overview"' in html

    def test_overall_status_metric(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-overall-status"' in html

    def test_active_provider_metric(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-active-provider"' in html

    def test_configured_count_metric(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-configured-count"' in html

    def test_onboarding_status_metric(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-onboarding-status"' in html

    def test_defaults_summary_container(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-defaults-summary"' in html

    def test_overview_providers_container(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-overview-providers"' in html

    def test_overview_warnings_container(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-overview-warnings"' in html

    def test_overview_refresh_button(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-overview-refresh"' in html


class TestAiHubHtmlProvidersPanel:
    """Tests for the enhanced Providers panel HTML."""

    def test_providers_panel_exists(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-tab-panel="providers"' in html

    def test_provider_list_container(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-provider-list"' in html

    def test_provider_config_panel(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-provider-config-panel"' in html

    def test_provider_select(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-cfg-provider"' in html

    def test_provider_apikey_input(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-cfg-apikey"' in html

    def test_provider_save_button(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-cfg-save"' in html

    def test_provider_ping_button(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-cfg-ping"' in html


class TestAiHubHtmlModelsPanel:
    """Tests for the Models panel HTML."""

    def test_models_panel_exists(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-tab-panel="hub-models"' in html

    def test_models_table(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-models-table"' in html

    def test_models_tbody(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-models-tbody"' in html

    def test_default_chat_input(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-default-chat"' in html

    def test_default_code_input(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-default-code"' in html

    def test_default_embeddings_input(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-default-embeddings"' in html

    def test_defaults_save_button(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-defaults-save"' in html

    def test_models_refresh_button(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-models-refresh"' in html

    def test_defaults_result_container(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-defaults-result"' in html


class TestAiHubHtmlRoutingPanel:
    """Tests for the Routing/Usage panel HTML."""

    def test_routing_panel_exists(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-tab-panel="routing"' in html

    def test_routing_table(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-routing-table"' in html

    def test_routing_tbody(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-routing-tbody"' in html

    def test_routing_refresh_button(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-routing-refresh"' in html

    def test_routing_warnings_container(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-routing-warnings"' in html

    def test_routing_info_banner(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert "which AI provider and model each Aksara feature uses" in html


class TestAiHubHtmlOnboardingPanel:
    """Tests for the Onboarding wizard panel HTML."""

    def test_onboarding_panel_exists(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-tab-panel="onboarding"' in html

    def test_onboarding_steps_container(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-hub-onboarding-steps"' in html

    def test_step_1_select_providers(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert "Select Providers" in html
        assert 'id="onboarding-provider-select"' in html

    def test_step_2_enter_keys(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert "Enter API Keys" in html
        assert 'id="onboarding-keys-form"' in html

    def test_step_3_test_connections(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert "Test Connections" in html
        assert 'id="onboarding-test-results"' in html

    def test_step_4_choose_defaults(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert "Choose Defaults" in html
        assert 'id="onboarding-defaults-form"' in html

    def test_step_5_sample_query(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert "Sample Query" in html
        assert 'id="onboarding-sample-prompt"' in html

    def test_onboarding_test_all_button(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="onboarding-test-all"' in html

    def test_onboarding_save_keys_button(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="onboarding-save-keys"' in html

    def test_onboarding_save_defaults_button(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="onboarding-save-defaults"' in html

    def test_onboarding_run_sample_button(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="onboarding-run-sample"' in html

    def test_onboarding_step_statuses(self):
        html = (STATIC_DIR / "index.html").read_text()
        for i in range(1, 6):
            assert f'id="onboarding-step-{i}-status"' in html


# =============================================================================
# HTML Tests — Global AI Status Indicator
# =============================================================================

class TestAiHubHtmlGlobalIndicator:
    """Tests for the global AI status indicator in the sidebar."""

    def test_indicator_container(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-status-indicator"' in html

    def test_indicator_dot(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-status-dot"' in html

    def test_indicator_label(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="ai-status-label"' in html

    def test_indicator_class(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert "ai-status-indicator" in html

    def test_indicator_initially_hidden(self):
        html = (STATIC_DIR / "index.html").read_text()
        # The indicator should start hidden, shown via JS after status loads
        assert 'id="ai-status-indicator"' in html
        # display:none on the element
        idx = html.index('id="ai-status-indicator"')
        snippet = html[max(0, idx - 100):idx + 100]
        assert "display:none" in snippet


# =============================================================================
# JavaScript Tests
# =============================================================================

class TestAiHubJs:
    """Tests for the AI Hub 2.0 JavaScript functions."""

    def test_state_aihub_status(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "status: null" in js
        # v0.5.28 fields
        assert "models: null" in js
        assert "routing: null" in js

    def test_state_onboarding(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "onboardingState" in js

    def test_render_aihub_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "async function renderAiHub()" in js

    def test_load_aihub_overview_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "async function loadAiHubOverview()" in js

    def test_load_aihub_models_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "async function loadAiHubModels()" in js

    def test_load_aihub_routing_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "async function loadAiHubRouting()" in js

    def test_load_aihub_onboarding_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "async function loadAiHubOnboarding()" in js

    def test_load_ai_status_indicator_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "async function loadAiStatusIndicator()" in js

    def test_aihub_save_defaults_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "async function aiHubSaveDefaults()" in js

    def test_onboarding_test_all_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "async function onboardingTestAll()" in js

    def test_onboarding_save_keys_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "async function onboardingSaveKeys()" in js

    def test_onboarding_save_defaults_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "async function onboardingSaveDefaults()" in js

    def test_onboarding_run_sample_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "async function onboardingRunSample()" in js

    def test_aihub_test_provider_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "async function aiHubTestProvider(" in js

    def test_aihub_select_provider_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "function aiHubSelectProvider(" in js

    def test_hub_overview_is_default_loaded_tab(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "'hub-overview': true" in js

    def test_lazy_load_models_tab(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "if (target === 'hub-models') loadAiHubModels();" in js

    def test_lazy_load_routing_tab(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "if (target === 'routing') loadAiHubRouting();" in js

    def test_lazy_load_onboarding_tab(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "if (target === 'onboarding') loadAiHubOnboarding();" in js

    def test_provider_icons_in_js(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "providerIcons" in js
        assert "openai" in js and "🤖" in js

    def test_overview_calls_status_endpoint(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "/studio/ai-hub/status" in js

    def test_models_calls_models_endpoint(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "/studio/ai-hub/models" in js

    def test_providers_calls_providers_endpoint(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "/studio/ai-hub/providers" in js

    def test_defaults_calls_defaults_endpoint(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "/studio/ai-hub/defaults" in js

    def test_test_calls_test_endpoint(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "/studio/ai-hub/test" in js

    def test_configure_secret_endpoint_in_onboarding(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "/studio/ai-hub/configure/secret" in js


class TestAiHubJsKeyboardShortcut:
    """Tests for AI Hub keyboard shortcuts."""

    def test_alt_a_shortcut(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "e.altKey" in js
        # Alt+A navigates to AI Home (v0.5.38: changed from AI Hub)
        assert "v0.5.28: Alt/Option+A opens AI Home" in js

    def test_existing_a_shortcut_preserved(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "v0.5.25: 'A' opens AI Home" in js

    def test_indicator_loaded_during_init(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "loadAiStatusIndicator()" in js


class TestAiHubJsStatusIndicator:
    """Tests for global AI status indicator JavaScript."""

    def test_indicator_sets_ready_class(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "ai-status-ready" in js or "ai-status-" in js

    def test_indicator_sets_partial_class(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "AI Partial" in js

    def test_indicator_sets_disabled_label(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "AI Off" in js

    def test_indicator_sets_ready_label(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "AI Ready" in js


# =============================================================================
# CSS Tests
# =============================================================================

class TestAiHubCss:
    """Tests for AI Hub 2.0 CSS styles."""

    def test_ai_status_indicator_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".ai-status-indicator" in css

    def test_ai_status_dot_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".ai-status-dot" in css

    def test_ai_status_ready_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".ai-status-dot.ai-status-ready" in css

    def test_ai_status_partial_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".ai-status-dot.ai-status-partial" in css

    def test_ai_status_disabled_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".ai-status-dot.ai-status-disabled" in css

    def test_defaults_grid_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".defaults-grid" in css

    def test_defaults_row_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".defaults-row" in css

    def test_defaults_label_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".defaults-label" in css

    def test_provider_cards_grid_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".provider-cards-grid" in css

    def test_provider_card_actions_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".provider-card-actions" in css

    def test_provider_summary_row_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".provider-summary-row" in css

    def test_btn_xs_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".btn-xs" in css

    def test_data_table_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".data-table" in css

    def test_data_table_thead(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".data-table thead th" in css

    def test_data_table_tbody(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".data-table tbody td" in css

    def test_onboarding_steps_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".onboarding-steps" in css

    def test_onboarding_step_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".onboarding-step" in css

    def test_onboarding_step_header_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".onboarding-step-header" in css

    def test_onboarding_step_number_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".onboarding-step-number" in css

    def test_onboarding_step_title_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".onboarding-step-title" in css

    def test_onboarding_step_status_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".onboarding-step-status" in css

    def test_onboarding_test_results_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".onboarding-test-results" in css

    def test_ai_hub_warnings_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".ai-hub-warnings" in css

    def test_text_warning_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".text-warning" in css

    def test_defaults_edit_grid_class(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".defaults-edit-grid" in css
