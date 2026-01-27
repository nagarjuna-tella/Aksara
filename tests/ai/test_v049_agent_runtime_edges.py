"""
Aksara v0.4.10 - Agent Runtime Edge Cases

Tests for:
1. Invalid plan shape (missing fields, extra fields, invalid types)
2. Missing intent fields
3. Massive plan size handling
"""

import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from aksara.ai.agent import (
    AgentIntent,
    AgentContextBundle,
    build_agent_context_bundle,
)
from aksara.ai.models import AiTool
from aksara.ai.planner import AiPlan, AiPlanStep


# =============================================================================
# Section 1: Invalid Plan Shape
# =============================================================================

class TestInvalidPlanShape:
    """Tests for handling invalid plan shapes."""
    
    def test_missing_intent_field_rejected(self):
        """AiPlan without intent should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AiPlan(
                # intent missing!
                steps=[
                    AiPlanStep(id="s1", type="analyze_context", description="Test", payload={})
                ]
            )
        
        assert "intent" in str(exc_info.value).lower()
    
    def test_missing_steps_field_rejected(self):
        """AiPlan without steps should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AiPlan(
                intent="Test plan"
                # steps missing!
            )
        
        assert "steps" in str(exc_info.value).lower()
    
    def test_extra_unknown_fields_rejected(self):
        """AiPlan with unknown fields should be rejected (extra='forbid')."""
        with pytest.raises(ValidationError) as exc_info:
            AiPlan(
                intent="Test plan",
                steps=[
                    AiPlanStep(id="s1", type="analyze_context", description="Test", payload={})
                ],
                unknown_field="should_fail"  # Extra field!
            )
        
        assert "extra" in str(exc_info.value).lower() or "unknown" in str(exc_info.value).lower()
    
    def test_step_missing_id_rejected(self):
        """AiPlanStep without id should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AiPlanStep(
                # id missing!
                type="analyze_context",
                description="Test"
            )
        
        assert "id" in str(exc_info.value).lower()
    
    def test_step_missing_type_rejected(self):
        """AiPlanStep without type should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AiPlanStep(
                id="s1",
                # type missing!
                description="Test"
            )
        
        assert "type" in str(exc_info.value).lower()
    
    def test_step_missing_description_rejected(self):
        """AiPlanStep without description should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AiPlanStep(
                id="s1",
                type="analyze_context"
                # description missing!
            )
        
        assert "description" in str(exc_info.value).lower()
    
    def test_step_extra_fields_rejected(self):
        """AiPlanStep with extra fields should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AiPlanStep(
                id="s1",
                type="analyze_context",
                description="Test",
                extra_field="not_allowed"
            )
        
        assert "extra" in str(exc_info.value).lower()
    
    def test_invalid_step_type_string_rejected(self):
        """Invalid step type string should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AiPlanStep(
                id="s1",
                type="not_a_valid_type",
                description="Test"
            )
        
        assert "type" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
    
    def test_step_depends_on_wrong_type_rejected(self):
        """depends_on with wrong type should be rejected."""
        with pytest.raises(ValidationError):
            AiPlanStep(
                id="s1",
                type="analyze_context",
                description="Test",
                depends_on="should_be_list"  # Should be List[str]
            )
    
    def test_step_payload_wrong_type_rejected(self):
        """payload with wrong type should be rejected."""
        with pytest.raises(ValidationError):
            AiPlanStep(
                id="s1",
                type="analyze_context",
                description="Test",
                payload="should_be_dict"  # Should be Dict
            )


class TestPlanFromJson:
    """Tests for creating plans from JSON."""
    
    def test_valid_json_creates_plan(self):
        """Valid JSON should create a plan."""
        plan_json = {
            "intent": "Add a model",
            "steps": [
                {
                    "id": "s1",
                    "type": "analyze_context",
                    "description": "Analyze state",
                    "payload": {}
                }
            ]
        }
        
        plan = AiPlan(**plan_json)
        
        assert plan.intent == "Add a model"
        assert len(plan.steps) == 1
    
    def test_invalid_json_rejected(self):
        """Invalid JSON structure should be rejected."""
        invalid_json = {
            "intent": "Test",
            "steps": [
                {
                    "id": "s1",
                    "type": "invalid_type",  # Invalid!
                    "description": "Test"
                }
            ]
        }
        
        with pytest.raises(ValidationError):
            AiPlan(**invalid_json)
    
    def test_json_with_null_values(self):
        """JSON with null values for optional fields should work."""
        plan_json = {
            "intent": "Test plan",
            "steps": [
                {
                    "id": "s1",
                    "type": "analyze_context",
                    "description": "Test",
                    "depends_on": [],
                    "payload": {},
                    "reasoning": None  # Optional field
                }
            ],
            "metadata": {}
        }
        
        plan = AiPlan(**plan_json)
        assert plan.steps[0].reasoning is None


# =============================================================================
# Section 2: Missing Intent Fields
# =============================================================================

class TestAgentIntentValidation:
    """Tests for AgentIntent validation."""
    
    def test_empty_user_message_behavior(self):
        """
        Test behavior with empty user_message.
        
        Decision: We allow empty user_message for system-generated intents.
        """
        # Allow empty message
        intent = AgentIntent(user_message="", mode="read")
        
        assert intent.user_message == ""
        assert intent.mode == "read"
    
    def test_none_user_message_rejected(self):
        """user_message=None should be rejected (it's required)."""
        with pytest.raises(ValidationError):
            AgentIntent(user_message=None, mode="read")
    
    def test_missing_user_message_rejected(self):
        """Missing user_message should be rejected."""
        with pytest.raises(ValidationError):
            AgentIntent(mode="read")  # user_message not provided
    
    def test_valid_modes_accepted(self):
        """Valid mode values should be accepted."""
        valid_modes = ["read", "design", "modify"]
        
        for mode in valid_modes:
            intent = AgentIntent(user_message="Test", mode=mode)
            assert intent.mode == mode
    
    def test_invalid_mode_rejected(self):
        """Invalid mode value should be rejected."""
        with pytest.raises(ValidationError):
            AgentIntent(user_message="Test", mode="invalid_mode")
    
    def test_default_mode_is_modify(self):
        """Default mode should be 'modify'."""
        intent = AgentIntent(user_message="Test")
        
        assert intent.mode == "modify"
    
    def test_intent_with_all_fields(self):
        """Intent with all fields should work."""
        intent = AgentIntent(
            user_message="Add a User model",
            mode="modify",
            scope=["models", "api"],  # scope is a List, not str
            hints={"app": "users"},
            metadata={"source": "cli"}
        )
        
        assert intent.user_message == "Add a User model"
        assert intent.mode == "modify"
        assert "models" in intent.scope
        assert intent.hints["app"] == "users"
        assert intent.metadata["source"] == "cli"
    
    def test_intent_optional_fields_default(self):
        """Optional fields should have sensible defaults."""
        intent = AgentIntent(user_message="Test")
        
        assert intent.scope is None
        assert intent.hints == {}
        assert intent.metadata == {}


# =============================================================================
# Section 3: Massive Plan Size Handling
# =============================================================================

class TestMassivePlanSize:
    """Tests for handling large plans."""
    
    def test_many_steps_creates_valid_plan(self):
        """Plan with many steps should be creatable."""
        num_steps = 200
        
        steps = [
            AiPlanStep(
                id=f"step_{i}",
                type="analyze_context",
                description=f"Step {i}",
                payload={},
                depends_on=[f"step_{i-1}"] if i > 0 else []
            )
            for i in range(num_steps)
        ]
        
        plan = AiPlan(
            intent="Large plan test",
            steps=steps
        )
        
        assert len(plan.steps) == num_steps
    
    def test_topological_sort_performance(self):
        """Topological sort should handle large plans efficiently."""
        from aksara.ai.planner import _topological_sort
        
        num_steps = 200
        
        steps = [
            AiPlanStep(
                id=f"step_{i}",
                type="analyze_context",
                description=f"Step {i}",
                payload={},
                depends_on=[f"step_{i-1}"] if i > 0 else []
            )
            for i in range(num_steps)
        ]
        
        start = time.perf_counter()
        sorted_steps = _topological_sort(steps)
        elapsed = time.perf_counter() - start
        
        # Should complete in reasonable time (< 1 second)
        assert elapsed < 1.0, f"Topological sort took {elapsed:.2f}s"
        assert len(sorted_steps) == num_steps
    
    def test_circular_dependency_check_performance(self):
        """Circular dependency check should handle large plans efficiently."""
        from aksara.ai.planner import _has_circular_dependency
        
        num_steps = 200
        
        # Create a linear chain (no cycles)
        steps = [
            AiPlanStep(
                id=f"step_{i}",
                type="analyze_context",
                description=f"Step {i}",
                payload={},
                depends_on=[f"step_{i-1}"] if i > 0 else []
            )
            for i in range(num_steps)
        ]
        
        start = time.perf_counter()
        has_cycle = _has_circular_dependency(steps)
        elapsed = time.perf_counter() - start
        
        # Should complete in reasonable time
        assert elapsed < 1.0, f"Cycle check took {elapsed:.2f}s"
        assert has_cycle is False
    
    def test_validate_plan_performance(self):
        """validate_plan should handle large plans efficiently."""
        from aksara.ai.planner import validate_plan
        
        num_steps = 100
        
        steps = [
            AiPlanStep(
                id=f"step_{i}",
                type="analyze_context",
                description=f"Step {i}",
                payload={},
                depends_on=[]
            )
            for i in range(num_steps)
        ]
        
        plan = AiPlan(intent="Large plan", steps=steps)
        
        start = time.perf_counter()
        errors = validate_plan(plan)
        elapsed = time.perf_counter() - start
        
        # Should complete quickly
        assert elapsed < 1.0, f"Validation took {elapsed:.2f}s"
    
    def test_large_plan_no_stack_overflow(self):
        """Large plans should not cause stack overflow."""
        num_steps = 500
        
        steps = [
            AiPlanStep(
                id=f"step_{i}",
                type="analyze_context",
                description=f"Step {i}",
                payload={},
                depends_on=[]  # Independent steps to avoid deep recursion
            )
            for i in range(num_steps)
        ]
        
        # Should not raise RecursionError
        plan = AiPlan(intent="Very large plan", steps=steps)
        assert len(plan.steps) == num_steps


# =============================================================================
# Section 4: AgentContextBundle Validation
# =============================================================================

class TestAgentContextBundleValidation:
    """Tests for AgentContextBundle validation."""
    
    def test_bundle_requires_intent(self):
        """AgentContextBundle should require intent."""
        with pytest.raises(ValidationError):
            AgentContextBundle(
                # intent missing!
                full_context={},
                tools=[],
                plan_schema={},
                patch_schema={},
                query_plan_schema={},
                codegen_schema={},
                version="0.4.10"
            )
    
    def test_bundle_requires_version(self):
        """AgentContextBundle should require version."""
        with pytest.raises(ValidationError):
            AgentContextBundle(
                intent=AgentIntent(user_message="Test"),
                full_context={},
                tools=[],
                plan_schema={},
                patch_schema={},
                query_plan_schema={},
                codegen_schema={}
                # version missing!
            )
    
    def test_valid_bundle_creation(self):
        """Valid bundle should be creatable."""
        bundle = AgentContextBundle(
            intent=AgentIntent(user_message="Test", mode="read"),
            full_context={"models": [], "routes": []},
            tools=[{"name": "test_tool", "description": "Test"}],
            plan_schema={"type": "object"},
            patch_schema={"type": "object"},
            query_plan_schema={"type": "object"},
            codegen_schema={"type": "object"},
            version="0.4.10"
        )
        
        assert bundle.intent.user_message == "Test"
        assert bundle.version == "0.4.10"


# =============================================================================
# Section 5: AiTool Validation
# =============================================================================

class TestAiToolValidation:
    """Tests for AiTool validation."""
    
    def test_tool_requires_name(self):
        """AiTool should require name."""
        with pytest.raises(ValidationError):
            AiTool(
                # name missing!
                title="Test Tool",
                http_method="GET",
                path="/api/test/",
                description="Test tool",
            )
    
    def test_tool_requires_title(self):
        """AiTool should require title."""
        with pytest.raises(ValidationError):
            AiTool(
                name="test_tool",
                # title missing!
                http_method="GET",
                path="/api/test/",
            )
    
    def test_valid_tool_creation(self):
        """Valid tool should be creatable."""
        tool = AiTool(
            name="analyze_models",
            title="Analyze Models",
            description="Analyze model definitions",
            http_method="GET",
            path="/ai/models/analyze/",
            kind="query",
            input_schema={"type": "object"},
        )
        
        assert tool.name == "analyze_models"
        assert tool.title == "Analyze Models"
        assert tool.description == "Analyze model definitions"


# =============================================================================
# Section 6: Structured Error Responses
# =============================================================================

class TestStructuredErrorResponses:
    """Tests for structured error responses from validation."""
    
    def test_validation_error_has_location(self):
        """ValidationError should indicate error location."""
        try:
            AiPlan(
                intent="Test",
                steps=[
                    AiPlanStep(
                        id="s1",
                        type="invalid_type",  # Error here
                        description="Test"
                    )
                ]
            )
            pytest.fail("Should have raised ValidationError")
        except ValidationError as e:
            # Error should contain location info
            error_str = str(e)
            # Should mention steps or type
            assert "type" in error_str.lower() or "steps" in error_str.lower()
    
    def test_multiple_errors_all_reported(self):
        """Multiple validation errors should all be reported."""
        try:
            AiPlanStep(
                # id missing
                # type missing
                # description missing
            )
            pytest.fail("Should have raised ValidationError")
        except ValidationError as e:
            errors = e.errors()
            # Should have multiple errors
            assert len(errors) >= 2
    
    def test_error_type_information(self):
        """Validation errors should have type information."""
        try:
            AiPlanStep(
                id=123,  # Should be string
                type="analyze_context",
                description="Test"
            )
            pytest.fail("Should have raised ValidationError")
        except ValidationError as e:
            errors = e.errors()
            # Should indicate type error
            assert any("type" in str(err).lower() for err in errors)


# =============================================================================
# Section 7: Build Agent Context Bundle
# =============================================================================

class TestBuildAgentContextBundle:
    """Tests for build_agent_context_bundle function."""
    
    @pytest.mark.asyncio
    async def test_build_returns_valid_bundle(self):
        """build_agent_context_bundle should return valid bundle."""
        mock_app = MagicMock()
        intent = AgentIntent(user_message="Test", mode="read")
        
        # Patch the context builder (imported inside the function)
        with patch("aksara.ai.context.build_full_ai_context", new_callable=AsyncMock) as mock_context:
            # Return a mock that has model_dump()
            mock_result = MagicMock()
            mock_result.model_dump.return_value = {"models": [], "viewsets": [], "routes": [], "migrations": []}
            mock_context.return_value = mock_result
            
            bundle = await build_agent_context_bundle(mock_app, intent)
            
            assert isinstance(bundle, AgentContextBundle)
            assert bundle.intent.user_message == "Test"
    
    @pytest.mark.asyncio
    async def test_build_includes_schemas(self):
        """build_agent_context_bundle should include all schemas."""
        mock_app = MagicMock()
        intent = AgentIntent(user_message="Test")
        
        # Patch the context builder (imported inside the function)
        with patch("aksara.ai.context.build_full_ai_context", new_callable=AsyncMock) as mock_context:
            mock_result = MagicMock()
            mock_result.model_dump.return_value = {}
            mock_context.return_value = mock_result
            
            bundle = await build_agent_context_bundle(mock_app, intent)
            
            # Should have all schema fields
            assert bundle.plan_schema is not None
            assert bundle.patch_schema is not None
            assert bundle.query_plan_schema is not None
            assert bundle.codegen_schema is not None
