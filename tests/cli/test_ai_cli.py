"""
Tests for AI CLI Commands (v0.4.8)

Comprehensive test coverage for:
- aksara ai context
- aksara ai schema-health
- aksara ai schema-issues
- aksara ai plan preview
- aksara ai plan apply
- aksara ai plan template
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from aksara.cli.main import (
    cli,
    ai,
    ai_context,
    ai_schema_health,
    ai_schema_issues,
    plan,
    plan_preview,
    plan_apply,
    plan_template,
    _setup_app_for_cli,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_app():
    """Create a mock FastAPI app."""
    app = MagicMock()
    app.state = MagicMock()
    return app


@pytest.fixture
def sample_plan_json():
    """Sample plan JSON for testing."""
    return {
        "intent": {
            "user_message": "Add a Category model",
            "mode": "modify"
        },
        "plan": {
            "intent": "Add a Category model to the blog app",
            "steps": [
                {
                    "id": "step_1",
                    "type": "analyze_context",
                    "description": "Analyze current state",
                    "payload": {}
                }
            ]
        }
    }


@pytest.fixture
def mock_context_bundle():
    """Create a mock context bundle."""
    from aksara.ai.agent import AgentIntent, AgentContextBundle
    
    return AgentContextBundle(
        intent=AgentIntent(user_message="Test intent", mode="modify"),
        full_context={
            "models": [{"name": "User"}, {"name": "Article"}],
            "viewsets": [{"name": "UserViewSet"}],
            "routes": [{"path": "/users"}],
            "migrations": [],
        },
        tools=[{"name": "test_tool"}],
        plan_schema={"type": "object"},
        patch_schema={"type": "object"},
        query_plan_schema={"type": "object"},
        codegen_schema={"type": "object"},
        version="0.4.8",
    )


@pytest.fixture
def mock_schema_health():
    """Create a mock schema health result."""
    from aksara.ai.schema_doctor import AiSchemaHealth
    
    return AiSchemaHealth(
        status="healthy",
        issue_counts={"info": 0, "warning": 0, "danger": 0},
        issues=[],
        inspected_at="2026-01-25T12:00:00Z",
        db_version="PostgreSQL 16.1",
        db_name="test_db",
        app_version="0.4.8",
    )


@pytest.fixture
def mock_schema_health_with_issues():
    """Create a mock schema health result with issues."""
    from aksara.ai.schema_doctor import AiSchemaHealth, AiSchemaIssue
    
    return AiSchemaHealth(
        status="danger",
        issue_counts={"info": 0, "warning": 1, "danger": 1},
        issues=[
            AiSchemaIssue(
                id="blog.Article.slug.missing_column",
                kind="missing_column",
                severity="danger",
                app_label="blog",
                model="Article",
                table="blog_articles",
                column="slug",
                message="Column 'slug' is missing from table",
                hint="Run migrations",
            ),
            AiSchemaIssue(
                id="auth.User.old_field.extra_column",
                kind="extra_column",
                severity="warning",
                app_label="auth",
                model="User",
                table="auth_users",
                column="old_field",
                message="Column 'old_field' exists but not in model",
                hint="Remove column or add field",
            ),
        ],
        inspected_at="2026-01-25T12:00:00Z",
        db_version="PostgreSQL 16.1",
        db_name="test_db",
        app_version="0.4.8",
    )


@pytest.fixture
def mock_plan_execution_success():
    """Create a mock successful plan execution result."""
    from aksara.ai.planner import AiPlanExecutionResult, AiPlanStepResult
    
    return AiPlanExecutionResult(
        success=True,
        steps=[
            AiPlanStepResult(
                id="step_1",
                type="analyze_context",
                success=True,
            )
        ],
        notes=["Plan executed successfully"],
        dry_run=True,
    )


@pytest.fixture
def mock_plan_execution_failure():
    """Create a mock failed plan execution result."""
    from aksara.ai.planner import AiPlanExecutionResult, AiPlanStepResult
    
    return AiPlanExecutionResult(
        success=False,
        steps=[
            AiPlanStepResult(
                id="step_1",
                type="analyze_context",
                success=False,
                error="Something went wrong",
            )
        ],
        notes=["Plan failed"],
        dry_run=True,
    )


# =============================================================================
# Test ai group
# =============================================================================

class TestAiCommandGroup:
    """Tests for the ai command group."""
    
    def test_ai_group_exists(self, runner):
        """ai group should be accessible."""
        result = runner.invoke(cli, ["ai", "--help"])
        assert result.exit_code == 0
        assert "AI-powered development commands" in result.output
    
    def test_ai_group_lists_commands(self, runner):
        """ai group should list subcommands."""
        result = runner.invoke(cli, ["ai", "--help"])
        assert "context" in result.output
        assert "schema-health" in result.output
        assert "schema-issues" in result.output
        assert "plan" in result.output


# =============================================================================
# Test ai context command
# =============================================================================

class TestAiContextCommand:
    """Tests for aksara ai context."""
    
    def test_context_requires_intent(self, runner):
        """context command should require --intent or --stdin."""
        result = runner.invoke(cli, ["ai", "context"])
        assert result.exit_code == 1
        assert "Error" in result.output
    
    def test_context_with_intent_summary(self, runner, mock_context_bundle):
        """context command with --intent should output summary."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.agent.build_agent_context_bundle", new_callable=AsyncMock) as mock_build:
                    mock_build.return_value = mock_context_bundle
                    
                    result = runner.invoke(cli, [
                        "ai", "context",
                        "--intent", "Add a Category model",
                        "--format", "summary"
                    ])
                    
                    assert result.exit_code == 0
                    assert "Context Summary" in result.output
                    assert "Models:" in result.output
    
    def test_context_with_intent_json(self, runner, mock_context_bundle):
        """context command with --format json should output valid JSON."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.agent.build_agent_context_bundle", new_callable=AsyncMock) as mock_build:
                    mock_build.return_value = mock_context_bundle
                    
                    result = runner.invoke(cli, [
                        "ai", "context",
                        "--intent", "Test intent",
                        "--format", "json"
                    ])
                    
                    assert result.exit_code == 0
                    data = json.loads(result.output)
                    assert "intent" in data
                    assert "full_context" in data
                    assert "version" in data
    
    def test_context_with_mode(self, runner, mock_context_bundle):
        """context command should accept --mode option."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.agent.build_agent_context_bundle", new_callable=AsyncMock) as mock_build:
                    mock_build.return_value = mock_context_bundle
                    
                    result = runner.invoke(cli, [
                        "ai", "context",
                        "--intent", "Read app structure",
                        "--mode", "read"
                    ])
                    
                    assert result.exit_code == 0
                    assert "Mode:" in result.output
                    assert "read" in result.output
    
    def test_context_with_scope(self, runner, mock_context_bundle):
        """context command should accept --scope option."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.agent.build_agent_context_bundle", new_callable=AsyncMock) as mock_build:
                    mock_build.return_value = mock_context_bundle
                    
                    result = runner.invoke(cli, [
                        "ai", "context",
                        "--intent", "Test intent",
                        "--scope", "models,routes"
                    ])
                    
                    assert result.exit_code == 0
                    assert "Scope:" in result.output
    
    def test_context_with_stdin(self, runner, mock_context_bundle):
        """context command should read intent from stdin."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.agent.build_agent_context_bundle", new_callable=AsyncMock) as mock_build:
                    mock_build.return_value = mock_context_bundle
                    
                    result = runner.invoke(cli, [
                        "ai", "context",
                        "--stdin"
                    ], input="Add a new model")
                    
                    assert result.exit_code == 0
    
    def test_context_empty_intent_fails(self, runner):
        """context command should fail with empty intent."""
        result = runner.invoke(cli, [
            "ai", "context",
            "--stdin"
        ], input="")
        
        assert result.exit_code == 1
        assert "Error" in result.output


