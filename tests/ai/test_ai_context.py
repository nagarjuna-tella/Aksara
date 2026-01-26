"""
Tests for Vidyut AI Context Engine (v0.4.3)

Comprehensive tests for the AI Context module including:
- Pydantic model validation
- Model extraction
- ViewSet extraction
- Route extraction
- Settings extraction
- Admin extraction
- Middleware extraction
- AI tools extraction
- Full context building
- Endpoint tests
- Checksum stability
- Determinism tests
"""

import pytest
import json
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from pydantic import ValidationError

from vidyut import Model, fields, Vidyut, ModelViewSet, include_viewset, action
from vidyut.registry import ModelRegistry
from vidyut.conf import settings, configure, reset_settings


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset model registry before each test."""
    ModelRegistry.clear()
    yield
    ModelRegistry.clear()


@pytest.fixture
def sample_model():
    """Create a sample model for testing."""
    class Article(Model):
        title = fields.String(max_length=200, ai_description="Article title")
        body = fields.Text(ai_description="Article body content")
        is_published = fields.Boolean(default=False)
        view_count = fields.Integer(default=0, ai_agent_writable=False)
        created_at = fields.DateTime(ai_sensitive=False)
        
        class Meta:
            table_name = "articles"
            app_label = "blog"
            ai_name = "BlogArticle"
            ai_description = "A blog article with title and body"
            ai_agent_exposed = True
            ai_permissions = ["read", "write"]
    
    return Article


@pytest.fixture
def sample_model_with_fk():
    """Create models with foreign key relationships."""
    class Author(Model):
        name = fields.String(max_length=100)
        email = fields.Email()
        
        class Meta:
            table_name = "authors"
    
    class Post(Model):
        title = fields.String(max_length=200)
        author = fields.ForeignKey("Author", on_delete="CASCADE")
        
        class Meta:
            table_name = "posts"
    
    return Author, Post


@pytest.fixture
def sample_viewset(sample_model):
    """Create a sample ViewSet."""
    from vidyut.permissions import IsAuthenticated
    
    class ArticleViewSet(ModelViewSet):
        model = sample_model
        prefix = "/articles"
        tags = ["Articles", "Blog"]
        permission_classes = [IsAuthenticated]
        ai_exposed = True
        default_limit = 25
        max_limit = 200
        
        @action(detail=False, methods=["GET"], summary="Get featured articles")
        async def featured(self, request):
            return {"featured": []}
        
        @action(detail=True, methods=["POST"], summary="Publish article")
        async def publish(self, pk, request):
            return {"published": True}
    
    return ArticleViewSet


@pytest.fixture
def sample_app(sample_model, sample_viewset):
    """Create a minimal Vidyut app for testing."""
    app = Vidyut(
        title="Test App",
        version="1.0.0",
        ai_enabled=True,
    )
    include_viewset(app, sample_viewset)
    
    # Initialize viewset registry if not present
    if not hasattr(app.state, 'viewset_registry'):
        app.state.viewset_registry = [sample_viewset]
    
    return app


# =============================================================================
# Pydantic Model Tests
# =============================================================================


class TestAiModelFieldInfo:
    """Tests for AiModelFieldInfo model."""
    
    def test_basic_field_info(self):
        """Test basic field info creation."""
        from vidyut.ai.context import AiModelFieldInfo
        
        field = AiModelFieldInfo(
            name="title",
            db_column="title",
            field_type="String",
            python_type="str",
        )
        
        assert field.name == "title"
        assert field.field_type == "String"
        assert field.python_type == "str"
        assert field.nullable is False
        assert field.ai_agent_writable is True
    
    def test_field_with_fk(self):
        """Test field info with foreign key."""
        from vidyut.ai.context import AiModelFieldInfo
        
        field = AiModelFieldInfo(
            name="author",
            db_column="author_id",
            field_type="ForeignKey",
            python_type="int",
            fk_to_model="Author",
            fk_on_delete="CASCADE",
        )
        
        assert field.fk_to_model == "Author"
        assert field.fk_on_delete == "CASCADE"
    
    def test_field_with_ai_metadata(self):
        """Test field info with AI metadata."""
        from vidyut.ai.context import AiModelFieldInfo
        
        field = AiModelFieldInfo(
            name="password",
            db_column="password",
            field_type="String",
            python_type="str",
            ai_sensitive=True,
            ai_agent_writable=False,
            ai_description="User password (hashed)",
        )
        
        assert field.ai_sensitive is True
        assert field.ai_agent_writable is False
        assert "password" in field.ai_description.lower()


class TestAiModelInfo:
    """Tests for AiModelInfo model."""
    
    def test_basic_model_info(self):
        """Test basic model info creation."""
        from vidyut.ai.context import AiModelInfo, AiModelFieldInfo
        
        model = AiModelInfo(
            name="User",
            table_name="users",
            fields=[
                AiModelFieldInfo(
                    name="id",
                    db_column="id",
                    field_type="UUID",
                    python_type="UUID",
                    primary_key=True,
                )
            ],
        )
        
        assert model.name == "User"
        assert model.table_name == "users"
        assert len(model.fields) == 1
        assert model.ai_agent_exposed is True
    
    def test_model_with_ai_metadata(self):
        """Test model info with AI metadata."""
        from vidyut.ai.context import AiModelInfo
        
        model = AiModelInfo(
            name="Article",
            table_name="articles",
            ai_name="BlogPost",
            ai_description="A blog post",
            ai_permissions=["read"],
        )
        
        assert model.ai_name == "BlogPost"
        assert model.ai_description == "A blog post"
        assert model.ai_permissions == ["read"]


class TestAiRelationInfo:
    """Tests for AiRelationInfo model."""
    
    def test_foreign_key_relation(self):
        """Test FK relation info."""
        from vidyut.ai.context import AiRelationInfo
        
        rel = AiRelationInfo(
            name="author",
            relation_type="foreign_key",
            from_model="Post",
            to_model="Author",
            on_delete="CASCADE",
        )
        
        assert rel.relation_type == "foreign_key"
        assert rel.on_delete == "CASCADE"
    
    def test_m2m_relation(self):
        """Test M2M relation info."""
        from vidyut.ai.context import AiRelationInfo
        
        rel = AiRelationInfo(
            name="tags",
            relation_type="many_to_many",
            from_model="Article",
            to_model="Tag",
            through_model="ArticleTag",
        )
        
        assert rel.relation_type == "many_to_many"
        assert rel.through_model == "ArticleTag"


class TestAiViewSetInfo:
    """Tests for AiViewSetInfo model."""
    
    def test_basic_viewset_info(self):
        """Test basic ViewSet info."""
        from vidyut.ai.context import AiViewSetInfo
        
        vs = AiViewSetInfo(
            name="ArticleViewSet",
            model_name="Article",
            prefix="/articles",
            tags=["Articles"],
        )
        
        assert vs.name == "ArticleViewSet"
        assert vs.model_name == "Article"
        assert vs.prefix == "/articles"
        assert vs.supports_list is True
    
    def test_viewset_with_actions(self):
        """Test ViewSet with custom actions."""
        from vidyut.ai.context import AiViewSetInfo, AiActionInfo
        
        vs = AiViewSetInfo(
            name="ArticleViewSet",
            model_name="Article",
            prefix="/articles",
            actions=[
                AiActionInfo(
                    name="publish",
                    url_path="publish",
                    methods=["POST"],
                    detail=True,
                )
            ],
        )
        
        assert len(vs.actions) == 1
        assert vs.actions[0].name == "publish"


class TestAiActionInfo:
    """Tests for AiActionInfo model."""
    
    def test_collection_action(self):
        """Test collection action (detail=False)."""
        from vidyut.ai.context import AiActionInfo
        
        action = AiActionInfo(
            name="featured",
            url_path="featured",
            methods=["GET"],
            detail=False,
            summary="Get featured items",
        )
        
        assert action.detail is False
        assert action.methods == ["GET"]
    
    def test_detail_action(self):
        """Test detail action (detail=True)."""
        from vidyut.ai.context import AiActionInfo
        
        action = AiActionInfo(
            name="approve",
            url_path="approve",
            methods=["POST"],
            detail=True,
        )
        
        assert action.detail is True


class TestAiRouteInfo:
    """Tests for AiRouteInfo model."""
    
    def test_basic_route(self):
        """Test basic route info."""
        from vidyut.ai.context import AiRouteInfo
        
        route = AiRouteInfo(
            path="/api/users",
            methods=["GET", "POST"],
            tags=["Users"],
        )
        
        assert route.path == "/api/users"
        assert "GET" in route.methods
        assert route.deprecated is False
    
    def test_route_with_source(self):
        """Test route with source type."""
        from vidyut.ai.context import AiRouteInfo
        
        route = AiRouteInfo(
            path="/admin/users",
            methods=["GET"],
            source_type="admin",
        )
        
        assert route.source_type == "admin"


class TestAiMigrationInfo:
    """Tests for AiMigrationInfo model."""
    
    def test_migration_info(self):
        """Test migration info."""
        from vidyut.ai.context import AiMigrationInfo
        
        mig = AiMigrationInfo(
            name="0001_initial",
            app_label="blog",
            operations_count=3,
            operations_summary=["CreateTable", "AddColumn", "AddIndex"],
            applied=True,
        )
        
        assert mig.name == "0001_initial"
        assert mig.applied is True
        assert len(mig.operations_summary) == 3


class TestAiAdminInfo:
    """Tests for AiAdminInfo model."""
    
    def test_admin_disabled(self):
        """Test admin when disabled."""
        from vidyut.ai.context import AiAdminInfo
        
        admin = AiAdminInfo(enabled=False)
        
        assert admin.enabled is False
        assert admin.total_models == 0
    
    def test_admin_with_models(self):
        """Test admin with registered models."""
        from vidyut.ai.context import AiAdminInfo, AiAdminModelInfo
        
        admin = AiAdminInfo(
            enabled=True,
            site_name="admin",
            registered_models=[
                AiAdminModelInfo(
                    model_name="Article",
                    list_display=["title", "created_at"],
                )
            ],
            total_models=1,
        )
        
        assert admin.enabled is True
        assert len(admin.registered_models) == 1


class TestAiSettingsInfo:
    """Tests for AiSettingsInfo model."""
    
    def test_settings_info(self):
        """Test settings info."""
        from vidyut.ai.context import AiSettingsInfo
        
        settings = AiSettingsInfo(
            app_title="My App",
            debug=True,
            ai_enabled=True,
            installed_apps=["app", "blog"],
        )
        
        assert settings.app_title == "My App"
        assert settings.debug is True
        assert settings.ai_enabled is True
    
    def test_settings_no_credentials(self):
        """Verify settings don't expose credentials."""
        from vidyut.ai.context import AiSettingsInfo
        
        settings = AiSettingsInfo(
            database_configured=True,
        )
        
        # Should not have database_url field
        assert not hasattr(settings, 'database_url')
        assert settings.database_configured is True


