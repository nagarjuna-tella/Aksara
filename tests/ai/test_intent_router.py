"""
v0.5.31 — AI Intent Router: comprehensive unit tests.

Tests cover:
    - detect_intent() for all 11 action keys with primary phrases
    - Confidence levels and ranking
    - Context extraction: model name, route method+path, SQL, migration ref, issue id
    - Edge cases: empty input, gibberish, overlapping patterns
    - list_intents() shape and completeness
    - suggest_commands() autocomplete
    - EXAMPLE_COMMANDS list integrity
    - IntentMatch dataclass defaults
"""

from __future__ import annotations

import pytest
from aksara.ai.intent_router import (
    IntentMatch,
    detect_intent,
    list_intents,
    suggest_commands,
    EXAMPLE_COMMANDS,
    _extract_context,
)


# ═══════════════════════════════════════════════════════════════════════════
# IntentMatch defaults
# ═══════════════════════════════════════════════════════════════════════════


class TestIntentMatchDefaults:

    def test_default_intent(self):
        m = IntentMatch()
        assert m.intent == "unknown"

    def test_default_flow_type(self):
        m = IntentMatch()
        assert m.flow_type == ""

    def test_default_action_key(self):
        m = IntentMatch()
        assert m.action_key == ""

    def test_default_confidence(self):
        m = IntentMatch()
        assert m.confidence == 0.0

    def test_default_context(self):
        m = IntentMatch()
        assert m.extracted_context == {}


# ═══════════════════════════════════════════════════════════════════════════
# detect_intent — model intents
# ═══════════════════════════════════════════════════════════════════════════


class TestModelIntents:

    def test_explain_model(self):
        m = detect_intent("explain the User model")
        assert m.action_key == "explain_model"
        assert m.flow_type == "model"
        assert m.confidence > 0.80

    def test_explain_model_reversed(self):
        m = detect_intent("model User explain")
        assert m.action_key == "explain_model"

    def test_describe_model(self):
        m = detect_intent("describe the Product model")
        assert m.action_key == "explain_model"

    def test_tell_me_about_model(self):
        m = detect_intent("tell me about the Order model")
        assert m.action_key == "explain_model"

    def test_what_is_model(self):
        m = detect_intent("what is the Account model")
        assert m.action_key == "explain_model"

    def test_suggest_constraints(self):
        m = detect_intent("suggest constraints for Order")
        assert m.action_key == "suggest_constraints"
        assert m.flow_type == "model"

    def test_missing_constraints(self):
        m = detect_intent("missing constraints on User")
        assert m.action_key == "suggest_constraints"

    def test_refactor_model(self):
        m = detect_intent("refactor the Product model")
        assert m.action_key == "refactor_suggestions"
        assert m.flow_type == "model"

    def test_improve_model(self):
        m = detect_intent("improve the Order model")
        assert m.action_key == "refactor_suggestions"

    def test_clean_up_model(self):
        m = detect_intent("clean up the Invoice model")
        assert m.action_key == "refactor_suggestions"


# ═══════════════════════════════════════════════════════════════════════════
# detect_intent — route intents
# ═══════════════════════════════════════════════════════════════════════════


class TestRouteIntents:

    def test_review_endpoint(self):
        m = detect_intent("review endpoint GET /api/users")
        assert m.action_key == "review_endpoint"
        assert m.flow_type == "route"

    def test_review_route(self):
        m = detect_intent("review route POST /api/orders")
        assert m.action_key == "review_endpoint"

    def test_review_http_method(self):
        m = detect_intent("review GET /api/products")
        assert m.action_key == "review_endpoint"

    def test_check_endpoint(self):
        m = detect_intent("check endpoint /api/users")
        assert m.action_key == "review_endpoint"

    def test_harden_permissions(self):
        m = detect_intent("harden permissions on POST /api/admin")
        assert m.action_key == "harden_permissions"
        assert m.flow_type == "route"

    def test_secure_endpoint(self):
        m = detect_intent("secure endpoint /api/users")
        assert m.action_key == "harden_permissions"

    def test_security_route(self):
        m = detect_intent("security check on route /api/admin")
        assert m.action_key == "harden_permissions"

    def test_generate_examples(self):
        m = detect_intent("generate example requests")
        assert m.action_key == "generate_examples"
        assert m.flow_type == "route"

    def test_example_request(self):
        m = detect_intent("example request for GET /api/users")
        assert m.action_key == "generate_examples"

    def test_curl_endpoint(self):
        m = detect_intent("curl for endpoint /api/orders")
        assert m.action_key == "generate_examples"

    def test_sample_request(self):
        m = detect_intent("sample request for POST /api/users")
        assert m.action_key == "generate_examples"