# =============================================================================
# Test ai schema-health command
# =============================================================================

class TestAiSchemaHealthCommand:
    """Tests for aksara ai schema-health."""
    
    def test_schema_health_table_format(self, runner, mock_schema_health):
        """schema-health should output table format by default."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.schema_doctor.analyze_schema_health", new_callable=AsyncMock) as mock_analyze:
                    mock_analyze.return_value = mock_schema_health
                    
                    result = runner.invoke(cli, ["ai", "schema-health"])
                    
                    assert result.exit_code == 0
                    assert "Status:" in result.output
                    assert "HEALTHY" in result.output
    
    def test_schema_health_json_format(self, runner, mock_schema_health):
        """schema-health with --format json should output valid JSON."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.schema_doctor.analyze_schema_health", new_callable=AsyncMock) as mock_analyze:
                    mock_analyze.return_value = mock_schema_health
                    
                    result = runner.invoke(cli, ["ai", "schema-health", "--format", "json"])
                    
                    assert result.exit_code == 0
                    data = json.loads(result.output)
                    assert data["status"] == "healthy"
                    assert "issue_counts" in data
    
    def test_schema_health_danger_exit_code(self, runner, mock_schema_health_with_issues):
        """schema-health should exit with code 1 if status is danger."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.schema_doctor.analyze_schema_health", new_callable=AsyncMock) as mock_analyze:
                    mock_analyze.return_value = mock_schema_health_with_issues
                    
                    result = runner.invoke(cli, ["ai", "schema-health"])
                    
                    assert result.exit_code == 1
                    assert "DANGER" in result.output
    
    def test_schema_health_shows_counts(self, runner, mock_schema_health_with_issues):
        """schema-health should display issue counts."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.schema_doctor.analyze_schema_health", new_callable=AsyncMock) as mock_analyze:
                    mock_analyze.return_value = mock_schema_health_with_issues
                    
                    result = runner.invoke(cli, ["ai", "schema-health"])
                    
                    assert "Warning:" in result.output or "warning" in result.output.lower()
                    assert "Danger:" in result.output or "danger" in result.output.lower()