class TestAiMiddlewareInfo:
    """Tests for AiMiddlewareInfo model."""
    
    def test_middleware_info(self):
        """Test middleware info."""
        from vidyut.ai.context import AiMiddlewareInfo
        
        mw = AiMiddlewareInfo(
            name="RequestIDMiddleware",
            module="vidyut.middleware.request_id",
            order=0,
            config={"header_name": "X-Request-ID"},
        )
        
        assert mw.name == "RequestIDMiddleware"
        assert mw.order == 0


class TestAiToolSummary:
    """Tests for AiToolSummary model."""
    
    def test_tool_summary(self):
        """Test tool summary."""
        from vidyut.ai.context import AiToolSummary
        
        tool = AiToolSummary(
            name="users_list",
            description="List all users",
            kind="query",
            http_method="GET",
            endpoint="/api/users",
        )
        
        assert tool.kind == "query"
        assert tool.http_method == "GET"


class TestAiSchemaInfo:
    """Tests for AiSchemaInfo model."""
    
    def test_schema_info(self):
        """Test schema info."""
        from vidyut.ai.context import AiSchemaInfo
        
        schema = AiSchemaInfo(
            name="AiQueryPlan",
            description="Query plan schema",
            schema_type="pydantic",
            json_schema={"type": "object", "properties": {}},
        )
        
        assert schema.name == "AiQueryPlan"
        assert schema.schema_type == "pydantic"