# ═══════════════════════════════════════════════════════════════════════════
# detect_intent — query intents
# ═══════════════════════════════════════════════════════════════════════════


class TestQueryIntents:

    def test_explain_query(self):
        m = detect_intent("explain the query plan")
        assert m.action_key == "explain_plan"
        assert m.flow_type == "query"

    def test_explain_plan(self):
        m = detect_intent("explain plan for this query")
        assert m.action_key == "explain_plan"

    def test_query_performance(self):
        m = detect_intent("query performance analysis")
        assert m.action_key == "explain_plan"

    def test_analyse_query(self):
        m = detect_intent("analyse query performance")
        assert m.action_key == "explain_plan"

    def test_analyze_query(self):
        m = detect_intent("analyze query patterns")
        assert m.action_key == "explain_plan"

    def test_suggest_indexes(self):
        m = detect_intent("suggest indexes for users table")
        assert m.action_key == "suggest_indexes"
        assert m.flow_type == "query"

    def test_missing_indexes(self):
        m = detect_intent("find missing indexes")
        assert m.action_key == "suggest_indexes"

    def test_rewrite_query(self):
        m = detect_intent("rewrite query for better performance")
        assert m.action_key == "rewrite_suggestions"
        assert m.flow_type == "query"

    def test_optimize_query(self):
        m = detect_intent("optimize query for users")
        assert m.action_key == "rewrite_suggestions"

    def test_n_plus_one(self):
        m = detect_intent("detect N+1 issues")
        assert m.action_key == "rewrite_suggestions"


# ═══════════════════════════════════════════════════════════════════════════
# detect_intent — migration intents
# ═══════════════════════════════════════════════════════════════════════════


class TestMigrationIntents:

    def test_explain_migration(self):
        m = detect_intent("explain migration impact")
        assert m.action_key == "explain_migration"
        assert m.flow_type == "migration"

    def test_migration_risk(self):
        m = detect_intent("what is the migration risk")
        assert m.action_key == "explain_migration"

    def test_safe_rollout_plan(self):
        m = detect_intent("create a rollout plan")
        assert m.action_key == "safe_rollout_plan"
        assert m.flow_type == "migration"

    def test_safe_migration(self):
        m = detect_intent("safe migration strategy")
        assert m.action_key == "safe_rollout_plan"

    def test_deploy_migration(self):
        m = detect_intent("deploy migration safely")
        assert m.action_key == "safe_rollout_plan"


# ═══════════════════════════════════════════════════════════════════════════
# detect_intent — diagnostic intents
# ═══════════════════════════════════════════════════════════════════════════


class TestDiagnosticIntents:

    def test_diagnostic_prioritize(self):
        m = detect_intent("diagnostic prioritize issues")
        assert m.action_key == "diagnostic_prioritize"
        assert m.flow_type == "diagnostic"

    def test_diagnostic_prioritise_uk(self):
        m = detect_intent("diagnostic prioritise all issues")
        assert m.action_key == "diagnostic_prioritize"

    def test_triage_diagnostic(self):
        m = detect_intent("triage diagnostic findings")
        assert m.action_key == "diagnostic_prioritize"

    def test_diagnostic_explain(self):
        m = detect_intent("diagnostic explain the findings")
        assert m.action_key == "diagnostic_prioritize"

    def test_fix_diagnostic(self):
        m = detect_intent("fix diagnostic issues")
        assert m.action_key == "diagnostic_prioritize"


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_empty_string(self):
        m = detect_intent("")
        assert m.intent == "unknown"
        assert m.confidence == 0.0

    def test_whitespace_only(self):
        m = detect_intent("   ")
        assert m.intent == "unknown"

    def test_none_returns_unknown(self):
        m = detect_intent(None)
        assert m.intent == "unknown"

    def test_gibberish(self):
        m = detect_intent("xyzzy plugh")
        assert m.intent == "unknown"
        assert m.confidence == 0.0

    def test_single_word_low_confidence(self):
        m = detect_intent("explain")
        assert m.confidence <= 0.65  # generic fallback rule

    def test_confidence_below_zero(self):
        """Confidence should never be negative."""
        m = detect_intent("hello world")
        assert m.confidence >= 0.0

    def test_confidence_max_one(self):
        """Confidence is capped at 1.0."""
        m = detect_intent("explain model model model explain")
        assert m.confidence <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
# Context extraction
# ═══════════════════════════════════════════════════════════════════════════