# =============================================================================
# Test ai schema-issues command
# =============================================================================

class TestAiSchemaIssuesCommand:
    """Tests for aksara ai schema-issues."""
    
    def test_schema_issues_no_issues(self, runner, mock_schema_health):
        """schema-issues should show no issues message."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.schema_doctor.analyze_schema_health", new_callable=AsyncMock) as mock_analyze:
                    mock_analyze.return_value = mock_schema_health
                    
                    result = runner.invoke(cli, ["ai", "schema-issues"])
                    
                    assert result.exit_code == 0
                    assert "No issues found" in result.output
    
    def test_schema_issues_with_issues(self, runner, mock_schema_health_with_issues):
        """schema-issues should list issues."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.schema_doctor.analyze_schema_health", new_callable=AsyncMock) as mock_analyze:
                    mock_analyze.return_value = mock_schema_health_with_issues
                    
                    result = runner.invoke(cli, ["ai", "schema-issues"])
                    
                    assert result.exit_code == 0
                    assert "2 found" in result.output
    
    def test_schema_issues_filter_severity(self, runner, mock_schema_health_with_issues):
        """schema-issues should filter by severity."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.schema_doctor.analyze_schema_health", new_callable=AsyncMock) as mock_analyze:
                    mock_analyze.return_value = mock_schema_health_with_issues
                    
                    result = runner.invoke(cli, ["ai", "schema-issues", "--severity", "danger"])
                    
                    assert result.exit_code == 0
                    assert "1 found" in result.output
    
    def test_schema_issues_filter_kind(self, runner, mock_schema_health_with_issues):
        """schema-issues should filter by kind."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.schema_doctor.analyze_schema_health", new_callable=AsyncMock) as mock_analyze:
                    mock_analyze.return_value = mock_schema_health_with_issues
                    
                    result = runner.invoke(cli, ["ai", "schema-issues", "--kind", "missing_column"])
                    
                    assert result.exit_code == 0
                    assert "1 found" in result.output
    
    def test_schema_issues_json_format(self, runner, mock_schema_health_with_issues):
        """schema-issues with --format json should output valid JSON."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.schema_doctor.analyze_schema_health", new_callable=AsyncMock) as mock_analyze:
                    mock_analyze.return_value = mock_schema_health_with_issues
                    
                    result = runner.invoke(cli, ["ai", "schema-issues", "--format", "json"])
                    
                    assert result.exit_code == 0
                    data = json.loads(result.output)
                    assert isinstance(data, list)
                    assert len(data) == 2
    
    def test_schema_issues_invalid_severity(self, runner):
        """schema-issues should reject invalid severity."""
        result = runner.invoke(cli, ["ai", "schema-issues", "--severity", "invalid"])
        
        assert result.exit_code == 1
        assert "Error" in result.output
    
    def test_schema_issues_filter_by_table(self, runner, mock_schema_health_with_issues):
        """schema-issues should filter by table name."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.schema_doctor.analyze_schema_health", new_callable=AsyncMock) as mock_analyze:
                    mock_analyze.return_value = mock_schema_health_with_issues
                    
                    result = runner.invoke(cli, ["ai", "schema-issues", "--table", "blog_articles"])
                    
                    assert result.exit_code == 0
                    assert "1 found" in result.output
    
    def test_schema_issues_filter_by_app_label(self, runner, mock_schema_health_with_issues):
        """schema-issues should filter by app label."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.schema_doctor.analyze_schema_health", new_callable=AsyncMock) as mock_analyze:
                    mock_analyze.return_value = mock_schema_health_with_issues
                    
                    result = runner.invoke(cli, ["ai", "schema-issues", "--app-label", "auth"])
                    
                    assert result.exit_code == 0
                    assert "1 found" in result.output


# =============================================================================
# Test ai plan subgroup
# =============================================================================

class TestAiPlanCommandGroup:
    """Tests for the ai plan command group."""
    
    def test_plan_group_exists(self, runner):
        """plan group should be accessible."""
        result = runner.invoke(cli, ["ai", "plan", "--help"])
        assert result.exit_code == 0
        assert "preview" in result.output
        assert "apply" in result.output
        assert "template" in result.output


# =============================================================================
# Test ai plan preview command
# =============================================================================

class TestAiPlanPreviewCommand:
    """Tests for aksara ai plan preview."""
    
    def test_plan_preview_from_file(self, runner, sample_plan_json, mock_plan_execution_success, tmp_path):
        """plan preview should read from file."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(sample_plan_json))
        
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.planner.execute_plan", new_callable=AsyncMock) as mock_execute:
                    mock_execute.return_value = mock_plan_execution_success
                    
                    result = runner.invoke(cli, ["ai", "plan", "preview", str(plan_file)])
                    
                    assert result.exit_code == 0
                    assert "WOULD SUCCEED" in result.output
    
    def test_plan_preview_from_stdin(self, runner, sample_plan_json, mock_plan_execution_success):
        """plan preview should read from stdin with -."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.planner.execute_plan", new_callable=AsyncMock) as mock_execute:
                    mock_execute.return_value = mock_plan_execution_success
                    
                    result = runner.invoke(
                        cli, 
                        ["ai", "plan", "preview", "-"],
                        input=json.dumps(sample_plan_json)
                    )
                    
                    assert result.exit_code == 0
    
    def test_plan_preview_json_format(self, runner, sample_plan_json, mock_plan_execution_success, tmp_path):
        """plan preview with --format json should output valid JSON."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(sample_plan_json))
        
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.planner.execute_plan", new_callable=AsyncMock) as mock_execute:
                    mock_execute.return_value = mock_plan_execution_success
                    
                    result = runner.invoke(cli, [
                        "ai", "plan", "preview", str(plan_file), "--format", "json"
                    ])
                    
                    assert result.exit_code == 0
                    data = json.loads(result.output)
                    assert "execution" in data
                    assert "intent" in data
    
    def test_plan_preview_failure_exit_code(self, runner, sample_plan_json, mock_plan_execution_failure, tmp_path):
        """plan preview should exit with code 1 on failure."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(sample_plan_json))
        
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.planner.execute_plan", new_callable=AsyncMock) as mock_execute:
                    mock_execute.return_value = mock_plan_execution_failure
                    
                    result = runner.invoke(cli, ["ai", "plan", "preview", str(plan_file)])
                    
                    assert result.exit_code == 1
                    assert "WOULD FAIL" in result.output
    
    def test_plan_preview_invalid_json(self, runner, tmp_path):
        """plan preview should fail with invalid JSON."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text("not valid json")
        
        result = runner.invoke(cli, ["ai", "plan", "preview", str(plan_file)])
        
        assert result.exit_code == 1
        assert "Invalid JSON" in result.output
    
    def test_plan_preview_file_not_found(self, runner):
        """plan preview should fail if file not found."""
        result = runner.invoke(cli, ["ai", "plan", "preview", "nonexistent.json"])
        
        assert result.exit_code == 1
        assert "not found" in result.output
    
    def test_plan_preview_missing_plan_key(self, runner, tmp_path):
        """plan preview should fail if plan key is missing."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps({"intent": {"user_message": "test"}}))
        
        result = runner.invoke(cli, ["ai", "plan", "preview", str(plan_file)])
        
        assert result.exit_code == 1
        assert "plan" in result.output.lower()
    
    def test_plan_preview_shows_step_results(self, runner, sample_plan_json, mock_plan_execution_success, tmp_path):
        """plan preview should show step results."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(sample_plan_json))
        
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.planner.execute_plan", new_callable=AsyncMock) as mock_execute:
                    mock_execute.return_value = mock_plan_execution_success
                    
                    result = runner.invoke(cli, ["ai", "plan", "preview", str(plan_file)])
                    
                    assert "Step Results" in result.output
                    assert "step_1" in result.output