class TestAiFullContext:
    """Tests for AiFullContext model."""
    
    def test_full_context(self):
        """Test full context creation."""
        from vidyut.ai.context import AiFullContext
        
        context = AiFullContext(
            framework_version="0.4.3",
            generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            checksum="abc123",
        )
        
        assert context.framework == "vidyut"
        assert context.framework_version == "0.4.3"
        assert context.context_version == "1.0.0"
    
    def test_full_context_with_data(self):
        """Test full context with all data."""
        from vidyut.ai.context import (
            AiFullContext, AiModelInfo, AiViewSetInfo,
            AiSettingsInfo, AiAdminInfo
        )
        
        context = AiFullContext(
            framework_version="0.4.3",
            generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            checksum="abc123",
            models=[AiModelInfo(name="User", table_name="users")],
            model_count=1,
            viewsets=[AiViewSetInfo(name="UserViewSet", model_name="User", prefix="/users")],
            viewset_count=1,
        )
        
        assert context.model_count == 1
        assert context.viewset_count == 1


# =============================================================================
# Extraction Function Tests
# =============================================================================


class TestModelExtraction:
    """Tests for model extraction."""
    
    def test_extract_model_info(self, sample_model):
        """Test extracting model info."""
        from vidyut.ai.context import _extract_model_info
        
        info = _extract_model_info(sample_model)
        
        assert info.name == "Article"
        assert info.table_name == "articles"
        assert info.app_label == "blog"
        assert info.ai_name == "BlogArticle"
        assert "read" in info.ai_permissions
    
    def test_extract_model_fields(self, sample_model):
        """Test extracting model fields."""
        from vidyut.ai.context import _extract_model_info
        
        info = _extract_model_info(sample_model)
        
        # Find title field
        title_field = next((f for f in info.fields if f.name == "title"), None)
        assert title_field is not None
        assert title_field.field_type == "String"
        assert title_field.max_length == 200
        
        # Find view_count field (not AI writable)
        view_count = next((f for f in info.fields if f.name == "view_count"), None)
        assert view_count is not None
        assert view_count.ai_agent_writable is False
    
    def test_extract_model_with_fk(self, sample_model_with_fk):
        """Test extracting model with FK."""
        from vidyut.ai.context import _extract_model_info
        
        Author, Post = sample_model_with_fk
        
        post_info = _extract_model_info(Post)
        
        # Check FK field
        author_field = next((f for f in post_info.fields if f.name == "author"), None)
        assert author_field is not None
        assert author_field.fk_to_model == "Author"
        
        # Check relation
        assert len(post_info.relations) >= 1
        fk_rel = next((r for r in post_info.relations if r.relation_type == "foreign_key"), None)
        assert fk_rel is not None


