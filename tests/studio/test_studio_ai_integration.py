"""
Tests for Aksara Studio AI Integration (v0.5.4).

Tests:
- GET /studio/ai/context
- GET /studio/ai/schemas
- GET /studio/ai/prompts
- Studio AI models
- No secrets exposed
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from aksara.studio.models import (
    # v0.5.4: AI Integration models
    StudioAiProjectMeta,
    StudioAiModelSummary,
    StudioAiRouteSummary,
    StudioAiToolInfo,
    StudioAiContextExport,
    StudioAiSchemas,
    StudioAiPromptTemplate,
    StudioAiPrompts,
    StudioMigrationStatus,
)
from aksara.studio.fastapi import router, verify_studio_auth as _verify_studio_auth


# =============================================================================
# Test Setup
# =============================================================================

def create_test_app() -> FastAPI:
    """Create a test FastAPI app with Studio router."""
    app = FastAPI(title="Test App", version="1.0.0")
    app.include_router(router)
    app.dependency_overrides[_verify_studio_auth] = lambda: None
    
    # Mock database state
    app._db = None
    app.state.db = None
    app.state.viewset_registry = []
    app.ai_registry = None
    
    return app


def create_mock_settings():
    """Create mock settings for testing."""
    mock_settings = MagicMock()
    mock_settings.debug = True
    mock_settings.log_level = "DEBUG"
    mock_settings.pool_min_size = 5
    mock_settings.pool_max_size = 20
    mock_settings.migrations_dir = "migrations"
    mock_settings.ai_enabled = True
    mock_settings.mcp_enabled = False
    mock_settings.apps = ["app"]
    mock_settings.app_title = "Test App"
    mock_settings.app_version = "1.0.0"
    mock_settings.enable_studio = True
    mock_settings.studio_secret_token = "test_token"
    mock_settings.studio_expose_in_production = False
    mock_settings.env = "development"
    mock_settings.installed_apps = ["app"]
    mock_settings.studio_allowed_origins = ["*"]
    return mock_settings


# =============================================================================
# GET /studio/ai/context Tests
# =============================================================================

class TestStudioAiContext:
    """Tests for GET /studio/ai/context endpoint."""
    
    def test_ai_context_returns_200(self):
        """AI context endpoint returns 200 OK."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                
                response = client.get("/studio/ai/context")
        
        assert response.status_code == 200
    
    def test_ai_context_returns_project_meta(self):
        """AI context includes project metadata."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                
                response = client.get("/studio/ai/context")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "project" in data
        project = data["project"]
        assert "name" in project
        assert "version" in project
        assert "environment" in project
        assert "debug" in project
    
    def test_ai_context_returns_models(self):
        """AI context includes model summaries."""
        app = create_test_app()
        client = TestClient(app)
        
        # Mock a model
        mock_model = MagicMock()
        mock_model._meta.table_name = "test_table"
        mock_model._meta.app_label = "test_app"
        mock_model._meta.fields = {"id": None, "name": None}
        mock_model._meta.primary_key = "id"
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {"TestModel": mock_model}
                
                response = client.get("/studio/ai/context")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "models" in data
        assert isinstance(data["models"], list)
    
    def test_ai_context_returns_tools(self):
        """AI context includes available tools."""
        app = create_test_app()
        client = TestClient(app)

        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}

                response = client.get("/studio/ai/context")

        assert response.status_code == 200
        data = response.json()

        assert "tools" in data
        assert isinstance(data["tools"], list)

        # Check tool structure
        if data["tools"]:
            tool = data["tools"][0]
            assert "name" in tool
            assert "description" in tool
            assert "safe" in tool

    def test_ai_context_tools_match_live_routes(self):
        """Exported tool endpoints must match the actually mounted /ai/* routes.

        Regression for the static-inventory drift bug: previously the export
        advertised phantom paths like /ai/query, /ai/plan, /ai/patch/validate
        that no real route served. Each exported tool endpoint must now
        correspond to a live route on this app's routing table.
        """
        app = create_test_app()
        client = TestClient(app)

        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                response = client.get("/studio/ai/context")

        assert response.status_code == 200
        tools = response.json().get("tools", [])
        assert tools, "expected at least one tool to be exported"

        live_paths = {getattr(r, "path", "") for r in app.routes}
        for tool in tools:
            assert tool["endpoint"] in live_paths, (
                f"tool {tool['name']!r} advertises {tool['endpoint']!r} "
                f"which is not mounted on the app"
            )
    
    def test_ai_context_includes_schema_checksum(self):
        """AI context includes schema checksum for change detection."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                
                response = client.get("/studio/ai/context")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "schema_checksum" in data
        assert isinstance(data["schema_checksum"], str)
    
    def test_ai_context_no_secrets_exposed(self):
        """AI context does not expose sensitive information."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                
                response = client.get("/studio/ai/context")
        
        assert response.status_code == 200
        json_str = json.dumps(response.json())
        
        # Check for actual secret values, not metadata field names like "secret_hints"
        # These patterns indicate actual exposed secrets, not field names
        forbidden_patterns = [
            "password=",
            "password\":",
            "api_key=",
            "credential=",
            "token=",
            # Exclude "secret_hints" which is a valid metadata field name
        ]
        for pattern in forbidden_patterns:
            assert pattern not in json_str.lower(), f"Found '{pattern}' in AI context"


# =============================================================================
# GET /studio/ai/schemas Tests
# =============================================================================

class TestStudioAiSchemas:
    """Tests for GET /studio/ai/schemas endpoint."""
    
    def test_ai_schemas_returns_200(self):
        """AI schemas endpoint returns 200 OK."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/ai/schemas")
        
        assert response.status_code == 200
    
    def test_ai_schemas_returns_plan_schema(self):
        """AI schemas includes plan schema."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/ai/schemas")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "plan_schema" in data
        assert isinstance(data["plan_schema"], dict)
    
    def test_ai_schemas_returns_patch_schema(self):
        """AI schemas includes patch schema."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/ai/schemas")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "patch_schema" in data
        assert isinstance(data["patch_schema"], dict)
    
    def test_ai_schemas_returns_query_schema(self):
        """AI schemas includes query schema."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/ai/schemas")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "query_schema" in data
        assert isinstance(data["query_schema"], dict)
    
    def test_ai_schemas_returns_codegen_schema(self):
        """AI schemas includes codegen schema."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/ai/schemas")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "codegen_schema" in data
        assert isinstance(data["codegen_schema"], dict)


# =============================================================================
# GET /studio/ai/prompts Tests
# =============================================================================

class TestStudioAiPrompts:
    """Tests for GET /studio/ai/prompts endpoint."""
    
    def test_ai_prompts_returns_200(self):
        """AI prompts endpoint returns 200 OK."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/ai/prompts")
        
        assert response.status_code == 200
    
    def test_ai_prompts_returns_list(self):
        """AI prompts returns a list of templates."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/ai/prompts")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "prompts" in data
        assert isinstance(data["prompts"], list)
        assert len(data["prompts"]) > 0
    
    def test_ai_prompts_have_required_fields(self):
        """Each prompt template has required fields."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/ai/prompts")
        
        assert response.status_code == 200
        prompts = response.json()["prompts"]
        
        for prompt in prompts:
            assert "id" in prompt
            assert "title" in prompt
            assert "description" in prompt
            assert "template" in prompt
            assert "placeholders" in prompt
            
            # Verify non-empty
            assert prompt["id"]
            assert prompt["title"]
            assert prompt["template"]
    
    def test_ai_prompts_include_expected_templates(self):
        """AI prompts include expected template IDs."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/ai/prompts")
        
        assert response.status_code == 200
        prompts = response.json()["prompts"]
        
        prompt_ids = {p["id"] for p in prompts}
        
        # Should have these basic templates
        expected = {"add-field", "refactor-model", "fix-migrations", "natural-query"}
        assert expected.issubset(prompt_ids), f"Missing templates: {expected - prompt_ids}"
    
    def test_ai_prompts_include_version(self):
        """AI prompts response includes version."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/ai/prompts")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "version" in data
        assert data["version"] == "1.0"


# =============================================================================
# Model Tests
# =============================================================================

class TestStudioAiModels:
    """Tests for v0.5.4 AI Integration models."""
    
    def test_project_meta_instantiation(self):
        """StudioAiProjectMeta can be instantiated."""
        meta = StudioAiProjectMeta(
            name="Test App",
            version="0.5.4",
            environment="development",
            debug=True,
        )
        
        assert meta.name == "Test App"
        assert meta.version == "0.5.4"
        assert meta.environment == "development"
        assert meta.debug is True
    
    def test_model_summary_instantiation(self):
        """StudioAiModelSummary can be instantiated."""
        summary = StudioAiModelSummary(
            name="User",
            table_name="users",
            app_label="auth",
            fields=["id", "email", "name"],
            primary_key="id",
            has_timestamps=True,
        )
        
        assert summary.name == "User"
        assert summary.table_name == "users"
        assert summary.app_label == "auth"
        assert len(summary.fields) == 3
    
    def test_route_summary_instantiation(self):
        """StudioAiRouteSummary can be instantiated."""
        route = StudioAiRouteSummary(
            path="/api/users",
            methods=["GET", "POST"],
            name="users_list",
            is_authenticated=True,
        )
        
        assert route.path == "/api/users"
        assert route.methods == ["GET", "POST"]
        assert route.is_authenticated is True
    
    def test_tool_info_instantiation(self):
        """StudioAiToolInfo can be instantiated."""
        tool = StudioAiToolInfo(
            name="ai_query",
            description="Execute queries",
            endpoint="/ai/query",
            safe=True,
        )
        
        assert tool.name == "ai_query"
        assert tool.safe is True
    
    def test_context_export_instantiation(self):
        """StudioAiContextExport can be instantiated."""
        export = StudioAiContextExport(
            project=StudioAiProjectMeta(
                name="Test",
                version="1.0",
                environment="dev",
                debug=True,
            ),
            models=[],
            routes=[],
            tools=[],
            apps=["app"],
            migration_status=StudioMigrationStatus(),
            schema_checksum="abc123",
        )
        
        assert export.project.name == "Test"
        assert export.schema_checksum == "abc123"
    
    def test_schemas_instantiation(self):
        """StudioAiSchemas can be instantiated."""
        schemas = StudioAiSchemas(
            plan_schema={"type": "object"},
            patch_schema={"type": "object"},
            query_schema={"type": "object"},
            codegen_schema={"type": "object"},
            context_schema={"type": "object"},
        )
        
        assert "type" in schemas.plan_schema
        assert "type" in schemas.patch_schema
    
    def test_prompt_template_instantiation(self):
        """StudioAiPromptTemplate can be instantiated."""
        prompt = StudioAiPromptTemplate(
            id="test-prompt",
            title="Test Prompt",
            description="A test prompt",
            template="Hello {name}!",
            placeholders=["name"],
            category="test",
        )
        
        assert prompt.id == "test-prompt"
        assert prompt.placeholders == ["name"]
    
    def test_prompts_container_instantiation(self):
        """StudioAiPrompts can be instantiated."""
        prompts = StudioAiPrompts(
            prompts=[
                StudioAiPromptTemplate(
                    id="test",
                    title="Test",
                    description="Test",
                    template="Test",
                    placeholders=[],
                )
            ],
            version="1.0",
        )
        
        assert len(prompts.prompts) == 1
        assert prompts.version == "1.0"


# =============================================================================
# CLI Tests
# =============================================================================

class TestStudioAiCLI:
    """Tests for aksara studio ai-context CLI command."""
    
    def test_cli_ai_context_json(self):
        """aksara studio ai-context outputs JSON by default."""
        from click.testing import CliRunner
        from aksara.cli.main import cli
        
        runner = CliRunner()
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                result = runner.invoke(cli, ["studio", "ai-context"])
        
        assert result.exit_code == 0
        # Should contain JSON-like content
        assert "{" in result.output
        assert "project" in result.output
    
    def test_cli_ai_context_summary(self):
        """aksara studio ai-context --format summary outputs summary."""
        from click.testing import CliRunner
        from aksara.cli.main import cli
        
        runner = CliRunner()
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                result = runner.invoke(cli, ["studio", "ai-context", "--format", "summary"])
        
        assert result.exit_code == 0
        # Should contain summary keywords
        assert "Project:" in result.output
        assert "Environment:" in result.output
