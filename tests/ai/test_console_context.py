"""
v0.5.31 — AI Console Context Builder: unit tests.

Tests cover:
    - enrich_context() for each flow type
    - _enrich_model() — model name resolution, first-model fallback
    - _enrich_route() — default method
    - _enrich_query() — sql passthrough
    - _enrich_migration() — passthrough
    - _enrich_diagnostic() — passthrough
    - _resolve_model_name() — case-insensitive lookup
    - Edge cases: empty context, missing registry
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from aksara.ai.console_context import (
    enrich_context,
    _enrich_model,
    _enrich_route,
    _enrich_query,
    _enrich_migration,
    _enrich_diagnostic,
    _first_model_name,
    _resolve_model_name,
)


# ═══════════════════════════════════════════════════════════════════════════
# enrich_context dispatch
# ═══════════════════════════════════════════════════════════════════════════


class TestEnrichContext:

    def test_model_dispatch(self):
        ctx = enrich_context("model", {"model_name": "User"})
        assert "model_name" in ctx

    def test_route_dispatch(self):
        ctx = enrich_context("route", {"path": "/api/users"})
        assert ctx.get("method") is not None

    def test_query_dispatch(self):
        ctx = enrich_context("query", {"sql": "SELECT 1"})
        assert ctx.get("sql") == "SELECT 1"

    def test_migration_dispatch(self):
        ctx = enrich_context("migration", {"app": "auth", "name": "0001"})
        assert ctx.get("app") == "auth"

    def test_diagnostic_dispatch(self):
        ctx = enrich_context("diagnostic", {"issue_id": "DX-001"})
        assert ctx.get("issue_id") == "DX-001"

    def test_unknown_flow_type(self):
        ctx = enrich_context("magic", {"foo": "bar"})
        assert ctx.get("foo") == "bar"

    def test_empty_extracted(self):
        ctx = enrich_context("model", {})
        assert isinstance(ctx, dict)


# ═══════════════════════════════════════════════════════════════════════════
# _enrich_model
# ═══════════════════════════════════════════════════════════════════════════


class TestEnrichModel:

    def test_preserves_model_name(self):
        ctx = _enrich_model({"model_name": "User"})
        assert ctx["model_name"] == "User"

    def test_empty_model_name_tries_first(self):
        with patch("aksara.ai.console_context._first_model_name", return_value="Product"):
            ctx = _enrich_model({})
            assert ctx.get("model_name") == "Product"

    def test_empty_model_name_no_registry(self):
        with patch("aksara.ai.console_context._first_model_name", return_value=""):
            ctx = _enrich_model({})
            assert ctx.get("model_name", "") == ""

    def test_resolve_case_insensitive(self):
        with patch("aksara.ai.console_context._resolve_model_name", return_value="User"):
            ctx = _enrich_model({"model_name": "user"})
            assert ctx["model_name"] == "User"


# ═══════════════════════════════════════════════════════════════════════════
# _enrich_route
# ═══════════════════════════════════════════════════════════════════════════


class TestEnrichRoute:

    def test_default_method_get(self):
        ctx = _enrich_route({"path": "/api/users"})
        assert ctx["method"] == "GET"

    def test_preserves_method(self):
        ctx = _enrich_route({"path": "/api/users", "method": "POST"})
        assert ctx["method"] == "POST"

    def test_empty_path_default(self):
        ctx = _enrich_route({})
        assert ctx["path"] == ""


# ═══════════════════════════════════════════════════════════════════════════
# _enrich_query
# ═══════════════════════════════════════════════════════════════════════════


class TestEnrichQuery:

    def test_sql_passthrough(self):
        ctx = _enrich_query({"sql": "SELECT * FROM users"})
        assert ctx["sql"] == "SELECT * FROM users"

    def test_empty_sql_default(self):
        ctx = _enrich_query({})
        assert ctx["sql"] == ""


# ═══════════════════════════════════════════════════════════════════════════
# _enrich_migration & _enrich_diagnostic
# ═══════════════════════════════════════════════════════════════════════════


class TestEnrichMigration:

    def test_passthrough(self):
        ctx = _enrich_migration({"app": "auth", "name": "0001"})
        assert ctx == {"app": "auth", "name": "0001"}


class TestEnrichDiagnostic:

    def test_passthrough(self):
        ctx = _enrich_diagnostic({"issue_id": "DX-001"})
        assert ctx == {"issue_id": "DX-001"}


# ═══════════════════════════════════════════════════════════════════════════
# _first_model_name & _resolve_model_name
# ═══════════════════════════════════════════════════════════════════════════


class TestRegistryHelpers:

    def test_first_model_name_empty(self):
        """If registry has no models, return ''."""
        mock_reg = MagicMock()
        mock_reg._models = {}
        with patch("aksara.registry.ModelRegistry", mock_reg):
            assert _first_model_name() == ""

    def test_first_model_name_found(self):
        mock_reg = MagicMock()
        mock_reg._models = {"User": MagicMock(), "Product": MagicMock()}
        with patch("aksara.registry.ModelRegistry", mock_reg):
            result = _first_model_name()
            assert result in ("User", "Product")

    def test_resolve_exact(self):
        mock_reg = MagicMock()
        mock_reg._models = {"User": MagicMock()}
        with patch("aksara.registry.ModelRegistry", mock_reg):
            assert _resolve_model_name("User") == "User"

    def test_resolve_case_insensitive(self):
        mock_reg = MagicMock()
        mock_reg._models = {"User": MagicMock()}
        with patch("aksara.registry.ModelRegistry", mock_reg):
            assert _resolve_model_name("user") == "User"

    def test_resolve_not_found(self):
        mock_reg = MagicMock()
        mock_reg._models = {"User": MagicMock()}
        with patch("aksara.registry.ModelRegistry", mock_reg):
            assert _resolve_model_name("Nonexistent") == "Nonexistent"

    def test_resolve_exception_handling(self):
        with patch("aksara.registry.ModelRegistry", side_effect=Exception("boom")):
            assert _resolve_model_name("User") == "User"