class TestViewSetExtraction:
    """Tests for ViewSet extraction."""
    
    def test_extract_viewset_info(self, sample_viewset):
        """Test extracting ViewSet info."""
        from vidyut.ai.context import _extract_viewset_info
        
        info = _extract_viewset_info(sample_viewset)
        
        assert info.name == "ArticleViewSet"
        assert info.model_name == "Article"
        assert info.prefix == "/articles"
        assert "Articles" in info.tags
        assert info.default_limit == 25
    
    def test_extract_viewset_actions(self, sample_viewset):
        """Test extracting ViewSet actions."""
        from vidyut.ai.context import _extract_viewset_info
        
        info = _extract_viewset_info(sample_viewset)
        
        # Should have 2 custom actions
        assert len(info.actions) >= 2
        
        # Find featured action
        featured = next((a for a in info.actions if a.name == "featured"), None)
        assert featured is not None
        assert featured.detail is False
        
        # Find publish action
        publish = next((a for a in info.actions if a.name == "publish"), None)
        assert publish is not None
        assert publish.detail is True
    
    def test_extract_viewset_permissions(self, sample_viewset):
        """Test extracting ViewSet permissions."""
        from vidyut.ai.context import _extract_viewset_info
        
        info = _extract_viewset_info(sample_viewset)
        
        assert "IsAuthenticated" in info.permission_classes


class TestRouteExtraction:
    """Tests for route extraction."""
    
    def test_extract_routes(self, sample_app):
        """Test extracting routes from app."""
        from vidyut.ai.context import _extract_routes_from_app
        
        routes = _extract_routes_from_app(sample_app)
        
        # Should have routes for articles
        article_routes = [r for r in routes if "/articles" in r.path]
        assert len(article_routes) > 0
    
    def test_routes_sorted(self, sample_app):
        """Test that routes are sorted deterministically."""
        from vidyut.ai.context import _extract_routes_from_app
        
        routes = _extract_routes_from_app(sample_app)
        
        # Check sorting
        paths = [r.path for r in routes]
        assert paths == sorted(paths)


