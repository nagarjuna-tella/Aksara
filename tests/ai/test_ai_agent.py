"""
Tests for AI Runtime (Mini Agent Loop) - v0.4.6

Tests cover:
- AgentIntent model validation
- AgentContextBundle structure
- AgentPlanExecutionRequest/Response models
- AgentPlanApplyRequest/Response models
- build_agent_context_bundle function
- /ai/agent/context endpoint
- /ai/agent/plan/preview endpoint
- /ai/agent/plan/apply endpoint
- Safety requirements (confirm + header)
- Integration with Planner and other AI modules
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aksara.ai.agent import (
    # Models
    AgentIntent,
    AgentContextBundle,
    AgentPlanExecutionRequest,
    AgentPlanPreviewResponse,
    AgentPlanApplyRequest,
    AgentPlanApplyResponse,
    # Builder
    build_agent_context_bundle,
    build_agent_context_bundle_sync,
)


# =============================================================================
# AgentIntent Model Tests
# =============================================================================


class TestAgentIntentModel:
    """Tests for AgentIntent Pydantic model."""
    
    def test_minimal_intent(self):
        """Test creating intent with just user_message."""
        intent = AgentIntent(user_message="Add a slug field to Article")
        assert intent.user_message == "Add a slug field to Article"
        assert intent.mode == "modify"  # default
        assert intent.scope is None
        assert intent.hints == {}
        assert intent.metadata == {}
        assert intent.id is None
    
    def test_intent_with_all_fields(self):
        """Test intent with all optional fields."""
        intent = AgentIntent(
            id="req-123",
            user_message="Add slug field",
            mode="design",
            scope=["models", "migrations"],
            hints={"model": "Article", "app": "blog"},
            metadata={"editor": "vscode", "cursor_line": 42}
        )
        assert intent.id == "req-123"
        assert intent.mode == "design"
        assert intent.scope == ["models", "migrations"]
        assert intent.hints["model"] == "Article"
        assert intent.metadata["editor"] == "vscode"
    
    def test_mode_read(self):
        """Test read mode."""
        intent = AgentIntent(user_message="Show me all models", mode="read")
        assert intent.mode == "read"
    
    def test_mode_design(self):
        """Test design mode."""
        intent = AgentIntent(user_message="Plan adding a feature", mode="design")
        assert intent.mode == "design"
    
    def test_mode_modify(self):
        """Test modify mode (default)."""
        intent = AgentIntent(user_message="Add slug field", mode="modify")
        assert intent.mode == "modify"
    
    def test_invalid_mode_rejected(self):
        """Test that invalid modes are rejected."""
        with pytest.raises(Exception):  # Pydantic validation error
            AgentIntent(user_message="Test", mode="invalid")
    
    def test_extra_fields_forbidden(self):
        """Test that extra fields are rejected."""
        with pytest.raises(Exception):
            AgentIntent(
                user_message="Test",
                unknown_field="not allowed"
            )
    
    def test_intent_json_serialization(self):
        """Test intent can be serialized to JSON."""
        intent = AgentIntent(
            user_message="Test message",
            mode="modify",
            hints={"key": "value"}
        )
        json_str = intent.model_dump_json()
        assert "Test message" in json_str
        assert "modify" in json_str
    
    def test_empty_user_message_allowed(self):
        """Test that empty user message is handled."""
        # Empty string is technically valid, but we test the model accepts it
        intent = AgentIntent(user_message="")
        assert intent.user_message == ""


# =============================================================================
# AgentContextBundle Model Tests
# =============================================================================


class TestAgentContextBundleModel:
    """Tests for AgentContextBundle Pydantic model."""
    
    def test_bundle_creation(self):
        """Test creating a bundle with required fields."""
        intent = AgentIntent(user_message="Test")
        bundle = AgentContextBundle(
            intent=intent,
            full_context={"models": [], "routes": []},
            tools=[],
            plan_schema={"properties": {}},
            patch_schema={"properties": {}},
            query_plan_schema={"properties": {}},
            codegen_schema={"properties": {}},
            version="0.4.6"
        )
        assert bundle.intent.user_message == "Test"
        assert bundle.version == "0.4.6"
    
    def test_bundle_with_tools(self):
        """Test bundle with tools list."""
        intent = AgentIntent(user_message="Test")
        bundle = AgentContextBundle(
            intent=intent,
            full_context={},
            tools=[{"name": "tool1", "description": "Test tool"}],
            plan_schema={},
            patch_schema={},
            query_plan_schema={},
            codegen_schema={},
            version="0.4.6"
        )
        assert len(bundle.tools) == 1
        assert bundle.tools[0]["name"] == "tool1"
    
    def test_bundle_json_serialization(self):
        """Test bundle can be serialized to JSON."""
        intent = AgentIntent(user_message="Test")
        bundle = AgentContextBundle(
            intent=intent,
            full_context={"key": "value"},
            tools=[],
            plan_schema={"title": "AiPlan"},
            patch_schema={"title": "AiPatchRequest"},
            query_plan_schema={},
            codegen_schema={},
            version="0.4.6"
        )
        json_str = bundle.model_dump_json()
        assert "AiPlan" in json_str
        assert "0.4.6" in json_str


# =============================================================================
# AgentPlanExecutionRequest Model Tests
# =============================================================================


class TestAgentPlanExecutionRequest:
    """Tests for AgentPlanExecutionRequest model."""
    
    def test_execution_request_creation(self):
        """Test creating execution request."""
        intent = AgentIntent(user_message="Test")
        request = AgentPlanExecutionRequest(
            intent=intent,
            plan={"intent": "Test", "steps": []},
            dry_run=True
        )
        assert request.dry_run is True
        assert request.plan["intent"] == "Test"
    
    def test_execution_request_default_dry_run(self):
        """Test default dry_run is True."""
        intent = AgentIntent(user_message="Test")
        request = AgentPlanExecutionRequest(
            intent=intent,
            plan={"intent": "Test", "steps": []}
        )
        assert request.dry_run is True


# =============================================================================
# AgentPlanPreviewResponse Model Tests
# =============================================================================


class TestAgentPlanPreviewResponse:
    """Tests for AgentPlanPreviewResponse model."""
    
    def test_preview_response_creation(self):
        """Test creating preview response."""
        intent = AgentIntent(user_message="Test")
        response = AgentPlanPreviewResponse(
            intent=intent,
            plan={"intent": "Test", "steps": []},
            execution={"success": True, "steps": []},
            summary={"success": True, "step_count": 0}
        )
        assert response.summary["success"] is True
    
    def test_preview_response_with_failed_steps(self):
        """Test preview response with failed steps."""
        intent = AgentIntent(user_message="Test")
        response = AgentPlanPreviewResponse(
            intent=intent,
            plan={"intent": "Test", "steps": []},
            execution={"success": False, "steps": []},
            summary={"success": False, "failed_steps": ["s1", "s2"]}
        )
        assert response.summary["failed_steps"] == ["s1", "s2"]


# =============================================================================
# AgentPlanApplyRequest Model Tests
# =============================================================================


class TestAgentPlanApplyRequest:
    """Tests for AgentPlanApplyRequest model."""
    
    def test_apply_request_creation(self):
        """Test creating apply request."""
        intent = AgentIntent(user_message="Test")
        request = AgentPlanApplyRequest(
            intent=intent,
            plan={"intent": "Test", "steps": []},
            confirm=True
        )
        assert request.confirm is True
    
    def test_apply_request_default_confirm_false(self):
        """Test default confirm is False."""
        intent = AgentIntent(user_message="Test")
        request = AgentPlanApplyRequest(
            intent=intent,
            plan={"intent": "Test", "steps": []}
        )
        assert request.confirm is False


# =============================================================================
# AgentPlanApplyResponse Model Tests
# =============================================================================


class TestAgentPlanApplyResponse:
    """Tests for AgentPlanApplyResponse model."""
    
    def test_apply_response_creation(self):
        """Test creating apply response."""
        intent = AgentIntent(user_message="Test")
        response = AgentPlanApplyResponse(
            intent=intent,
            plan={"intent": "Test", "steps": []},
            execution={"success": True, "steps": []}
        )
        assert response.execution["success"] is True


# =============================================================================
# build_agent_context_bundle Tests
# =============================================================================


class TestBuildAgentContextBundle:
    """Tests for build_agent_context_bundle function."""
    
    @pytest.mark.asyncio
    async def test_build_bundle_returns_context_bundle(self):
        """Test that bundle contains all required components."""
        app = MagicMock(spec=FastAPI)
        intent = AgentIntent(user_message="Test request")
        
        with patch("aksara.ai.context.build_full_ai_context") as mock_ctx:
            mock_context = MagicMock()
            mock_context.model_dump.return_value = {
                "models": [],
                "routes": [],
                "framework_version": "0.4.6"
            }
            mock_ctx.return_value = mock_context
            
            bundle = await build_agent_context_bundle(app, intent)
        
        assert isinstance(bundle, AgentContextBundle)
        assert bundle.intent.user_message == "Test request"
        assert "models" in bundle.full_context
    
    @pytest.mark.asyncio
    async def test_build_bundle_contains_plan_schema(self):
        """Test that bundle includes plan schema."""
        app = MagicMock(spec=FastAPI)
        intent = AgentIntent(user_message="Test")
        
        with patch("aksara.ai.context.build_full_ai_context") as mock_ctx:
            mock_context = MagicMock()
            mock_context.model_dump.return_value = {}
            mock_ctx.return_value = mock_context
            
            bundle = await build_agent_context_bundle(app, intent)
        
        assert "AiPlan" in bundle.plan_schema
        assert "valid_step_types" in bundle.plan_schema
    
    @pytest.mark.asyncio
    async def test_build_bundle_contains_patch_schema(self):
        """Test that bundle includes patch schema."""
        app = MagicMock(spec=FastAPI)
        intent = AgentIntent(user_message="Test")
        
        with patch("aksara.ai.context.build_full_ai_context") as mock_ctx:
            mock_context = MagicMock()
            mock_context.model_dump.return_value = {}
            mock_ctx.return_value = mock_context
            
            bundle = await build_agent_context_bundle(app, intent)
        
        assert "AiPatchRequest" in bundle.patch_schema
        assert "AiPatchOperation" in bundle.patch_schema
    
    @pytest.mark.asyncio
    async def test_build_bundle_contains_query_schema(self):
        """Test that bundle includes query plan schema."""
        app = MagicMock(spec=FastAPI)
        intent = AgentIntent(user_message="Test")
        
        with patch("aksara.ai.context.build_full_ai_context") as mock_ctx:
            mock_context = MagicMock()
            mock_context.model_dump.return_value = {}
            mock_ctx.return_value = mock_context
            
            bundle = await build_agent_context_bundle(app, intent)
        
        # Query schema should have some structure
        assert bundle.query_plan_schema is not None
    
    @pytest.mark.asyncio
    async def test_build_bundle_contains_codegen_schema(self):
        """Test that bundle includes codegen schema."""
        app = MagicMock(spec=FastAPI)
        intent = AgentIntent(user_message="Test")
        
        with patch("aksara.ai.context.build_full_ai_context") as mock_ctx:
            mock_context = MagicMock()
            mock_context.model_dump.return_value = {}
            mock_ctx.return_value = mock_context
            
            bundle = await build_agent_context_bundle(app, intent)
        
        assert bundle.codegen_schema is not None
    
    @pytest.mark.asyncio
    async def test_build_bundle_includes_version(self):
        """Test that bundle includes Aksara version."""
        app = MagicMock(spec=FastAPI)
        intent = AgentIntent(user_message="Test")
        
        with patch("aksara.ai.context.build_full_ai_context") as mock_ctx:
            mock_context = MagicMock()
            mock_context.model_dump.return_value = {}
            mock_ctx.return_value = mock_context
            
            bundle = await build_agent_context_bundle(app, intent)
        
        import aksara
        assert bundle.version == aksara.__version__
    
    @pytest.mark.asyncio
    async def test_build_bundle_preserves_intent(self):
        """Test that original intent is preserved in bundle."""
        app = MagicMock(spec=FastAPI)
        intent = AgentIntent(
            id="test-123",
            user_message="My test message",
            mode="design",
            hints={"key": "value"}
        )
        
        with patch("aksara.ai.context.build_full_ai_context") as mock_ctx:
            mock_context = MagicMock()
            mock_context.model_dump.return_value = {}
            mock_ctx.return_value = mock_context
            
            bundle = await build_agent_context_bundle(app, intent)
        
        assert bundle.intent.id == "test-123"
        assert bundle.intent.user_message == "My test message"
        assert bundle.intent.mode == "design"
        assert bundle.intent.hints["key"] == "value"


# =============================================================================
# Schema Integration Tests
# =============================================================================


class TestSchemaIntegration:
    """Tests for JSON schema integration."""
    
    @pytest.mark.asyncio
    async def test_plan_schema_has_properties(self):
        """Test plan schema has expected structure."""
        app = MagicMock(spec=FastAPI)
        intent = AgentIntent(user_message="Test")
        
        with patch("aksara.ai.context.build_full_ai_context") as mock_ctx:
            mock_context = MagicMock()
            mock_context.model_dump.return_value = {}
            mock_ctx.return_value = mock_context
            
            bundle = await build_agent_context_bundle(app, intent)
        
        # Check AiPlan schema
        plan_schema = bundle.plan_schema.get("AiPlan", {})
        assert "properties" in plan_schema or "title" in plan_schema
    
    @pytest.mark.asyncio
    async def test_patch_schema_has_properties(self):
        """Test patch schema has expected structure."""
        app = MagicMock(spec=FastAPI)
        intent = AgentIntent(user_message="Test")
        
        with patch("aksara.ai.context.build_full_ai_context") as mock_ctx:
            mock_context = MagicMock()
            mock_context.model_dump.return_value = {}
            mock_ctx.return_value = mock_context
            
            bundle = await build_agent_context_bundle(app, intent)
        
        # Check patch schema
        patch_schema = bundle.patch_schema.get("AiPatchRequest", {})
        assert "properties" in patch_schema or "title" in patch_schema


# =============================================================================
# Endpoint Tests (Using TestClient)
# =============================================================================


class TestAgentContextEndpoint:
    """Tests for /ai/agent/context endpoint."""
    
    def test_context_endpoint_returns_bundle(self):
        """Test context endpoint returns bundle structure."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        # Mock at the agent module where build_agent_context_bundle is defined
        with patch("aksara.ai.agent.build_agent_context_bundle") as mock_build:
            mock_bundle = AgentContextBundle(
                intent=AgentIntent(user_message="Test"),
                full_context={"models": []},
                tools=[],
                plan_schema={"AiPlan": {}},
                patch_schema={"AiPatchRequest": {}},
                query_plan_schema={},
                codegen_schema={},
                version="0.4.6"
            )
            mock_build.return_value = mock_bundle
            
            response = client.post(
                "/ai/agent/context",
                json={"user_message": "Test request"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "intent" in data
        assert "full_context" in data
        assert "plan_schema" in data
        assert "version" in data
    
    def test_context_endpoint_preserves_intent(self):
        """Test intent is preserved in response."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        with patch("aksara.ai.agent.build_agent_context_bundle") as mock_build:
            mock_bundle = AgentContextBundle(
                intent=AgentIntent(
                    id="req-456",
                    user_message="My message",
                    mode="design"
                ),
                full_context={},
                tools=[],
                plan_schema={},
                patch_schema={},
                query_plan_schema={},
                codegen_schema={},
                version="0.4.6"
            )
            mock_build.return_value = mock_bundle
            
            response = client.post(
                "/ai/agent/context",
                json={
                    "id": "req-456",
                    "user_message": "My message",
                    "mode": "design"
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["intent"]["id"] == "req-456"
        assert data["intent"]["user_message"] == "My message"
        assert data["intent"]["mode"] == "design"
    
    def test_context_endpoint_invalid_intent(self):
        """Test endpoint rejects invalid intent."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        response = client.post(
            "/ai/agent/context",
            json={"mode": "invalid_mode"}  # Missing user_message
        )
        
        assert response.status_code == 422


class TestAgentPlanPreviewEndpoint:
    """Tests for /ai/agent/plan/preview endpoint."""
    
    def test_preview_endpoint_dry_run(self):
        """Test preview always runs in dry_run mode."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        # Mock at source module where execute_plan is defined
        with patch("aksara.ai.planner.execute_plan") as mock_execute:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.steps = []
            mock_result.model_dump.return_value = {"success": True, "steps": [], "notes": [], "dry_run": True}
            mock_execute.return_value = mock_result
            
            response = client.post(
                "/ai/agent/plan/preview",
                json={
                    "intent": {"user_message": "Test"},
                    "plan": {
                        "intent": "Test plan",
                        "steps": [
                            {"id": "s1", "type": "run_health_check", "description": "Check"}
                        ]
                    },
                    "dry_run": False  # Should be ignored
                }
            )
        
        assert response.status_code == 200
        # Verify dry_run=True was passed to execute_plan
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert call_args[1]["dry_run"] is True  # Always True for preview
    
    def test_preview_endpoint_returns_summary(self):
        """Test preview returns summary."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        with patch("aksara.ai.planner.execute_plan") as mock_execute:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.steps = [
                MagicMock(id="s1", success=True),
                MagicMock(id="s2", success=False)
            ]
            mock_result.model_dump.return_value = {"success": False, "steps": [], "notes": [], "dry_run": True}
            mock_execute.return_value = mock_result
            
            response = client.post(
                "/ai/agent/plan/preview",
                json={
                    "intent": {"user_message": "Test"},
                    "plan": {
                        "intent": "Test",
                        "steps": [
                            {"id": "s1", "type": "run_health_check", "description": "1"},
                            {"id": "s2", "type": "run_health_check", "description": "2"}
                        ]
                    }
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "step_count" in data["summary"]
    
    def test_preview_endpoint_invalid_plan(self):
        """Test preview rejects invalid plan."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        response = client.post(
            "/ai/agent/plan/preview",
            json={
                "intent": {"user_message": "Test"},
                "plan": {
                    "intent": "Test",
                    "steps": []  # Empty steps should fail
                }
            }
        )
        
        assert response.status_code == 422


class TestAgentPlanApplyEndpoint:
    """Tests for /ai/agent/plan/apply endpoint."""
    
    def test_apply_missing_header_rejected(self):
        """Test apply without X-AI-Apply header is rejected."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        response = client.post(
            "/ai/agent/plan/apply",
            json={
                "intent": {"user_message": "Test"},
                "plan": {
                    "intent": "Test",
                    "steps": [
                        {"id": "s1", "type": "run_health_check", "description": "1"}
                    ]
                },
                "confirm": True
            }
            # No X-AI-Apply header
        )
        
        assert response.status_code == 400
        assert "confirm=true" in response.json()["detail"]
    
    def test_apply_confirm_false_rejected(self):
        """Test apply with confirm=False is rejected."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        response = client.post(
            "/ai/agent/plan/apply",
            headers={"X-AI-Apply": "true"},
            json={
                "intent": {"user_message": "Test"},
                "plan": {
                    "intent": "Test",
                    "steps": [
                        {"id": "s1", "type": "run_health_check", "description": "1"}
                    ]
                },
                "confirm": False
            }
        )
        
        assert response.status_code == 400
    
    def test_apply_with_header_and_confirm(self):
        """Test apply succeeds with both header and confirm."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        with patch("aksara.ai.planner.execute_plan") as mock_execute:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.steps = []
            mock_result.model_dump.return_value = {"success": True, "steps": [], "notes": [], "dry_run": False}
            mock_execute.return_value = mock_result
            
            response = client.post(
                "/ai/agent/plan/apply",
                headers={"X-AI-Apply": "true"},
                json={
                    "intent": {"user_message": "Test"},
                    "plan": {
                        "intent": "Test",
                        "steps": [
                            {"id": "s1", "type": "run_health_check", "description": "1"}
                        ]
                    },
                    "confirm": True
                }
            )
        
        assert response.status_code == 200
        # Verify dry_run=False was passed
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert call_args[1]["dry_run"] is False
    
    def test_apply_header_case_insensitive(self):
        """Test X-AI-Apply header is case-insensitive."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        with patch("aksara.ai.planner.execute_plan") as mock_execute:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.steps = []
            mock_result.model_dump.return_value = {"success": True, "steps": [], "notes": [], "dry_run": False}
            mock_execute.return_value = mock_result
            
            response = client.post(
                "/ai/agent/plan/apply",
                headers={"X-AI-Apply": "TRUE"},  # Uppercase
                json={
                    "intent": {"user_message": "Test"},
                    "plan": {
                        "intent": "Test",
                        "steps": [
                            {"id": "s1", "type": "run_health_check", "description": "1"}
                        ]
                    },
                    "confirm": True
                }
            )
        
        assert response.status_code == 200


# =============================================================================
# Planner Integration Tests
# =============================================================================


class TestPlannerIntegration:
    """Tests for integration with Planner module."""
    
    def test_preview_with_analyze_context_step(self):
        """Test preview with analyze_context step."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        with patch("aksara.ai.planner.execute_plan") as mock_execute:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.steps = [MagicMock(id="s1", success=True)]
            mock_result.model_dump.return_value = {
                "success": True,
                "steps": [{"id": "s1", "type": "analyze_context", "success": True}],
                "notes": [],
                "dry_run": True
            }
            mock_execute.return_value = mock_result
            
            response = client.post(
                "/ai/agent/plan/preview",
                json={
                    "intent": {"user_message": "Analyze my app"},
                    "plan": {
                        "intent": "Analyze application",
                        "steps": [
                            {"id": "s1", "type": "analyze_context", "description": "Get context"}
                        ]
                    }
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["execution"]["success"] is True
    
    def test_preview_multi_step_plan(self):
        """Test preview with multi-step plan."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        with patch("aksara.ai.planner.execute_plan") as mock_execute:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.steps = [
                MagicMock(id="s1", success=True),
                MagicMock(id="s2", success=True),
                MagicMock(id="s3", success=True),
            ]
            mock_result.model_dump.return_value = {
                "success": True,
                "steps": [
                    {"id": "s1", "type": "analyze_context", "success": True},
                    {"id": "s2", "type": "run_health_check", "success": True},
                    {"id": "s3", "type": "run_health_check", "success": True},
                ],
                "notes": [],
                "dry_run": True
            }
            mock_execute.return_value = mock_result
            
            response = client.post(
                "/ai/agent/plan/preview",
                json={
                    "intent": {"user_message": "Multi-step"},
                    "plan": {
                        "intent": "Multi-step plan",
                        "steps": [
                            {"id": "s1", "type": "analyze_context", "description": "1"},
                            {"id": "s2", "type": "run_health_check", "description": "2", "depends_on": ["s1"]},
                            {"id": "s3", "type": "run_health_check", "description": "3", "depends_on": ["s2"]},
                        ]
                    }
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["step_count"] == 3
    
    def test_fail_fast_behavior(self):
        """Test that failed steps result in overall failure."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        with patch("aksara.ai.planner.execute_plan") as mock_execute:
            mock_result = MagicMock()
            mock_result.success = False
            mock_result.steps = [
                MagicMock(id="s1", success=False),
            ]
            mock_result.model_dump.return_value = {
                "success": False,
                "steps": [{"id": "s1", "type": "run_health_check", "success": False, "error": "Health check failed"}],
                "notes": ["Step s1 failed"],
                "dry_run": True
            }
            mock_execute.return_value = mock_result
            
            response = client.post(
                "/ai/agent/plan/preview",
                json={
                    "intent": {"user_message": "Test fail"},
                    "plan": {
                        "intent": "Failing plan",
                        "steps": [
                            {"id": "s1", "type": "run_health_check", "description": "Will fail"}
                        ]
                    }
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["execution"]["success"] is False


# =============================================================================
# Safety & Constraint Tests
# =============================================================================


class TestAgentSafety:
    """Tests for agent safety constraints."""
    
    def test_context_endpoint_is_read_only(self):
        """Test context endpoint doesn't modify anything."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        with patch("aksara.ai.agent.build_agent_context_bundle") as mock_build:
            mock_bundle = AgentContextBundle(
                intent=AgentIntent(user_message="Test"),
                full_context={},
                tools=[],
                plan_schema={},
                patch_schema={},
                query_plan_schema={},
                codegen_schema={},
                version="0.4.6"
            )
            mock_build.return_value = mock_bundle
            
            # Call multiple times
            for _ in range(3):
                response = client.post(
                    "/ai/agent/context",
                    json={"user_message": "Test"}
                )
                assert response.status_code == 200
    
    def test_preview_never_modifies_disk(self):
        """Test preview endpoint always uses dry_run."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        calls = []
        
        async def capture_execute(app, plan, dry_run):
            calls.append(dry_run)
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.steps = []
            mock_result.model_dump.return_value = {"success": True, "steps": [], "notes": [], "dry_run": dry_run}
            return mock_result
        
        with patch("aksara.ai.planner.execute_plan", side_effect=capture_execute):
            response = client.post(
                "/ai/agent/plan/preview",
                json={
                    "intent": {"user_message": "Test"},
                    "plan": {
                        "intent": "Test",
                        "steps": [{"id": "s1", "type": "run_health_check", "description": "1"}]
                    },
                    "dry_run": False  # Should be overridden
                }
            )
        
        assert response.status_code == 200
        assert all(dr is True for dr in calls)  # All calls should have dry_run=True
    
    def test_apply_requires_both_safeguards(self):
        """Test apply requires both confirm AND header."""
        from aksara.ai.fastapi import router
        
        app = FastAPI()
        app.include_router(router)
        
        client = TestClient(app)
        
        base_payload = {
            "intent": {"user_message": "Test"},
            "plan": {
                "intent": "Test",
                "steps": [{"id": "s1", "type": "run_health_check", "description": "1"}]
            }
        }
        
        # Test 1: confirm=False, no header
        response = client.post("/ai/agent/plan/apply", json={**base_payload, "confirm": False})
        assert response.status_code == 400
        
        # Test 2: confirm=True, no header
        response = client.post("/ai/agent/plan/apply", json={**base_payload, "confirm": True})
        assert response.status_code == 400
        
        # Test 3: confirm=False, with header
        response = client.post(
            "/ai/agent/plan/apply",
            headers={"X-AI-Apply": "true"},
            json={**base_payload, "confirm": False}
        )
        assert response.status_code == 400


# =============================================================================
# Edge Cases & Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_hints_and_metadata(self):
        """Test intent with empty hints and metadata."""
        intent = AgentIntent(
            user_message="Test",
            hints={},
            metadata={}
        )
        assert intent.hints == {}
        assert intent.metadata == {}
    
    def test_large_hints_payload(self):
        """Test intent with large hints payload."""
        large_hints = {f"key_{i}": f"value_{i}" for i in range(100)}
        intent = AgentIntent(
            user_message="Test",
            hints=large_hints
        )
        assert len(intent.hints) == 100
    
    def test_unicode_in_user_message(self):
        """Test intent with unicode characters."""
        intent = AgentIntent(
            user_message="Add a 🔥 field to Article 中文 测试"
        )
        assert "🔥" in intent.user_message
        assert "中文" in intent.user_message
    
    def test_scope_with_various_values(self):
        """Test intent with various scope values."""
        intent = AgentIntent(
            user_message="Test",
            scope=["models", "views", "migrations", "tests", "admin", "serializers"]
        )
        assert len(intent.scope) == 6
    
    def test_bundle_serialization_round_trip(self):
        """Test bundle can be serialized and deserialized."""
        intent = AgentIntent(user_message="Test")
        bundle = AgentContextBundle(
            intent=intent,
            full_context={"key": "value"},
            tools=[{"name": "tool1"}],
            plan_schema={"properties": {}},
            patch_schema={"properties": {}},
            query_plan_schema={},
            codegen_schema={},
            version="0.4.6"
        )
        
        # Serialize
        json_str = bundle.model_dump_json()
        
        # Deserialize
        from pydantic import TypeAdapter
        restored = TypeAdapter(AgentContextBundle).validate_json(json_str)
        
        assert restored.version == "0.4.6"
        assert restored.intent.user_message == "Test"


# =============================================================================
# Version Tests
# =============================================================================


class TestVersionIntegration:
    """Tests for version integration."""
    
    @pytest.mark.asyncio
    async def test_bundle_version_matches_aksara(self):
        """Test bundle version matches Aksara version."""
        import aksara
        
        app = MagicMock(spec=FastAPI)
        intent = AgentIntent(user_message="Test")
        
        with patch("aksara.ai.context.build_full_ai_context") as mock_ctx:
            mock_context = MagicMock()
            mock_context.model_dump.return_value = {}
            mock_ctx.return_value = mock_context
            
            bundle = await build_agent_context_bundle(app, intent)
        
        assert bundle.version == aksara.__version__