class TestContextExtraction:

    def test_model_name_extracted(self):
        m = detect_intent("explain the User model")
        assert m.extracted_context.get("model_name") == "User"

    def test_model_name_product(self):
        m = detect_intent("explain the Product model")
        assert m.extracted_context.get("model_name") == "Product"

    def test_route_method_path(self):
        m = detect_intent("review GET /api/users")
        ctx = m.extracted_context
        assert ctx.get("method") == "GET"
        assert ctx.get("path") == "/api/users"

    def test_route_post(self):
        m = detect_intent("review POST /api/orders")
        ctx = m.extracted_context
        assert ctx.get("method") == "POST"

    def test_sql_extraction_backtick(self):
        ctx = _extract_context("explain query `SELECT * FROM users`", "query")
        assert "SELECT" in ctx.get("sql", "")

    def test_sql_extraction_colon(self):
        ctx = _extract_context("query: SELECT * FROM orders", "query")
        assert "SELECT" in ctx.get("sql", "")

    def test_migration_ref(self):
        ctx = _extract_context("explain migration auth/0003", "migration")
        assert ctx.get("app") == "auth"
        assert ctx.get("name") == "0003"

    def test_migration_no_app(self):
        ctx = _extract_context("explain migration 0005", "migration")
        assert ctx.get("name") == "0005"

    def test_issue_id(self):
        ctx = _extract_context("diagnostic issue #12", "diagnostic")
        assert ctx.get("issue_id") == "12"

    def test_issue_id_code(self):
        ctx = _extract_context("prioritize issue DX-001", "diagnostic")
        assert ctx.get("issue_id") == "DX-001"


# ═══════════════════════════════════════════════════════════════════════════
# list_intents
# ═══════════════════════════════════════════════════════════════════════════


class TestListIntents:

    def test_returns_list(self):
        result = list_intents()
        assert isinstance(result, list)

    def test_has_entries(self):
        result = list_intents()
        assert len(result) >= 11

    def test_entry_keys(self):
        result = list_intents()
        for entry in result:
            assert "action_key" in entry
            assert "flow_type" in entry
            assert "title" in entry
            assert "description" in entry

    def test_no_duplicates(self):
        result = list_intents()
        keys = [e["action_key"] for e in result]
        assert len(keys) == len(set(keys))

    def test_all_actions_present(self):
        result = list_intents()
        keys = {e["action_key"] for e in result}
        assert "explain_model" in keys
        assert "review_endpoint" in keys
        assert "suggest_indexes" in keys
        assert "explain_migration" in keys
        assert "diagnostic_prioritize" in keys


# ═══════════════════════════════════════════════════════════════════════════
# suggest_commands
# ═══════════════════════════════════════════════════════════════════════════


class TestSuggestCommands:

    def test_empty_prefix(self):
        result = suggest_commands("")
        assert len(result) <= 6
        assert len(result) > 0

    def test_prefix_explain(self):
        result = suggest_commands("explain")
        assert any("explain" in r.lower() for r in result)

    def test_prefix_review(self):
        result = suggest_commands("review")
        assert any("review" in r.lower() for r in result)

    def test_prefix_suggest(self):
        result = suggest_commands("suggest")
        assert any("suggest" in r.lower() for r in result)

    def test_max_six(self):
        result = suggest_commands("a")  # broad match
        assert len(result) <= 6

    def test_no_match(self):
        result = suggest_commands("xyzzy_no_match_here")
        assert result == []

    def test_case_insensitive(self):
        r1 = suggest_commands("Explain")
        r2 = suggest_commands("explain")
        assert r1 == r2


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE_COMMANDS integrity
# ═══════════════════════════════════════════════════════════════════════════


class TestExampleCommands:

    def test_not_empty(self):
        assert len(EXAMPLE_COMMANDS) >= 10

    def test_all_strings(self):
        for cmd in EXAMPLE_COMMANDS:
            assert isinstance(cmd, str)
            assert len(cmd) > 3


# ═══════════════════════════════════════════════════════════════════════════
# v0.5.36 — Intent Conflict Resolution Matrix
# ═══════════════════════════════════════════════════════════════════════════