class TestSettingsExtraction:
    """Tests for settings extraction."""
    
    def test_extract_settings(self):
        """Test extracting settings."""
        from vidyut.ai.context import _extract_settings_info
        
        info = _extract_settings_info()
        
        assert isinstance(info.debug, bool)
        assert isinstance(info.installed_apps, list)
        assert isinstance(info.log_level, str)
    
    def test_settings_no_secrets(self):
        """Test that settings don't expose secrets."""
        from vidyut.ai.context import _extract_settings_info
        
        info = _extract_settings_info()
        
        # Should not have actual database URL
        dump = info.model_dump()
        assert 'database_url' not in dump
        assert 'secret_key' not in dump


class TestAdminExtraction:
    """Tests for admin extraction."""
    
    def test_extract_admin_disabled(self):
        """Test extracting admin when none registered."""
        from vidyut.ai.context import _extract_admin_info
        from vidyut.contrib.admin import site
        
        # Clear admin registry
        site.clear()
        
        info = _extract_admin_info()
        
        # May be enabled but with no models
        assert info.total_models == 0


class TestMiddlewareExtraction:
    """Tests for middleware extraction."""
    
    def test_extract_middleware(self, sample_app):
        """Test extracting middleware."""
        from vidyut.ai.context import _extract_middleware_info
        
        middleware = _extract_middleware_info(sample_app)
        
        # Should be a list
        assert isinstance(middleware, list)


class TestAiToolsExtraction:
    """Tests for AI tools extraction."""
    
    def test_extract_ai_tools_empty(self, sample_app):
        """Test extracting AI tools when none registered."""
        from vidyut.ai.context import _extract_ai_tools_info
        
        tools = _extract_ai_tools_info(sample_app)
        
        # May be empty if no registry
        assert isinstance(tools, list)


class TestAiSchemasExtraction:
    """Tests for AI schemas extraction."""
    
    def test_extract_ai_schemas(self):
        """Test extracting AI schemas."""
        from vidyut.ai.context import _extract_ai_schemas_info
        
        schemas = _extract_ai_schemas_info()
        
        # Should have query plan and codegen schemas
        assert len(schemas) > 0
        
        # Check for query plan schema
        query_schema = next((s for s in schemas if s.name == "AiQueryPlan"), None)
        assert query_schema is not None


# =============================================================================
# Full Context Building Tests
# =============================================================================


class TestBuildFullContext:
    """Tests for build_full_ai_context function."""
    
    @pytest.mark.asyncio
    async def test_build_full_context(self, sample_app):
        """Test building full context."""
        from vidyut.ai.context import build_full_ai_context
        
        context = await build_full_ai_context(sample_app)
        
        assert context.framework == "vidyut"
        assert context.framework_version is not None
        assert context.checksum is not None
        assert context.generated_at is not None
    
    @pytest.mark.asyncio
    async def test_context_includes_models(self, sample_app, sample_model):
        """Test that context includes models."""
        from vidyut.ai.context import build_full_ai_context
        
        context = await build_full_ai_context(sample_app)
        
        # Should have at least the sample model
        assert context.model_count >= 1
        
        # Find Article model
        article = next((m for m in context.models if m.name == "Article"), None)
        assert article is not None
    
    @pytest.mark.asyncio
    async def test_context_includes_viewsets(self, sample_app):
        """Test that context includes ViewSets."""
        from vidyut.ai.context import build_full_ai_context
        
        context = await build_full_ai_context(sample_app)
        
        # Should have ViewSets if registry is set
        if hasattr(sample_app.state, 'viewset_registry'):
            assert context.viewset_count >= 1
    
    @pytest.mark.asyncio
    async def test_context_includes_routes(self, sample_app):
        """Test that context includes routes."""
        from vidyut.ai.context import build_full_ai_context
        
        context = await build_full_ai_context(sample_app)
        
        assert context.route_count >= 0
    
    @pytest.mark.asyncio
    async def test_context_includes_settings(self, sample_app):
        """Test that context includes settings."""
        from vidyut.ai.context import build_full_ai_context
        
        context = await build_full_ai_context(sample_app)
        
        assert context.settings is not None
        assert isinstance(context.settings.installed_apps, list)
    
    @pytest.mark.asyncio
    async def test_context_includes_schemas(self, sample_app):
        """Test that context includes AI schemas."""
        from vidyut.ai.context import build_full_ai_context
        
        context = await build_full_ai_context(sample_app)
        
        assert len(context.ai_schemas) > 0