# =============================================================================
# Test ai plan apply command
# =============================================================================

class TestAiPlanApplyCommand:
    """Tests for aksara ai plan apply."""
    
    def test_plan_apply_requires_confirmation(self, runner, sample_plan_json, tmp_path):
        """plan apply should require confirmation without --yes."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(sample_plan_json))
        
        result = runner.invoke(cli, ["ai", "plan", "apply", str(plan_file)], input="n\n")
        
        assert "Aborted" in result.output or result.exit_code == 0
    
    def test_plan_apply_with_yes_flag(self, runner, sample_plan_json, mock_plan_execution_success, tmp_path):
        """plan apply with --yes should skip confirmation."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(sample_plan_json))
        
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.planner.execute_plan", new_callable=AsyncMock) as mock_execute:
                    mock_execute.return_value = mock_plan_execution_success
                    
                    result = runner.invoke(cli, ["ai", "plan", "apply", str(plan_file), "--yes"])
                    
                    assert result.exit_code == 0
                    assert "SUCCESS" in result.output
    
    def test_plan_apply_calls_execute_with_dry_run_false(self, runner, sample_plan_json, mock_plan_execution_success, tmp_path):
        """plan apply should call execute_plan with dry_run=False."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(sample_plan_json))
        
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.planner.execute_plan", new_callable=AsyncMock) as mock_execute:
                    mock_execute.return_value = mock_plan_execution_success
                    
                    result = runner.invoke(cli, ["ai", "plan", "apply", str(plan_file), "--yes"])
                    
                    # Check that execute_plan was called with dry_run=False
                    call_args = mock_execute.call_args
                    assert call_args[1]["dry_run"] is False
    
    def test_plan_apply_failure_exit_code(self, runner, sample_plan_json, mock_plan_execution_failure, tmp_path):
        """plan apply should exit with code 1 on failure."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(sample_plan_json))
        
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.planner.execute_plan", new_callable=AsyncMock) as mock_execute:
                    mock_execute.return_value = mock_plan_execution_failure
                    
                    result = runner.invoke(cli, ["ai", "plan", "apply", str(plan_file), "--yes"])
                    
                    assert result.exit_code == 1
                    assert "FAILED" in result.output
    
    def test_plan_apply_json_format(self, runner, sample_plan_json, mock_plan_execution_success, tmp_path):
        """plan apply with --format json should output valid JSON."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(sample_plan_json))
        
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.planner.execute_plan", new_callable=AsyncMock) as mock_execute:
                    mock_execute.return_value = mock_plan_execution_success
                    
                    result = runner.invoke(cli, [
                        "ai", "plan", "apply", str(plan_file), "--yes", "--format", "json"
                    ])
                    
                    assert result.exit_code == 0
                    data = json.loads(result.output)
                    assert "execution" in data
    
    def test_plan_apply_from_stdin(self, runner, sample_plan_json, mock_plan_execution_success):
        """plan apply should read from stdin with -."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.planner.execute_plan", new_callable=AsyncMock) as mock_execute:
                    mock_execute.return_value = mock_plan_execution_success
                    
                    result = runner.invoke(
                        cli, 
                        ["ai", "plan", "apply", "-", "--yes"],
                        input=json.dumps(sample_plan_json)
                    )
                    
                    assert result.exit_code == 0


