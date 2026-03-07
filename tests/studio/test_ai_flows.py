"""
v0.5.29 — Studio AI Flows: backend builder tests.

Tests cover:
    - Flow action registry completeness
    - All 5 builders (model / route / query / migration / diagnostic)
    - Stable response contract (StudioAiFlowResponse fields)
    - Missing AI Hub config yields AI_HUB_NOT_CONFIGURED
    - Risk levels are valid
    - Hub defaults for provider/model selection
    - Prompt pack determinism
    - Context helpers produce sane output
    - Hub override support
    - Edge cases: unknown action, wrong kind, empty input
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from aksara.studio.models import StudioAiFlowResponse


# ─── Fixtures ────────────────────────────────────────────────────────────────

class _FakeDefaults:
    chat_model = "gpt-4.1-mini"
    chat_provider = "openai"
    code_model = "gpt-4.1-mini"
    code_provider = "openai"
    embeddings_model = "text-embedding-3-small"
    embeddings_provider = "openai"


class _FakeProvider:
    kind = "openai"
    enabled = True
    is_configured = True
    api_key = "sk-test"
    model = "gpt-4.1-mini"
    base_url = ""
    def get_supported_modes(self): return ["chat"]
    def to_unified_provider(self): return MagicMock()


class _FakeHub:
    providers = [_FakeProvider()]
    defaults = _FakeDefaults()
    active_provider = "openai"
    version = "0.5.36"
    def configured_providers(self): return [_FakeProvider()]
    def get_provider(self, kind): return _FakeProvider() if kind == "openai" else None
    def provider_status_summary(self): return {}
    def resolve_defaults(self): return {}
    def to_safe_dict(self): return {}


class _FakeHubEmpty:
    """AI Hub with zero configured providers."""
    providers = []
    defaults = type("D", (), {
        "chat_model": None, "chat_provider": None,
        "code_model": None, "code_provider": None,
        "embeddings_model": None, "embeddings_provider": None,
    })()
    active_provider = None
    version = "0.5.36"
    def configured_providers(self): return []
    def get_provider(self, kind): return None


@pytest.fixture
def hub():
    return _FakeHub()


@pytest.fixture
def hub_empty():
    return _FakeHubEmpty()


def _patch_hub(fake):
    return patch("aksara.studio.ai_flows._get_hub_settings", return_value=fake)


# ─── 1. Action Registry ─────────────────────────────────────────────────────

class TestAiFlowActionRegistry:
    def test_list_flow_actions_returns_list(self):
        from aksara.studio.ai_flows import list_flow_actions
        actions = list_flow_actions()
        assert isinstance(actions, list)
        assert len(actions) >= 11

    def test_all_actions_have_required_keys(self):
        from aksara.studio.ai_flows import list_flow_actions
        for a in list_flow_actions():
            assert "action_key" in a
            assert "kind" in a
            assert "title" in a
            assert "description" in a
            assert "risk" in a

    def test_action_keys_unique(self):
        from aksara.studio.ai_flows import list_flow_actions
        keys = [a["action_key"] for a in list_flow_actions()]
        assert len(keys) == len(set(keys))

    def test_risk_values_valid(self):
        from aksara.studio.ai_flows import list_flow_actions
        for a in list_flow_actions():
            assert a["risk"] in ("low", "medium", "high")

    def test_kind_values_valid(self):
        from aksara.studio.ai_flows import list_flow_actions
        valid_kinds = {"model", "route", "query", "migration", "diagnostic"}
        for a in list_flow_actions():
            assert a["kind"] in valid_kinds

    def test_model_actions_exist(self):
        from aksara.studio.ai_flows import list_flow_actions
        model_actions = [a for a in list_flow_actions() if a["kind"] == "model"]
        assert len(model_actions) == 3

    def test_route_actions_exist(self):
        from aksara.studio.ai_flows import list_flow_actions
        route_actions = [a for a in list_flow_actions() if a["kind"] == "route"]
        assert len(route_actions) == 3

    def test_query_actions_exist(self):
        from aksara.studio.ai_flows import list_flow_actions
        query_actions = [a for a in list_flow_actions() if a["kind"] == "query"]
        assert len(query_actions) == 3

    def test_migration_actions_exist(self):
        from aksara.studio.ai_flows import list_flow_actions
        mig_actions = [a for a in list_flow_actions() if a["kind"] == "migration"]
        assert len(mig_actions) == 2

    def test_diagnostic_actions_exist(self):
        from aksara.studio.ai_flows import list_flow_actions
        diag_actions = [a for a in list_flow_actions() if a["kind"] == "diagnostic"]
        assert len(diag_actions) == 1

    def test_get_flow_action_found(self):
        from aksara.studio.ai_flows import get_flow_action
        a = get_flow_action("explain_model")
        assert a is not None
        assert a["action_key"] == "explain_model"

    def test_get_flow_action_not_found(self):
        from aksara.studio.ai_flows import get_flow_action
        assert get_flow_action("nonexistent_action") is None

    def test_what_it_does_present(self):
        from aksara.studio.ai_flows import list_flow_actions
        for a in list_flow_actions():
            assert "what_it_does" in a and len(a["what_it_does"]) > 5

    def test_what_it_cannot_do_present(self):
        from aksara.studio.ai_flows import list_flow_actions
        for a in list_flow_actions():
            assert "what_it_cannot_do" in a and len(a["what_it_cannot_do"]) > 5

    def test_recommended_next_is_list(self):
        from aksara.studio.ai_flows import list_flow_actions
        for a in list_flow_actions():
            assert isinstance(a.get("recommended_next", []), list)


# ─── 2. Response Contract ───────────────────────────────────────────────────

class TestResponseContract:
    def test_response_model_fields(self):
        resp = StudioAiFlowResponse()
        assert hasattr(resp, "ok")
        assert hasattr(resp, "action_key")
        assert hasattr(resp, "risk")
        assert hasattr(resp, "provider")
        assert hasattr(resp, "model")
        assert hasattr(resp, "system_prompt")
        assert hasattr(resp, "user_prompt")
        assert hasattr(resp, "result_markdown")
        assert hasattr(resp, "result_json")
        assert hasattr(resp, "suggested_next")
        assert hasattr(resp, "what_it_does")
        assert hasattr(resp, "what_it_cannot_do")
        assert hasattr(resp, "error_code")
        assert hasattr(resp, "error")

    def test_default_ok_is_true(self):
        resp = StudioAiFlowResponse()
        assert resp.ok is True

    def test_default_risk_is_low(self):
        resp = StudioAiFlowResponse()
        assert resp.risk == "low"

    def test_serialisation_roundtrip(self):
        resp = StudioAiFlowResponse(
            ok=True,
            action_key="explain_model",
            risk="low",
            provider="openai",
            model="gpt-4.1-mini",
            system_prompt="sys",
            user_prompt="usr",
            result_markdown="md",
            suggested_next=["a", "b"],
        )
        d = resp.model_dump()
        resp2 = StudioAiFlowResponse(**d)
        assert resp2.action_key == "explain_model"


# ─── 3. Model Flow Builder ──────────────────────────────────────────────────

class TestBuildModelFlow:
    def test_explain_model_ok(self, hub):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub):
            resp = build_model_flow("User", "explain_model")
        assert resp.ok is True
        assert resp.action_key == "explain_model"
        assert resp.risk == "low"
        assert resp.provider == "openai"
        assert resp.model == "gpt-4.1-mini"

    def test_suggest_constraints_ok(self, hub):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub):
            resp = build_model_flow("User", "suggest_constraints")
        assert resp.ok is True
        assert resp.risk == "medium"

    def test_refactor_suggestions_ok(self, hub):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub):
            resp = build_model_flow("User", "refactor_suggestions")
        assert resp.ok is True
        assert resp.risk == "medium"

    def test_system_prompt_not_empty(self, hub):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub):
            resp = build_model_flow("User", "explain_model")
        assert len(resp.system_prompt) > 20

    def test_user_prompt_contains_model_name(self, hub):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub):
            resp = build_model_flow("User", "explain_model")
        assert "User" in resp.user_prompt

    def test_model_not_found_still_ok(self, hub):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub):
            resp = build_model_flow("NonExistentModel", "explain_model")
        assert resp.ok is True
        assert "not found" in resp.user_prompt.lower() or "NonExistentModel" in resp.user_prompt

    def test_invalid_action_key(self, hub):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub):
            resp = build_model_flow("User", "totally_bogus")
        assert resp.ok is False
        assert resp.error_code == "INVALID_ACTION"

    def test_wrong_kind_action(self, hub):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub):
            resp = build_model_flow("User", "review_endpoint")  # route action
        assert resp.ok is False
        assert resp.error_code == "INVALID_ACTION"

    def test_hub_not_configured(self, hub_empty):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub_empty):
            resp = build_model_flow("User", "explain_model")
        assert resp.ok is False
        assert resp.error_code == "AI_HUB_NOT_CONFIGURED"

    def test_suggested_next_populated(self, hub):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub):
            resp = build_model_flow("User", "explain_model")
        assert isinstance(resp.suggested_next, list)
        assert len(resp.suggested_next) >= 1

    def test_what_it_does_populated(self, hub):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub):
            resp = build_model_flow("User", "explain_model")
        assert len(resp.what_it_does) > 5

    def test_what_it_cannot_do_populated(self, hub):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub):
            resp = build_model_flow("User", "explain_model")
        assert len(resp.what_it_cannot_do) > 5

    def test_deterministic_output(self, hub):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub):
            r1 = build_model_flow("User", "explain_model")
            r2 = build_model_flow("User", "explain_model")
        assert r1.system_prompt == r2.system_prompt
        assert r1.user_prompt == r2.user_prompt

    def test_hub_override_provider(self, hub):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub):
            resp = build_model_flow("User", "explain_model", hub_overrides={"provider": "anthropic", "model": "claude-3"})
        assert resp.provider == "anthropic"
        assert resp.model == "claude-3"


# ─── 4. Route Flow Builder ──────────────────────────────────────────────────

class TestBuildRouteFlow:
    def _patch_route_ctx(self, path="/api/users", method="GET"):
        """Patch _build_route_context to return deterministic context."""
        return patch(
            "aksara.studio.ai_flows._build_route_context",
            return_value=f"## Endpoint: {method} {path}\nName: list_users\nTags: ['users']",
        )

    def test_review_endpoint_ok(self, hub):
        from aksara.studio.ai_flows import build_route_flow
        with _patch_hub(hub), self._patch_route_ctx():
            resp = build_route_flow("/api/users", "GET", "review_endpoint")
        assert resp.ok is True
        assert resp.risk == "low"

    def test_harden_permissions_ok(self, hub):
        from aksara.studio.ai_flows import build_route_flow
        with _patch_hub(hub), self._patch_route_ctx():
            resp = build_route_flow("/api/users", "POST", "harden_permissions")
        assert resp.ok is True
        assert resp.risk == "medium"

    def test_generate_examples_ok(self, hub):
        from aksara.studio.ai_flows import build_route_flow
        with _patch_hub(hub), self._patch_route_ctx():
            resp = build_route_flow("/api/users", "GET", "generate_examples")
        assert resp.ok is True

    def test_prompt_contains_path(self, hub):
        from aksara.studio.ai_flows import build_route_flow
        with _patch_hub(hub), self._patch_route_ctx():
            resp = build_route_flow("/api/users", "GET", "review_endpoint")
        assert "/api/users" in resp.user_prompt

    def test_invalid_action(self, hub):
        from aksara.studio.ai_flows import build_route_flow
        with _patch_hub(hub):
            resp = build_route_flow("/api", "GET", "explain_model")
        assert resp.ok is False

    def test_hub_not_configured(self, hub_empty):
        from aksara.studio.ai_flows import build_route_flow
        with _patch_hub(hub_empty):
            resp = build_route_flow("/api", "GET", "review_endpoint")
        assert resp.ok is False
        assert resp.error_code == "AI_HUB_NOT_CONFIGURED"


# ─── 5. Query Flow Builder ──────────────────────────────────────────────────

class TestBuildQueryFlow:
    def test_explain_plan_ok(self, hub):
        from aksara.studio.ai_flows import build_query_flow
        with _patch_hub(hub):
            resp = build_query_flow("SELECT * FROM users", "explain_plan")
        assert resp.ok is True
        assert resp.risk == "low"

    def test_suggest_indexes_ok(self, hub):
        from aksara.studio.ai_flows import build_query_flow
        with _patch_hub(hub):
            resp = build_query_flow("SELECT * FROM users WHERE status = 'active'", "suggest_indexes")
        assert resp.ok is True
        assert resp.risk == "medium"

    def test_rewrite_suggestions_ok(self, hub):
        from aksara.studio.ai_flows import build_query_flow
        with _patch_hub(hub):
            resp = build_query_flow("SELECT * FROM users", "rewrite_suggestions")
        assert resp.ok is True

    def test_prompt_contains_sql(self, hub):
        from aksara.studio.ai_flows import build_query_flow
        with _patch_hub(hub):
            resp = build_query_flow("SELECT id FROM orders", "explain_plan")
        assert "SELECT id FROM orders" in resp.user_prompt

    def test_invalid_action(self, hub):
        from aksara.studio.ai_flows import build_query_flow
        with _patch_hub(hub):
            resp = build_query_flow("SELECT 1", "explain_model")
        assert resp.ok is False

    def test_hub_not_configured(self, hub_empty):
        from aksara.studio.ai_flows import build_query_flow
        with _patch_hub(hub_empty):
            resp = build_query_flow("SELECT 1", "explain_plan")
        assert resp.ok is False
        assert resp.error_code == "AI_HUB_NOT_CONFIGURED"

    def test_include_explain_flag(self, hub):
        from aksara.studio.ai_flows import build_query_flow
        with _patch_hub(hub):
            resp = build_query_flow("SELECT 1", "explain_plan", include_explain=True)
        assert "EXPLAIN" in resp.user_prompt


# ─── 6. Migration Flow Builder ──────────────────────────────────────────────

class TestBuildMigrationFlow:
    def test_explain_migration_ok(self, hub):
        from aksara.studio.ai_flows import build_migration_flow
        with _patch_hub(hub):
            resp = build_migration_flow("explain_migration", app="blog", name="001_initial")
        assert resp.ok is True
        assert resp.risk == "low"

    def test_safe_rollout_plan_ok(self, hub):
        from aksara.studio.ai_flows import build_migration_flow
        with _patch_hub(hub):
            resp = build_migration_flow("safe_rollout_plan", app="blog")
        assert resp.ok is True
        assert resp.risk == "medium"

    def test_prompt_contains_app(self, hub):
        from aksara.studio.ai_flows import build_migration_flow
        with _patch_hub(hub):
            resp = build_migration_flow("explain_migration", app="blog")
        assert "blog" in resp.user_prompt

    def test_invalid_action(self, hub):
        from aksara.studio.ai_flows import build_migration_flow
        with _patch_hub(hub):
            resp = build_migration_flow("explain_model")
        assert resp.ok is False

    def test_hub_not_configured(self, hub_empty):
        from aksara.studio.ai_flows import build_migration_flow
        with _patch_hub(hub_empty):
            resp = build_migration_flow("explain_migration")
        assert resp.ok is False
        assert resp.error_code == "AI_HUB_NOT_CONFIGURED"


# ─── 7. Diagnostic Flow Builder ─────────────────────────────────────────────

class TestBuildDiagnosticFlow:
    def test_diagnostic_prioritize_ok(self, hub):
        from aksara.studio.ai_flows import build_diagnostic_flow
        issue = {"category": "db", "severity": "error", "title": "No DB", "message": "Database not connected"}
        with _patch_hub(hub):
            resp = build_diagnostic_flow("diagnostic_prioritize", issue_payload=issue)
        assert resp.ok is True
        assert resp.risk == "low"

    def test_prompt_contains_issue(self, hub):
        from aksara.studio.ai_flows import build_diagnostic_flow
        issue = {"category": "db", "severity": "error", "title": "No DB URL", "message": "DATABASE_URL not set"}
        with _patch_hub(hub):
            resp = build_diagnostic_flow("diagnostic_prioritize", issue_payload=issue)
        assert "No DB URL" in resp.user_prompt

    def test_with_issue_id(self, hub):
        from aksara.studio.ai_flows import build_diagnostic_flow
        with _patch_hub(hub):
            resp = build_diagnostic_flow("diagnostic_prioritize", issue_id="DB_NO_URL")
        assert resp.ok is True
        assert "DB_NO_URL" in resp.user_prompt

    def test_invalid_action(self, hub):
        from aksara.studio.ai_flows import build_diagnostic_flow
        with _patch_hub(hub):
            resp = build_diagnostic_flow("explain_model")
        assert resp.ok is False

    def test_hub_not_configured(self, hub_empty):
        from aksara.studio.ai_flows import build_diagnostic_flow
        with _patch_hub(hub_empty):
            resp = build_diagnostic_flow("diagnostic_prioritize")
        assert resp.ok is False
        assert resp.error_code == "AI_HUB_NOT_CONFIGURED"

    def test_issue_with_actions(self, hub):
        from aksara.studio.ai_flows import build_diagnostic_flow
        issue = {
            "category": "migrations",
            "severity": "warning",
            "title": "Pending migrations",
            "message": "2 unapplied migrations",
            "actions": [{"description": "Run: aksara migrate apply"}],
        }
        with _patch_hub(hub):
            resp = build_diagnostic_flow("diagnostic_prioritize", issue_payload=issue)
        assert "aksara migrate apply" in resp.user_prompt


# ─── 8. Prompt Determinism ──────────────────────────────────────────────────

class TestPromptDeterminism:
    def test_model_flow_deterministic(self, hub):
        from aksara.studio.ai_flows import build_model_flow
        with _patch_hub(hub):
            a = build_model_flow("User", "explain_model")
            b = build_model_flow("User", "explain_model")
        assert a.system_prompt == b.system_prompt
        assert a.user_prompt == b.user_prompt

    def test_route_flow_deterministic(self, hub):
        from aksara.studio.ai_flows import build_route_flow
        with _patch_hub(hub):
            a = build_route_flow("/api/users", "GET", "review_endpoint")
            b = build_route_flow("/api/users", "GET", "review_endpoint")
        assert a.system_prompt == b.system_prompt

    def test_query_flow_deterministic(self, hub):
        from aksara.studio.ai_flows import build_query_flow
        with _patch_hub(hub):
            a = build_query_flow("SELECT 1", "explain_plan")
            b = build_query_flow("SELECT 1", "explain_plan")
        assert a.user_prompt == b.user_prompt


# ─── 9. Context Helpers ─────────────────────────────────────────────────────

class TestContextHelpers:
    def test_build_model_context_not_found(self):
        from aksara.studio.ai_flows import _build_model_context
        ctx = _build_model_context("NonexistentModel999")
        assert "not found" in ctx.lower() or "NonexistentModel999" in ctx

    def test_build_route_context_not_found(self):
        from aksara.studio.ai_flows import _build_route_context
        ctx = _build_route_context("/never/exists", "DELETE")
        # Without a running app, returns an error or "not found" string
        assert "not found" in ctx.lower() or "error" in ctx.lower() or "/never/exists" in ctx

    def test_build_query_context_contains_sql(self):
        from aksara.studio.ai_flows import _build_query_context
        ctx = _build_query_context("SELECT * FROM foo")
        assert "SELECT * FROM foo" in ctx

    def test_build_query_context_explain_note(self):
        from aksara.studio.ai_flows import _build_query_context
        ctx = _build_query_context("SELECT 1", include_explain=True)
        assert "EXPLAIN" in ctx

    def test_build_migration_context(self):
        from aksara.studio.ai_flows import _build_migration_context
        ctx = _build_migration_context(app="blog", name="001")
        assert "blog" in ctx
        assert "001" in ctx

    def test_build_diagnostic_context_with_payload(self):
        from aksara.studio.ai_flows import _build_diagnostic_context
        ctx = _build_diagnostic_context(issue_payload={"category": "db", "severity": "error", "title": "Test"})
        assert "Test" in ctx

    def test_build_diagnostic_context_with_id(self):
        from aksara.studio.ai_flows import _build_diagnostic_context
        ctx = _build_diagnostic_context(issue_id="DB_001")
        assert "DB_001" in ctx

    def test_build_diagnostic_context_empty(self):
        from aksara.studio.ai_flows import _build_diagnostic_context
        ctx = _build_diagnostic_context()
        assert "No issue data" in ctx