class TestContextDeterminism:
    """Tests for context determinism."""
    
    @pytest.mark.asyncio
    async def test_checksum_stable(self, sample_app, sample_model):
        """Test that checksum is stable for same state."""
        from vidyut.ai.context import build_full_ai_context
        
        context1 = await build_full_ai_context(sample_app)
        context2 = await build_full_ai_context(sample_app)
        
        # Checksums should be the same (ignoring timestamp)
        assert context1.checksum == context2.checksum
    
    @pytest.mark.asyncio
    async def test_models_sorted(self, sample_app):
        """Test that models are sorted deterministically."""
        from vidyut.ai.context import build_full_ai_context
        
        context = await build_full_ai_context(sample_app)
        
        # Check sorting by (app_label, name)
        model_keys = [(m.app_label, m.name) for m in context.models]
        assert model_keys == sorted(model_keys)
    
    @pytest.mark.asyncio
    async def test_fields_included(self, sample_app, sample_model):
        """Test that fields are included in deterministic order."""
        from vidyut.ai.context import build_full_ai_context
        
        context = await build_full_ai_context(sample_app)
        
        # Find Article model
        article = next((m for m in context.models if m.name == "Article"), None)
        assert article is not None
        
        # Should have fields
        assert len(article.fields) > 0


class TestContextSerialization:
    """Tests for context serialization."""
    
    @pytest.mark.asyncio
    async def test_json_serializable(self, sample_app):
        """Test that context is JSON serializable."""
        from vidyut.ai.context import build_full_ai_context
        
        context = await build_full_ai_context(sample_app)
        
        # Should serialize without error
        json_str = json.dumps(context.model_dump(), default=str)
        assert isinstance(json_str, str)
        
        # Should parse back
        parsed = json.loads(json_str)
        assert parsed["framework"] == "vidyut"
    
    @pytest.mark.asyncio
    async def test_no_circular_refs(self, sample_app):
        """Test that there are no circular references."""
        from vidyut.ai.context import build_full_ai_context
        
        context = await build_full_ai_context(sample_app)
        
        # json.dumps will fail on circular refs
        try:
            json.dumps(context.model_dump(), default=str)
        except ValueError as e:
            pytest.fail(f"Circular reference detected: {e}")


# =============================================================================
# Endpoint Tests
# =============================================================================


class TestContextEndpoints:
    """Tests for context endpoints."""
    
    def test_full_context_endpoint(self, sample_app):
        """Test GET /ai/context/full endpoint."""
        from fastapi.testclient import TestClient
        from vidyut.ai import ai_router
        
        sample_app.include_router(ai_router)
        client = TestClient(sample_app)
        
        response = client.get("/ai/context/full")
        
        assert response.status_code == 200
        data = response.json()
        assert data["framework"] == "vidyut"
        assert "checksum" in data
    
    def test_models_endpoint(self, sample_app, sample_model):
        """Test GET /ai/context/models endpoint."""
        from fastapi.testclient import TestClient
        from vidyut.ai import ai_router
        
        sample_app.include_router(ai_router)
        client = TestClient(sample_app)
        
        response = client.get("/ai/context/models")
        
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert "model_count" in data
    
    def test_viewsets_endpoint(self, sample_app):
        """Test GET /ai/context/viewsets endpoint."""
        from fastapi.testclient import TestClient
        from vidyut.ai import ai_router
        
        sample_app.include_router(ai_router)
        client = TestClient(sample_app)
        
        response = client.get("/ai/context/viewsets")
        
        assert response.status_code == 200
        data = response.json()
        assert "viewsets" in data
        assert "viewset_count" in data
    
    def test_settings_endpoint(self, sample_app):
        """Test GET /ai/context/settings endpoint."""
        from fastapi.testclient import TestClient
        from vidyut.ai import ai_router
        
        sample_app.include_router(ai_router)
        client = TestClient(sample_app)
        
        response = client.get("/ai/context/settings")
        
        assert response.status_code == 200
        data = response.json()
        assert "settings" in data
        assert "middleware" in data
    
    def test_routes_endpoint(self, sample_app):
        """Test GET /ai/context/routes endpoint."""
        from fastapi.testclient import TestClient
        from vidyut.ai import ai_router
        
        sample_app.include_router(ai_router)
        client = TestClient(sample_app)
        
        response = client.get("/ai/context/routes")
        
        assert response.status_code == 200
        data = response.json()
        assert "routes" in data
        assert "route_count" in data
    
    def test_admin_endpoint(self, sample_app):
        """Test GET /ai/context/admin endpoint."""
        from fastapi.testclient import TestClient
        from vidyut.ai import ai_router
        
        sample_app.include_router(ai_router)
        client = TestClient(sample_app)
        
        response = client.get("/ai/context/admin")
        
        assert response.status_code == 200
        data = response.json()
        assert "admin" in data