# =============================================================================
# Test ai plan template command
# =============================================================================

class TestAiPlanTemplateCommand:
    """Tests for aksara ai plan template."""
    
    def test_plan_template_requires_intent(self, runner):
        """plan template should require --intent."""
        result = runner.invoke(cli, ["ai", "plan", "template"])
        
        assert result.exit_code != 0
    
    def test_plan_template_outputs_valid_json(self, runner):
        """plan template should output valid JSON."""
        result = runner.invoke(cli, [
            "ai", "plan", "template",
            "--intent", "Add a Category model"
        ])
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "intent" in data
        assert "plan" in data
    
    def test_plan_template_includes_intent(self, runner):
        """plan template should include the provided intent."""
        result = runner.invoke(cli, [
            "ai", "plan", "template",
            "--intent", "Add slug field to Article"
        ])
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["intent"]["user_message"] == "Add slug field to Article"
        assert data["plan"]["intent"] == "Add slug field to Article"
    
    def test_plan_template_with_mode(self, runner):
        """plan template should respect --mode option."""
        result = runner.invoke(cli, [
            "ai", "plan", "template",
            "--intent", "Read app structure",
            "--mode", "read"
        ])
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["intent"]["mode"] == "read"
    
    def test_plan_template_includes_schema(self, runner):
        """plan template with --include-schema should include schema."""
        result = runner.invoke(cli, [
            "ai", "plan", "template",
            "--intent", "Add a model",
            "--include-schema"
        ])
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "_plan_schema" in data
    
    def test_plan_template_empty_steps(self, runner):
        """plan template should have a starter step."""
        result = runner.invoke(cli, [
            "ai", "plan", "template",
            "--intent", "Add a model"
        ])
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["plan"]["steps"]) >= 1


