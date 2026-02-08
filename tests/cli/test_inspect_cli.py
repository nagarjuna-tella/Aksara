"""
Tests for `aksara inspect` CLI commands.

v0.5.21: Tests for `aksara inspect models` and `aksara inspect queries`.
"""

import pytest
import json
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from aksara.inspectors.models import (
    ModelInspectorField,
    ModelInspectorRelationship,
    ModelInspectorConstraint,
    ModelInspectorSummary,
)
from aksara.inspectors.queries import QueryStats


def _extract_json(output: str) -> str:
    """Extract JSON from CLI output that may contain header lines."""
    # Find first [ or { which starts the JSON
    for i, ch in enumerate(output):
        if ch in ('[', '{'):
            return output[i:]
    return output


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()


def _make_inspect_result(name="User", table="users", num_fields=3, num_rels=1):
    """Create a mock ModelInspectorSummary."""
    return ModelInspectorSummary(
        name=name,
        table_name=table,
        app_label="core",
        num_fields=num_fields,
        num_relationships=num_rels,
        has_timestamps=True,
        pk_field="id",
        pk_type="AutoField",
        fields=[
            ModelInspectorField(
                name="id", column_name="id", field_type="AutoField",
                python_type="int", primary_key=True, auto_generated="Primary key",
            ),
            ModelInspectorField(
                name="name", column_name="name", field_type="CharField",
                python_type="str", max_length=100,
            ),
            ModelInspectorField(
                name="email", column_name="email", field_type="CharField",
                python_type="str", unique=True, ai_sensitive=True,
                auto_generated="Unique; ⚠️ Sensitive",
            ),
        ],
        relationships=[
            ModelInspectorRelationship(
                field_name="role", kind="fk", target_model="Role",
                on_delete="CASCADE",
            ),
        ],
        constraints=[
            ModelInspectorConstraint(kind="primary_key", columns=["id"]),
            ModelInspectorConstraint(kind="unique", columns=["email"]),
        ],
        comments=["✓ Timestamps (created_at, updated_at) detected", "Relations: 1 FK(s)"],
    )


def _make_query_stats():
    """Create a mock QueryStats result."""
    return QueryStats(
        total_queries=42,
        total_batches=10,
        total_slow_queries=2,
        avg_duration_ms=15.6,
        max_duration_ms=250.0,
        slow_threshold_ms=100.0,
        top_slow=[
            {"sql": "SELECT * FROM users WHERE active = true", "duration_ms": 250.0,
             "table": "users", "operation": "SELECT"},
            {"sql": "UPDATE posts SET views = views + 1", "duration_ms": 120.0,
             "table": "posts", "operation": "UPDATE"},
        ],
        n_plus_one_count=1,
        by_operation={"SELECT": 30, "INSERT": 8, "UPDATE": 4},
    )


# =============================================================================
# inspect models tests
# =============================================================================


