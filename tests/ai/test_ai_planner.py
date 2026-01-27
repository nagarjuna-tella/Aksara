"""
Tests for AI Planner (THE ARCHITECT) - v0.4.5

Tests cover:
- Pydantic model validation
- Plan step types and validation
- Topological sorting and dependency ordering
- Circular dependency detection
- Step handler execution
- Dry run vs apply semantics
- Fail-fast behavior
- Plan validation
- Schema generation
- Full integration with context, codegen, and patch
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI

from aksara.ai.planner import (
    # Types
    PlanStepType,
    VALID_STEP_TYPES,
    # Models
    AiPlanStep,
    AiPlan,
    AiPlanStepResult,
    AiPlanExecutionResult,
    # Helpers
    _has_circular_dependency,
    _topological_sort,
    # Handlers
    _handle_analyze_context,
    _handle_create_model,
    _handle_update_model,
    _handle_create_field,
    _handle_update_field,
    _handle_delete_field,
    _handle_create_migration,
    _handle_run_migrations,
    _handle_generate_viewset,
    _handle_generate_serializer,
    _handle_generate_admin,
    _handle_generate_tests,
    _handle_apply_patch,
    _handle_run_query_check,
    _handle_run_health_check,
    # Execution
    execute_plan,
    validate_plan,
    get_plan_schema,
)


# =============================================================================
# Pydantic Model Validation Tests
# =============================================================================


class TestAiPlanStepModel:
    """Tests for AiPlanStep Pydantic model."""
    
    def test_valid_step_creation(self):
        """Test creating a valid plan step."""
        step = AiPlanStep(
            id="step-1",
            type="analyze_context",
            description="Analyze the current application state"
        )
        assert step.id == "step-1"
        assert step.type == "analyze_context"
        assert step.description == "Analyze the current application state"
        assert step.depends_on == []
        assert step.payload == {}
        assert step.reasoning is None
    
    def test_step_with_dependencies(self):
        """Test step with depends_on list."""
        step = AiPlanStep(
            id="step-2",
            type="create_field",
            description="Add slug field",
            depends_on=["step-1"]
        )
        assert step.depends_on == ["step-1"]
    
    def test_step_with_payload(self):
        """Test step with custom payload."""
        step = AiPlanStep(
            id="step-1",
            type="create_field",
            description="Add slug field",
            payload={
                "model": "Article",
                "field": "slug",
                "field_spec": {"type": "slug", "max_length": 100}
            }
        )
        assert step.payload["model"] == "Article"
        assert step.payload["field"] == "slug"
    
    def test_step_with_reasoning(self):
        """Test step with AI reasoning."""
        step = AiPlanStep(
            id="step-1",
            type="analyze_context",
            description="Check state",
            reasoning="Need to understand current models before making changes"
        )
        assert step.reasoning is not None
    
    def test_invalid_step_type_rejected(self):
        """Test that invalid step types are rejected."""
        with pytest.raises(Exception):  # Pydantic literal error
            AiPlanStep(
                id="step-1",
                type="invalid_type",
                description="Invalid step"
            )
    
    def test_all_valid_step_types(self):
        """Test all valid step types are accepted."""
        for step_type in VALID_STEP_TYPES:
            step = AiPlanStep(
                id="test",
                type=step_type,
                description=f"Test {step_type}"
            )
            assert step.type == step_type
    
    def test_extra_fields_forbidden(self):
        """Test that extra fields are rejected."""
        with pytest.raises(Exception):  # Pydantic validation error
            AiPlanStep(
                id="step-1",
                type="analyze_context",
                description="Test",
                extra_field="not allowed"
            )


class TestAiPlanModel:
    """Tests for AiPlan Pydantic model."""
    
    def test_valid_plan_creation(self):
        """Test creating a valid plan."""
        plan = AiPlan(
            intent="Add slug field to Article",
            steps=[
                AiPlanStep(id="s1", type="analyze_context", description="Check state")
            ]
        )
        assert plan.intent == "Add slug field to Article"
        assert len(plan.steps) == 1
        assert plan.metadata == {}
    
    def test_plan_with_multiple_steps(self):
        """Test plan with multiple steps."""
        plan = AiPlan(
            intent="Create new model with viewset",
            steps=[
                AiPlanStep(id="s1", type="analyze_context", description="Check state"),
                AiPlanStep(id="s2", type="create_model", description="Create model", depends_on=["s1"]),
                AiPlanStep(id="s3", type="generate_viewset", description="Create viewset", depends_on=["s2"]),
            ]
        )
        assert len(plan.steps) == 3
    
    def test_plan_with_metadata(self):
        """Test plan with custom metadata."""
        plan = AiPlan(
            intent="Test intent",
            steps=[
                AiPlanStep(id="s1", type="run_health_check", description="Health check")
            ],
            metadata={"source": "ai_agent", "model": "gpt-4"}
        )
        assert plan.metadata["source"] == "ai_agent"
    
    def test_empty_steps_rejected(self):
        """Test that empty steps list is rejected."""
        with pytest.raises(ValueError, match="at least one step"):
            AiPlan(intent="Test", steps=[])
    
    def test_duplicate_ids_rejected(self):
        """Test that duplicate step IDs are rejected."""
        with pytest.raises(ValueError, match="unique"):
            AiPlan(
                intent="Test",
                steps=[
                    AiPlanStep(id="s1", type="analyze_context", description="Step 1"),
                    AiPlanStep(id="s1", type="run_health_check", description="Step 2"),
                ]
            )
    
    def test_invalid_depends_on_reference(self):
        """Test that invalid depends_on references are rejected."""
        with pytest.raises(ValueError, match="unknown step"):
            AiPlan(
                intent="Test",
                steps=[
                    AiPlanStep(id="s1", type="analyze_context", description="Step 1", depends_on=["s99"])
                ]
            )
    
    def test_circular_dependency_rejected(self):
        """Test that circular dependencies are rejected."""
        with pytest.raises(ValueError, match="circular"):
            AiPlan(
                intent="Test",
                steps=[
                    AiPlanStep(id="s1", type="analyze_context", description="Step 1", depends_on=["s2"]),
                    AiPlanStep(id="s2", type="run_health_check", description="Step 2", depends_on=["s1"]),
                ]
            )


class TestAiPlanStepResult:
    """Tests for AiPlanStepResult model."""
    
    def test_success_result(self):
        """Test successful step result."""
        result = AiPlanStepResult(
            id="s1",
            type="analyze_context",
            success=True,
            output={"model_count": 5}
        )
        assert result.success is True
        assert result.error is None
    
    def test_failure_result(self):
        """Test failed step result."""
        result = AiPlanStepResult(
            id="s1",
            type="create_model",
            success=False,
            error="Model already exists"
        )
        assert result.success is False
        assert result.error == "Model already exists"


class TestAiPlanExecutionResult:
    """Tests for AiPlanExecutionResult model."""
    
    def test_successful_execution(self):
        """Test successful plan execution result."""
        result = AiPlanExecutionResult(
            success=True,
            steps=[
                AiPlanStepResult(id="s1", type="analyze_context", success=True),
                AiPlanStepResult(id="s2", type="run_health_check", success=True),
            ],
            notes=["Plan executed successfully"],
            dry_run=False
        )
        assert result.success is True
        assert len(result.steps) == 2
    
    def test_dry_run_execution(self):
        """Test dry run execution result."""
        result = AiPlanExecutionResult(
            success=True,
            steps=[],
            notes=["Dry run complete"],
            dry_run=True
        )
        assert result.dry_run is True


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestCircularDependencyDetection:
    """Tests for circular dependency detection."""
    
    def test_no_cycles_simple(self):
        """Test simple chain has no cycles."""
        steps = [
            AiPlanStep(id="s1", type="analyze_context", description="1"),
            AiPlanStep(id="s2", type="analyze_context", description="2", depends_on=["s1"]),
            AiPlanStep(id="s3", type="analyze_context", description="3", depends_on=["s2"]),
        ]
        assert _has_circular_dependency(steps) is False
    
    def test_no_cycles_diamond(self):
        """Test diamond pattern has no cycles."""
        steps = [
            AiPlanStep(id="s1", type="analyze_context", description="1"),
            AiPlanStep(id="s2", type="analyze_context", description="2", depends_on=["s1"]),
            AiPlanStep(id="s3", type="analyze_context", description="3", depends_on=["s1"]),
            AiPlanStep(id="s4", type="analyze_context", description="4", depends_on=["s2", "s3"]),
        ]
        assert _has_circular_dependency(steps) is False
    
    def test_direct_cycle(self):
        """Test direct cycle is detected."""
        steps = [
            AiPlanStep(id="s1", type="analyze_context", description="1", depends_on=["s2"]),
            AiPlanStep(id="s2", type="analyze_context", description="2", depends_on=["s1"]),
        ]
        assert _has_circular_dependency(steps) is True
    
    def test_indirect_cycle(self):
        """Test indirect cycle is detected."""
        steps = [
            AiPlanStep(id="s1", type="analyze_context", description="1", depends_on=["s3"]),
            AiPlanStep(id="s2", type="analyze_context", description="2", depends_on=["s1"]),
            AiPlanStep(id="s3", type="analyze_context", description="3", depends_on=["s2"]),
        ]
        assert _has_circular_dependency(steps) is True
    
    def test_self_cycle(self):
        """Test self-referential cycle is detected."""
        steps = [
            AiPlanStep(id="s1", type="analyze_context", description="1", depends_on=["s1"]),
        ]
        assert _has_circular_dependency(steps) is True


class TestTopologicalSort:
    """Tests for topological sorting of steps."""
    
    def test_already_sorted(self):
        """Test already sorted steps remain in order."""
        steps = [
            AiPlanStep(id="s1", type="analyze_context", description="1"),
            AiPlanStep(id="s2", type="analyze_context", description="2", depends_on=["s1"]),
            AiPlanStep(id="s3", type="analyze_context", description="3", depends_on=["s2"]),
        ]
        sorted_steps = _topological_sort(steps)
        assert [s.id for s in sorted_steps] == ["s1", "s2", "s3"]
    
    def test_reversed_order(self):
        """Test reversed order is corrected."""
        steps = [
            AiPlanStep(id="s3", type="analyze_context", description="3", depends_on=["s2"]),
            AiPlanStep(id="s2", type="analyze_context", description="2", depends_on=["s1"]),
            AiPlanStep(id="s1", type="analyze_context", description="1"),
        ]
        sorted_steps = _topological_sort(steps)
        ids = [s.id for s in sorted_steps]
        # s1 must come before s2, s2 must come before s3
        assert ids.index("s1") < ids.index("s2")
        assert ids.index("s2") < ids.index("s3")
    
    def test_diamond_dependency(self):
        """Test diamond dependency is sorted correctly."""
        steps = [
            AiPlanStep(id="s4", type="analyze_context", description="4", depends_on=["s2", "s3"]),
            AiPlanStep(id="s2", type="analyze_context", description="2", depends_on=["s1"]),
            AiPlanStep(id="s3", type="analyze_context", description="3", depends_on=["s1"]),
            AiPlanStep(id="s1", type="analyze_context", description="1"),
        ]
        sorted_steps = _topological_sort(steps)
        ids = [s.id for s in sorted_steps]
        # s1 first, then s2 and s3 (in any order), then s4
        assert ids[0] == "s1"
        assert ids[-1] == "s4"
    
    def test_no_dependencies(self):
        """Test steps with no dependencies maintain alphabetical order."""
        steps = [
            AiPlanStep(id="c", type="analyze_context", description="c"),
            AiPlanStep(id="a", type="analyze_context", description="a"),
            AiPlanStep(id="b", type="analyze_context", description="b"),
        ]
        sorted_steps = _topological_sort(steps)
        ids = [s.id for s in sorted_steps]
        assert ids == ["a", "b", "c"]


# =============================================================================
# Step Handler Tests
# =============================================================================


class TestAnalyzeContextHandler:
    """Tests for analyze_context step handler."""
    
    @pytest.mark.asyncio
    async def test_analyze_context_success(self):
        """Test successful context analysis."""
        app = MagicMock(spec=FastAPI)
        step = AiPlanStep(id="s1", type="analyze_context", description="Check state")
        
        # Mock the context builder - need to patch where it's imported
        with patch("aksara.ai.context.build_full_ai_context") as mock_ctx:
            mock_context = MagicMock()
            mock_context.framework_version = "0.4.5"
            mock_context.model_count = 5
            mock_context.viewset_count = 3
            mock_context.route_count = 20
            mock_context.migration_count = 10
            mock_context.pending_migrations = 0
            mock_context.models = []
            mock_context.viewsets = []
            mock_ctx.return_value = mock_context
            
            result = await _handle_analyze_context(app, step, dry_run=True)
        
        assert result.success is True
        assert "context_summary" in result.output
        assert result.output["context_summary"]["model_count"] == 5
    
    @pytest.mark.asyncio
    async def test_analyze_context_error(self):
        """Test context analysis handles errors."""
        app = MagicMock(spec=FastAPI)
        step = AiPlanStep(id="s1", type="analyze_context", description="Check state")
        
        with patch("aksara.ai.context.build_full_ai_context") as mock_ctx:
            mock_ctx.side_effect = Exception("Context build failed")
            
            result = await _handle_analyze_context(app, step, dry_run=True)
        
        assert result.success is False
        assert "Context build failed" in result.error


class TestCreateFieldHandler:
    """Tests for create_field step handler."""
    
    @pytest.mark.asyncio
    async def test_create_field_dry_run(self):
        """Test create field in dry run mode."""
        app = MagicMock(spec=FastAPI)
        app.state = MagicMock()
        app.state.project_root = "/tmp/test_project"
        
        step = AiPlanStep(
            id="s1",
            type="create_field",
            description="Add slug field",
            payload={
                "model": "Article",
                "field": "slug",
                "field_spec": {"type": "slug", "max_length": 100}
            }
        )
        
        with patch("aksara.ai.patch.apply_ai_patches") as mock_apply:
            mock_result = MagicMock()
            mock_result.applied = False
            mock_result.preview_only = True
            mock_result.files_changed = {}
            mock_apply.return_value = mock_result
            
            result = await _handle_create_field(app, step, dry_run=True)
        
        assert result.success is True
        assert result.output["model"] == "Article"
        assert result.output["field"] == "slug"
    
    @pytest.mark.asyncio
    async def test_create_field_missing_payload(self):
        """Test create field fails with missing payload."""
        app = MagicMock(spec=FastAPI)
        step = AiPlanStep(
            id="s1",
            type="create_field",
            description="Add field",
            payload={}
        )
        
        result = await _handle_create_field(app, step, dry_run=True)
        
        assert result.success is False
        assert "Missing" in result.error


class TestHealthCheckHandler:
    """Tests for run_health_check step handler."""
    
    @pytest.mark.asyncio
    async def test_health_check_basic(self):
        """Test basic health check returns results."""
        app = MagicMock(spec=FastAPI)
        app.routes = [MagicMock(), MagicMock()]
        
        step = AiPlanStep(id="s1", type="run_health_check", description="Health check")
        
        result = await _handle_run_health_check(app, step, dry_run=False)
        
        assert result.success is True
        assert "checks" in result.output
        assert result.output["checks"]["app_running"] is True


class TestGenerateTestsHandler:
    """Tests for generate_tests step handler."""
    
    @pytest.mark.asyncio
    async def test_generate_tests_dry_run(self):
        """Test generate tests in dry run mode."""
        app = MagicMock(spec=FastAPI)
        app.state = MagicMock()
        app.state.project_root = "/tmp/test"
        
        step = AiPlanStep(
            id="s1",
            type="generate_tests",
            description="Generate tests for Article",
            payload={"model": "Article", "app_label": "blog"}
        )
        
        result = await _handle_generate_tests(app, step, dry_run=True)
        
        assert result.success is True
        assert result.output["preview_only"] is True
        assert "test_article.py" in result.output["test_file"]
        assert "content_preview" in result.output
    
    @pytest.mark.asyncio
    async def test_generate_tests_missing_model(self):
        """Test generate tests fails without model name."""
        app = MagicMock(spec=FastAPI)
        step = AiPlanStep(
            id="s1",
            type="generate_tests",
            description="Generate tests",
            payload={}
        )
        
        result = await _handle_generate_tests(app, step, dry_run=True)
        
        assert result.success is False
        assert "Missing 'model'" in result.error


class TestRunMigrationsHandler:
    """Tests for run_migrations step handler."""
    
    @pytest.mark.asyncio
    async def test_run_migrations_dry_run(self):
        """Test run migrations in dry run mode."""
        app = MagicMock(spec=FastAPI)
        step = AiPlanStep(
            id="s1",
            type="run_migrations",
            description="Run migrations",
            payload={"apps": ["blog"], "fake": False}
        )
        
        result = await _handle_run_migrations(app, step, dry_run=True)
        
        assert result.success is True
        assert result.output["preview_only"] is True
        assert result.output["would_run_for_apps"] == ["blog"]


# =============================================================================
# Plan Execution Tests
# =============================================================================


class TestExecutePlan:
    """Tests for execute_plan function."""
    
    @pytest.mark.asyncio
    async def test_execute_single_step_plan(self):
        """Test executing a plan with a single step."""
        app = MagicMock(spec=FastAPI)
        app.routes = []
        
        plan = AiPlan(
            intent="Check health",
            steps=[
                AiPlanStep(id="s1", type="run_health_check", description="Health check")
            ]
        )
        
        result = await execute_plan(app, plan, dry_run=True)
        
        assert result.success is True
        assert len(result.steps) == 1
        assert result.dry_run is True
    
    @pytest.mark.asyncio
    async def test_execute_multi_step_plan(self):
        """Test executing a plan with multiple steps."""
        app = MagicMock(spec=FastAPI)
        app.routes = []
        
        plan = AiPlan(
            intent="Multiple health checks",
            steps=[
                AiPlanStep(id="s1", type="run_health_check", description="Check 1"),
                AiPlanStep(id="s2", type="run_health_check", description="Check 2", depends_on=["s1"]),
            ]
        )
        
        result = await execute_plan(app, plan, dry_run=True)
        
        assert result.success is True
        assert len(result.steps) == 2
    
    @pytest.mark.asyncio
    async def test_execute_plan_fail_fast(self):
        """Test that plan execution stops on first failure."""
        app = MagicMock(spec=FastAPI)
        
        plan = AiPlan(
            intent="Test fail fast",
            steps=[
                AiPlanStep(id="s1", type="create_field", description="Will fail", payload={}),
                AiPlanStep(id="s2", type="run_health_check", description="Should not run", depends_on=["s1"]),
            ]
        )
        
        result = await execute_plan(app, plan, dry_run=True)
        
        assert result.success is False
        assert len(result.steps) == 1  # Only first step executed
        assert result.steps[0].success is False
    
    @pytest.mark.asyncio
    async def test_execute_plan_respects_dependencies(self):
        """Test that steps are executed in dependency order."""
        app = MagicMock(spec=FastAPI)
        app.routes = []
        
        execution_order = []
        
        async def track_health_check(app, step, dry_run):
            execution_order.append(step.id)
            return AiPlanStepResult(id=step.id, type=step.type, success=True, output={})
        
        plan = AiPlan(
            intent="Test ordering",
            steps=[
                AiPlanStep(id="s3", type="run_health_check", description="3", depends_on=["s1", "s2"]),
                AiPlanStep(id="s1", type="run_health_check", description="1"),
                AiPlanStep(id="s2", type="run_health_check", description="2", depends_on=["s1"]),
            ]
        )
        
        with patch.dict("aksara.ai.planner.STEP_HANDLERS", {"run_health_check": track_health_check}):
            result = await execute_plan(app, plan, dry_run=True)
        
        assert result.success is True
        # s1 must come before s2 and s3
        assert execution_order.index("s1") < execution_order.index("s2")
        assert execution_order.index("s2") < execution_order.index("s3")
    
    @pytest.mark.asyncio
    async def test_execute_plan_dry_run_flag(self):
        """Test that dry_run flag is passed to handlers."""
        app = MagicMock(spec=FastAPI)
        
        received_dry_run = []
        
        async def capture_dry_run(app, step, dry_run):
            received_dry_run.append(dry_run)
            return AiPlanStepResult(id=step.id, type=step.type, success=True, output={})
        
        plan = AiPlan(
            intent="Test dry run",
            steps=[
                AiPlanStep(id="s1", type="run_health_check", description="Test")
            ]
        )
        
        with patch.dict("aksara.ai.planner.STEP_HANDLERS", {"run_health_check": capture_dry_run}):
            await execute_plan(app, plan, dry_run=True)
            await execute_plan(app, plan, dry_run=False)
        
        assert received_dry_run == [True, False]


# =============================================================================
# Validation Tests
# =============================================================================


class TestValidatePlan:
    """Tests for validate_plan function."""
    
    def test_validate_valid_plan(self):
        """Test that valid plan has no errors."""
        plan = AiPlan(
            intent="Valid plan",
            steps=[
                AiPlanStep(id="s1", type="run_health_check", description="Check")
            ]
        )
        
        errors = validate_plan(plan)
        assert errors == []
    
    def test_validate_create_model_missing_spec(self):
        """Test that create_model without spec is caught."""
        plan = AiPlan(
            intent="Test",
            steps=[
                AiPlanStep(id="s1", type="create_model", description="Create", payload={})
            ]
        )
        
        errors = validate_plan(plan)
        assert any("model_spec" in e for e in errors)
    
    def test_validate_create_field_missing_model(self):
        """Test that create_field without model is caught."""
        plan = AiPlan(
            intent="Test",
            steps=[
                AiPlanStep(id="s1", type="create_field", description="Add field", payload={})
            ]
        )
        
        errors = validate_plan(plan)
        assert any("model" in e for e in errors)
    
    def test_validate_apply_patch_missing_request(self):
        """Test that apply_patch without request is caught."""
        plan = AiPlan(
            intent="Test",
            steps=[
                AiPlanStep(id="s1", type="apply_patch", description="Patch", payload={})
            ]
        )
        
        errors = validate_plan(plan)
        assert any("patch_request" in e for e in errors)
    
    def test_validate_run_query_check_missing_plan(self):
        """Test that run_query_check without plan is caught."""
        plan = AiPlan(
            intent="Test",
            steps=[
                AiPlanStep(id="s1", type="run_query_check", description="Query", payload={})
            ]
        )
        
        errors = validate_plan(plan)
        assert any("plan" in e.lower() for e in errors)


# =============================================================================
# Schema Generation Tests
# =============================================================================


class TestGetPlanSchema:
    """Tests for get_plan_schema function."""
    
    def test_schema_contains_all_models(self):
        """Test that schema includes all model schemas."""
        schema = get_plan_schema()
        
        assert "AiPlan" in schema
        assert "AiPlanStep" in schema
        assert "AiPlanStepResult" in schema
        assert "AiPlanExecutionResult" in schema
    
    def test_schema_contains_step_types(self):
        """Test that schema includes valid step types."""
        schema = get_plan_schema()
        
        assert "valid_step_types" in schema
        assert "analyze_context" in schema["valid_step_types"]
        assert "create_model" in schema["valid_step_types"]
        assert "run_health_check" in schema["valid_step_types"]


# =============================================================================
# Integration Tests
# =============================================================================


class TestPlannerIntegration:
    """Integration tests for the planner with other AI modules."""
    
    @pytest.mark.asyncio
    async def test_analyze_context_integration(self):
        """Test analyze_context integrates with context module."""
        app = MagicMock(spec=FastAPI)
        
        plan = AiPlan(
            intent="Get app context",
            steps=[
                AiPlanStep(id="s1", type="analyze_context", description="Get context")
            ]
        )
        
        with patch("aksara.ai.context.build_full_ai_context") as mock_ctx:
            mock_context = MagicMock()
            mock_context.framework_version = "0.4.5"
            mock_context.model_count = 3
            mock_context.viewset_count = 2
            mock_context.route_count = 10
            mock_context.migration_count = 5
            mock_context.pending_migrations = 1
            mock_context.models = []
            mock_context.viewsets = []
            mock_ctx.return_value = mock_context
            
            result = await execute_plan(app, plan, dry_run=True)
        
        assert result.success is True
        assert result.steps[0].output["context_summary"]["model_count"] == 3


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestPlannerEdgeCases:
    """Edge case tests for the planner."""
    
    def test_step_types_constant(self):
        """Test that VALID_STEP_TYPES contains expected types."""
        expected = {
            "analyze_context",
            "create_model",
            "update_model",
            "create_field",
            "update_field",
            "delete_field",
            "create_migration",
            "run_migrations",
            "generate_viewset",
            "generate_serializer",
            "generate_admin",
            "generate_tests",
            "apply_patch",
            "run_query_check",
            "run_health_check",
        }
        assert VALID_STEP_TYPES == expected
    
    @pytest.mark.asyncio
    async def test_empty_depends_on_list(self):
        """Test that empty depends_on is handled correctly."""
        app = MagicMock(spec=FastAPI)
        app.routes = []
        
        plan = AiPlan(
            intent="Test",
            steps=[
                AiPlanStep(id="s1", type="run_health_check", description="Test", depends_on=[])
            ]
        )
        
        result = await execute_plan(app, plan, dry_run=True)
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_large_plan_execution(self):
        """Test executing a plan with many steps."""
        app = MagicMock(spec=FastAPI)
        app.routes = []
        
        steps = [
            AiPlanStep(id=f"s{i}", type="run_health_check", description=f"Step {i}")
            for i in range(20)
        ]
        
        plan = AiPlan(intent="Large plan", steps=steps)
        
        result = await execute_plan(app, plan, dry_run=True)
        
        assert result.success is True
        assert len(result.steps) == 20
    
    def test_plan_json_serialization(self):
        """Test that plans can be serialized to JSON."""
        plan = AiPlan(
            intent="Test serialization",
            steps=[
                AiPlanStep(id="s1", type="analyze_context", description="Test")
            ]
        )
        
        json_data = plan.model_dump_json()
        assert "Test serialization" in json_data
    
    def test_step_result_json_serialization(self):
        """Test that step results can be serialized to JSON."""
        result = AiPlanStepResult(
            id="s1",
            type="analyze_context",
            success=True,
            output={"key": "value"}
        )
        
        json_data = result.model_dump_json()
        assert '"success":true' in json_data.lower() or '"success": true' in json_data.lower()


# =============================================================================
# API Endpoint Tests (Mocked)
# =============================================================================


class TestPlannerEndpoints:
    """Tests for planner API endpoints."""
    
    @pytest.mark.asyncio
    async def test_plan_schema_endpoint_response(self):
        """Test that plan schema endpoint returns expected structure."""
        schema = get_plan_schema()
        
        # Verify structure matches endpoint expectations
        assert "AiPlan" in schema
        assert "valid_step_types" in schema
        assert len(schema["valid_step_types"]) == 15


class TestPlanStepPayloadValidation:
    """Tests for step payload validation in different scenarios."""
    
    def test_create_model_payload_structure(self):
        """Test create_model accepts proper payload structure."""
        step = AiPlanStep(
            id="s1",
            type="create_model",
            description="Create Article model",
            payload={
                "model_spec": {
                    "name": "Article",
                    "app_label": "blog",
                    "fields": [
                        {"name": "title", "type": "string", "max_length": 200}
                    ]
                }
            }
        )
        assert step.payload["model_spec"]["name"] == "Article"
    
    def test_create_field_payload_structure(self):
        """Test create_field accepts proper payload structure."""
        step = AiPlanStep(
            id="s1",
            type="create_field",
            description="Add slug field",
            payload={
                "model": "Article",
                "field": "slug",
                "field_spec": {"type": "slug", "max_length": 100}
            }
        )
        assert step.payload["field"] == "slug"
    
    def test_apply_patch_payload_structure(self):
        """Test apply_patch accepts proper payload structure."""
        step = AiPlanStep(
            id="s1",
            type="apply_patch",
            description="Apply changes",
            payload={
                "patch_request": {
                    "operations": [
                        {"type": "modify_file", "path": "test.py", "text": "# test"}
                    ],
                    "reason": "Test patch"
                }
            }
        )
        assert "patch_request" in step.payload
    
    def test_run_query_check_payload_structure(self):
        """Test run_query_check accepts proper payload structure."""
        step = AiPlanStep(
            id="s1",
            type="run_query_check",
            description="Check data",
            payload={
                "plan": {
                    "model": "User",
                    "filters": [],
                    "pagination": {"limit": 10}
                }
            }
        )
        assert step.payload["plan"]["model"] == "User"