# =============================================================================
# Test _setup_app_for_cli helper
# =============================================================================

class TestSetupAppForCli:
    """Tests for the _setup_app_for_cli helper."""
    
    def test_setup_returns_fastapi_app(self):
        """_setup_app_for_cli should return a FastAPI instance."""
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.apps = []
            
            app = _setup_app_for_cli()
            
            # Check it's FastAPI-like (has state)
            assert hasattr(app, "state")
    
    def test_setup_discovers_models(self):
        """_setup_app_for_cli should attempt to discover models."""
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.apps = ["myapp"]
            
            with patch("importlib.import_module") as mock_import:
                mock_import.side_effect = ImportError("No module")
                
                app = _setup_app_for_cli()
                
                # Should have tried to import myapp.models
                mock_import.assert_called_with("myapp.models")


# =============================================================================
# Test CLI version consistency
# =============================================================================

class TestCliVersion:
    """Tests for CLI version."""
    
    def test_version_matches_init(self):
        """CLI version should match aksara.__version__."""
        from aksara import __version__
        from aksara.cli.main import CLI_VERSION
        
        assert CLI_VERSION == __version__
    
    def test_version_command(self, runner):
        """--version should show version."""
        from aksara import __version__
        
        result = runner.invoke(cli, ["--version"])
        
        assert result.exit_code == 0
        assert __version__ in result.output