# =============================================================================
# Edge Cases & Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_model(self):
        """Test model with minimal fields."""
        from vidyut.ai.context import _extract_model_info
        
        class MinimalModel(Model):
            name = fields.String(max_length=50)
            
            class Meta:
                table_name = "minimal"
        
        info = _extract_model_info(MinimalModel)
        
        assert info.name == "MinimalModel"
        assert len(info.fields) >= 1
    
    def test_model_no_ai_meta(self):
        """Test model without AiMeta class."""
        from vidyut.ai.context import _extract_model_info
        
        class SimpleModel(Model):
            name = fields.String(max_length=100)
            
            class Meta:
                table_name = "simple"
        
        info = _extract_model_info(SimpleModel)
        
        # Should use defaults
        assert info.ai_agent_exposed is True
        assert info.ai_permissions == ["read", "write", "delete"]
    
    def test_viewset_no_actions(self, sample_model):
        """Test ViewSet with no custom actions."""
        from vidyut.ai.context import _extract_viewset_info
        
        class BasicViewSet(ModelViewSet):
            model = sample_model
            prefix = "/basic"
        
        info = _extract_viewset_info(BasicViewSet)
        
        assert info.name == "BasicViewSet"
        # May have 0 custom actions
        assert isinstance(info.actions, list)


class TestFieldTypes:
    """Tests for various field types."""
    
    def test_all_field_types(self):
        """Test extraction of all field types."""
        from vidyut.ai.context import _extract_model_info
        
        class AllFieldsModel(Model):
            name = fields.String(max_length=100)
            bio = fields.Text()
            is_active = fields.Boolean()
            created = fields.DateTime()
            price = fields.Decimal(max_digits=10, decimal_places=2)
            uid = fields.UUID()
            data = fields.JSON()
            email = fields.Email()
            website = fields.URL()
            
            class Meta:
                table_name = "all_fields"
        
        info = _extract_model_info(AllFieldsModel)
        
        # Should have all fields (plus auto id, created_at, updated_at)
        assert len(info.fields) >= 9
        
        # Check specific types
        field_types = {f.name: f.field_type for f in info.fields}
        assert field_types.get("bio") == "Text"
        assert field_types.get("price") == "Decimal"
        assert field_types.get("email") == "Email"


class TestAiFieldType:
    """Tests for AiFieldType enum."""
    
    def test_field_type_values(self):
        """Test AiFieldType enum values."""
        from vidyut.ai.context import AiFieldType
        
        assert AiFieldType.INTEGER.value == "integer"
        assert AiFieldType.STRING.value == "string"
        assert AiFieldType.BOOLEAN.value == "boolean"
        assert AiFieldType.FOREIGN_KEY.value == "foreign_key"


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestModuleExports:
    """Tests for module exports."""
    
    def test_context_exports(self):
        """Test that context module exports are available."""
        from vidyut.ai import (
            AiFieldType,
            AiModelFieldInfo,
            AiModelInfo,
            AiViewSetInfo,
            AiActionInfo,
            AiRouteInfo,
            AiMigrationInfo,
            AiAdminInfo,
            AiSettingsInfo,
            AiMiddlewareInfo,
            AiFullContext,
            build_full_ai_context,
        )
        
        # All should be importable
        assert AiFieldType is not None
        assert AiModelFieldInfo is not None
        assert AiFullContext is not None
        assert build_full_ai_context is not None
    
    def test_all_list_complete(self):
        """Test that __all__ includes context exports."""
        from vidyut.ai import __all__
        
        context_exports = [
            "AiFieldType",
            "AiModelFieldInfo",
            "AiModelInfo",
            "AiFullContext",
            "build_full_ai_context",
        ]
        
        for export in context_exports:
            assert export in __all__