class TestInspectModelsCommand:
    """Tests for `aksara inspect models`."""

    @patch("aksara.inspectors.models.inspect_all_models")
    def test_list_all_models(self, mock_all, runner):
        from aksara.cli.main import cli
        mock_all.return_value = [_make_inspect_result()]
        result = runner.invoke(cli, ["inspect", "models"])
        assert result.exit_code == 0
        assert "User" in result.output
        assert "users" in result.output

    @patch("aksara.inspectors.models.inspect_all_models")
    def test_list_empty(self, mock_all, runner):
        from aksara.cli.main import cli
        mock_all.return_value = []
        result = runner.invoke(cli, ["inspect", "models"])
        assert result.exit_code == 0
        assert "No models" in result.output

    @patch("aksara.registry.ModelRegistry")
    @patch("aksara.inspectors.models.inspect_model")
    def test_single_model(self, mock_inspect, mock_registry, runner):
        from aksara.cli.main import cli
        mock_model = MagicMock()
        mock_registry.get.return_value = mock_model
        mock_inspect.return_value = _make_inspect_result()
        result = runner.invoke(cli, ["inspect", "models", "--model", "User"])
        assert result.exit_code == 0
        assert "User" in result.output

    @patch("aksara.registry.ModelRegistry")
    def test_single_model_not_found(self, mock_registry, runner):
        from aksara.cli.main import cli
        mock_registry.get.side_effect = KeyError("User")
        mock_registry.all.return_value = {}
        result = runner.invoke(cli, ["inspect", "models", "--model", "NoExist"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    @patch("aksara.inspectors.models.inspect_all_models")
    def test_json_output(self, mock_all, runner):
        from aksara.cli.main import cli
        mock_all.return_value = [_make_inspect_result()]
        result = runner.invoke(cli, ["inspect", "models", "--json"])
        assert result.exit_code == 0
        # Extract JSON from output (skip header lines)
        json_str = _extract_json(result.output)
        data = json.loads(json_str)
        assert isinstance(data, list)
        assert data[0]["name"] == "User"

    @patch("aksara.registry.ModelRegistry")
    @patch("aksara.inspectors.models.inspect_model")
    def test_json_single_model(self, mock_inspect, mock_registry, runner):
        from aksara.cli.main import cli
        mock_model = MagicMock()
        mock_registry.get.return_value = mock_model
        mock_inspect.return_value = _make_inspect_result()
        result = runner.invoke(cli, ["inspect", "models", "--model", "User", "--json"])
        assert result.exit_code == 0
        json_str = _extract_json(result.output)
        data = json.loads(json_str)
        assert isinstance(data, dict)
        assert data["name"] == "User"

    @patch("aksara.inspectors.models.inspect_all_models")
    def test_fields_flag(self, mock_all, runner):
        from aksara.cli.main import cli
        mock_all.return_value = [_make_inspect_result()]
        result = runner.invoke(cli, ["inspect", "models", "--fields"])
        assert result.exit_code == 0
        assert "Fields:" in result.output
        assert "AutoField" in result.output

    @patch("aksara.inspectors.models.inspect_all_models")
    def test_relationships_flag(self, mock_all, runner):
        from aksara.cli.main import cli
        mock_all.return_value = [_make_inspect_result()]
        result = runner.invoke(cli, ["inspect", "models", "--relationships"])
        assert result.exit_code == 0
        assert "Relationships:" in result.output
        assert "Role" in result.output

    @patch("aksara.inspectors.models.inspect_all_models")
    def test_shows_timestamps(self, mock_all, runner):
        from aksara.cli.main import cli
        r = _make_inspect_result()
        mock_all.return_value = [r]
        result = runner.invoke(cli, ["inspect", "models"])
        assert "Timestamps" in result.output

    @patch("aksara.inspectors.models.inspect_all_models")
    def test_shows_pk(self, mock_all, runner):
        from aksara.cli.main import cli
        mock_all.return_value = [_make_inspect_result()]
        result = runner.invoke(cli, ["inspect", "models"])
        assert "PK: id" in result.output

    @patch("aksara.inspectors.models.inspect_all_models")
    def test_shows_total_count(self, mock_all, runner):
        from aksara.cli.main import cli
        mock_all.return_value = [_make_inspect_result(), _make_inspect_result("Post", "posts")]
        result = runner.invoke(cli, ["inspect", "models"])
        assert "2 model(s)" in result.output

    @patch("aksara.inspectors.models.inspect_all_models")
    def test_shows_comments(self, mock_all, runner):
        from aksara.cli.main import cli
        mock_all.return_value = [_make_inspect_result()]
        result = runner.invoke(cli, ["inspect", "models"])
        assert "FK" in result.output


# =============================================================================
# inspect queries tests
# =============================================================================


class TestInspectQueriesCommand:
    """Tests for `aksara inspect queries`."""

    @patch("aksara.inspectors.queries.get_query_stats")
    def test_basic_output(self, mock_stats, runner):
        from aksara.cli.main import cli
        mock_stats.return_value = _make_query_stats()
        result = runner.invoke(cli, ["inspect", "queries"])
        assert result.exit_code == 0
        assert "42" in result.output  # total queries
        assert "250.00" in result.output  # max duration

    @patch("aksara.inspectors.queries.get_query_stats")
    def test_json_output(self, mock_stats, runner):
        from aksara.cli.main import cli
        mock_stats.return_value = _make_query_stats()
        result = runner.invoke(cli, ["inspect", "queries", "--json"])
        assert result.exit_code == 0
        json_str = _extract_json(result.output)
        data = json.loads(json_str)
        assert data["total_queries"] == 42
        assert data["total_slow_queries"] == 2

    @patch("aksara.inspectors.queries.get_query_stats")
    def test_limit_flag(self, mock_stats, runner):
        from aksara.cli.main import cli
        mock_stats.return_value = _make_query_stats()
        result = runner.invoke(cli, ["inspect", "queries", "--limit", "5"])
        assert result.exit_code == 0
        mock_stats.assert_called_with(limit_slow=5)

    @patch("aksara.inspectors.queries.get_query_stats")
    def test_shows_by_operation(self, mock_stats, runner):
        from aksara.cli.main import cli
        mock_stats.return_value = _make_query_stats()
        result = runner.invoke(cli, ["inspect", "queries"])
        assert "SELECT" in result.output
        assert "INSERT" in result.output

    @patch("aksara.inspectors.queries.get_query_stats")
    def test_shows_slow_queries(self, mock_stats, runner):
        from aksara.cli.main import cli
        mock_stats.return_value = _make_query_stats()
        result = runner.invoke(cli, ["inspect", "queries"])
        assert "Slow" in result.output
        assert "users" in result.output

    @patch("aksara.inspectors.queries.get_query_stats")
    def test_shows_n_plus_one(self, mock_stats, runner):
        from aksara.cli.main import cli
        mock_stats.return_value = _make_query_stats()
        result = runner.invoke(cli, ["inspect", "queries"])
        assert "1" in result.output  # n+1 count

    @patch("aksara.inspectors.queries.get_query_stats")
    def test_empty_stats(self, mock_stats, runner):
        from aksara.cli.main import cli
        mock_stats.return_value = QueryStats()
        result = runner.invoke(cli, ["inspect", "queries"])
        assert result.exit_code == 0
        assert "No query data" in result.output

    @patch("aksara.inspectors.queries.get_query_stats")
    def test_shows_threshold(self, mock_stats, runner):
        from aksara.cli.main import cli
        mock_stats.return_value = _make_query_stats()
        result = runner.invoke(cli, ["inspect", "queries"])
        assert "100.0" in result.output  # threshold


# =============================================================================
# inspect group tests
# =============================================================================


class TestInspectGroup:
    """Tests for the inspect command group itself."""

    def test_help(self, runner):
        from aksara.cli.main import cli
        result = runner.invoke(cli, ["inspect", "--help"])
        assert result.exit_code == 0
        assert "models" in result.output
        assert "queries" in result.output

    def test_models_help(self, runner):
        from aksara.cli.main import cli
        result = runner.invoke(cli, ["inspect", "models", "--help"])
        assert result.exit_code == 0
        assert "--model" in result.output
        assert "--json" in result.output
        assert "--fields" in result.output

    def test_queries_help(self, runner):
        from aksara.cli.main import cli
        result = runner.invoke(cli, ["inspect", "queries", "--help"])
        assert result.exit_code == 0
        assert "--limit" in result.output
        assert "--json" in result.output