# =============================================================================
# Additional edge case tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_ai_context_handles_exception(self, runner):
        """ai context should handle exceptions gracefully."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.side_effect = Exception("Setup failed")
            
            result = runner.invoke(cli, ["ai", "context", "--intent", "test"])
            
            assert result.exit_code == 1
            assert "Error" in result.output
    
    def test_ai_schema_health_handles_exception(self, runner):
        """ai schema-health should handle exceptions gracefully."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.side_effect = Exception("Setup failed")
            
            result = runner.invoke(cli, ["ai", "schema-health"])
            
            assert result.exit_code == 1
            assert "Error" in result.output
    
    def test_plan_preview_handles_validation_errors(self, runner, tmp_path):
        """plan preview should handle plan validation errors."""
        # Create a plan with invalid step type
        invalid_plan = {
            "intent": {"user_message": "test"},
            "plan": {
                "intent": "test",
                "steps": [
                    {"id": "s1", "type": "invalid_type", "description": "bad", "payload": {}}
                ]
            }
        }
        
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(invalid_plan))
        
        result = runner.invoke(cli, ["ai", "plan", "preview", str(plan_file)])
        
        assert result.exit_code == 1
    
    def test_context_short_options(self, runner, mock_context_bundle):
        """ai context should accept short option flags."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.agent.build_agent_context_bundle", new_callable=AsyncMock) as mock_build:
                    mock_build.return_value = mock_context_bundle
                    
                    result = runner.invoke(cli, [
                        "ai", "context",
                        "-i", "Test",
                        "-m", "read",
                        "-f", "json"
                    ])
                    
                    assert result.exit_code == 0
    
    def test_schema_issues_multiple_filters(self, runner, mock_schema_health_with_issues):
        """schema-issues should combine multiple filters."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.schema_doctor.analyze_schema_health", new_callable=AsyncMock) as mock_analyze:
                    mock_analyze.return_value = mock_schema_health_with_issues
                    
                    result = runner.invoke(cli, [
                        "ai", "schema-issues",
                        "--severity", "danger",
                        "--table", "blog_articles"
                    ])
                    
                    assert result.exit_code == 0
                    # Should find the one matching issue
                    assert "1 found" in result.output


# =============================================================================
# Integration-style tests
# =============================================================================

class TestIntegrationFlows:
    """Test complete CLI flows."""
    
    def test_full_plan_workflow(self, runner, mock_context_bundle, mock_plan_execution_success, tmp_path):
        """Test complete plan workflow: template -> preview -> apply."""
        # Step 1: Generate template
        result = runner.invoke(cli, [
            "ai", "plan", "template",
            "--intent", "Add Category model"
        ])
        assert result.exit_code == 0
        template = json.loads(result.output)
        
        # Step 2: Save template
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(template))
        
        # Step 3: Preview
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.planner.execute_plan", new_callable=AsyncMock) as mock_execute:
                    mock_execute.return_value = mock_plan_execution_success
                    
                    result = runner.invoke(cli, ["ai", "plan", "preview", str(plan_file)])
                    assert result.exit_code == 0
                    
                    # Step 4: Apply
                    result = runner.invoke(cli, [
                        "ai", "plan", "apply", str(plan_file), "--yes"
                    ])
                    assert result.exit_code == 0
    
    def test_schema_health_to_issues_flow(self, runner, mock_schema_health_with_issues):
        """Test flow from schema-health to schema-issues."""
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.schema_doctor.analyze_schema_health", new_callable=AsyncMock) as mock_analyze:
                    mock_analyze.return_value = mock_schema_health_with_issues
                    
                    # Check health first
                    result = runner.invoke(cli, ["ai", "schema-health"])
                    assert "DANGER" in result.output
                    
                    # Get detailed issues
                    result = runner.invoke(cli, ["ai", "schema-issues", "--format", "json"])
                    issues = json.loads(result.output)
                    assert len(issues) == 2