class TestConflictResolution:
    """Ensure overlapping phrases route to the MOST SPECIFIC intent."""

    # ── Query-specific phrases must NOT be stolen by performance ──────────

    def test_query_performance_analysis_routes_to_query(self):
        """'query performance analysis' should match query/explain_plan."""
        m = detect_intent("query performance analysis")
        assert m.action_key == "explain_plan"

    def test_analyse_query_performance_routes_to_query(self):
        m = detect_intent("analyse query performance")
        assert m.action_key == "explain_plan"

    def test_missing_index_routes_to_query(self):
        """'find missing indexes' should go to query/suggest_indexes."""
        m = detect_intent("find missing indexes")
        assert m.action_key == "suggest_indexes"

    def test_missing_index_on_email(self):
        """'missing index on users.email' → suggest_indexes."""
        m = detect_intent("missing index on users.email")
        assert m.action_key == "suggest_indexes"

    def test_optimize_query_routes_to_rewrite(self):
        m = detect_intent("optimize query for users")
        assert m.action_key == "rewrite_suggestions"

    def test_n_plus_one_routes_to_rewrite(self):
        """Direct N+1 reference → query/rewrite_suggestions."""
        m = detect_intent("detect N+1 issues")
        assert m.action_key == "rewrite_suggestions"

    # ── Performance-specific phrases must route correctly ─────────────────

    def test_performance_analysis_routes_to_perf(self):
        m = detect_intent("performance analysis")
        assert m.flow_type == "performance_analysis"

    def test_analyze_performance_routes_to_perf(self):
        m = detect_intent("analyze performance")
        assert m.flow_type == "performance_analysis"

    def test_why_is_app_slow(self):
        m = detect_intent("why is my app slow")
        assert m.flow_type == "performance_analysis"

    def test_slow_endpoint(self):
        m = detect_intent("slow endpoint /api/orders")
        assert m.flow_type == "performance_analysis"

    def test_query_explosion(self):
        m = detect_intent("query explosion on /api/orders")
        assert m.flow_type == "performance_analysis"

    # ── Architecture phrases must NOT go to debug or performance ──────────

    def test_review_architecture_routes_to_arch(self):
        m = detect_intent("review my architecture")
        assert m.flow_type == "architecture_review"

    def test_architecture_review_not_debugger(self):
        m = detect_intent("architecture review")
        assert m.flow_type == "architecture_review"
        assert m.flow_type != "debug"

    def test_health_check_routes_to_arch(self):
        m = detect_intent("how healthy is my project")
        assert m.flow_type == "architecture_review"

    def test_anti_pattern_routes_to_arch(self):
        m = detect_intent("find anti-patterns")
        assert m.flow_type == "architecture_review"

    # ── Debug phrases must NOT be intercepted by other flows ──────────────

    def test_why_is_failing_routes_to_debug(self):
        m = detect_intent("why is /api/users failing")
        assert m.flow_type == "debug"

    def test_root_cause_routes_to_debug(self):
        m = detect_intent("find root cause")
        assert m.flow_type == "debug"

    def test_troubleshoot_routes_to_debug(self):
        m = detect_intent("troubleshoot the errors")
        assert m.flow_type == "debug"

    # ── Model phrases must remain with model intents ─────────────────────

    def test_explain_user_model_stays_model(self):
        m = detect_intent("explain User model")
        assert m.flow_type == "model"
        assert m.action_key == "explain_model"

    def test_refactor_model_stays_model(self):
        m = detect_intent("refactor Order model")
        assert m.flow_type == "model"
        assert m.action_key == "refactor_suggestions"

    # ── Confidence ordering: specific > generic ──────────────────────────

    def test_specific_higher_than_generic_explain(self):
        """'explain the User model' should have higher confidence than bare 'explain'."""
        specific = detect_intent("explain the User model")
        generic = detect_intent("explain")
        assert specific.confidence > generic.confidence

    def test_perf_higher_than_generic_review(self):
        specific = detect_intent("performance analysis")
        generic = detect_intent("review")
        assert specific.confidence > generic.confidence


# ═══════════════════════════════════════════════════════════════════════════
# v0.5.36 — Context Extraction for Debug/Arch/Perf flows
# ═══════════════════════════════════════════════════════════════════════════


class TestNewFlowContextExtraction:

    def test_debug_extracts_route(self):
        m = detect_intent("debug GET /api/users errors")
        assert m.flow_type == "debug"
        ctx = m.extracted_context
        assert ctx.get("method") == "GET"
        assert ctx.get("path") == "/api/users"

    def test_debug_extracts_model(self):
        m = detect_intent("debug Order model issues")
        assert m.flow_type == "debug"
        ctx = m.extracted_context
        assert ctx.get("model_name") == "Order"

    def test_arch_extracts_route(self):
        m = detect_intent("review architecture of GET /api/orders")
        ctx = m.extracted_context
        assert ctx.get("method") == "GET"
        assert ctx.get("path") == "/api/orders"

    def test_perf_extracts_route(self):
        m = detect_intent("why is GET /api/users slow")
        ctx = m.extracted_context
        assert ctx.get("method") == "GET"
        assert ctx.get("path") == "/api/users"
