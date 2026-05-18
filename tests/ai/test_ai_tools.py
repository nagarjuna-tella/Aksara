"""
Tests for AI tool discovery and registry.

Tests:
- AiTool model creation and validation
- AiToolRegistry registration and retrieval
- Tool discovery from ViewSets
- Tool discovery from @action decorated methods
- Permission-aware filtering
"""

import pytest
from unittest.mock import MagicMock, PropertyMock, patch
from typing import List, Type
from uuid import uuid4

from aksara.ai.models import AiTool, AiToolParam, ToolKind
from aksara.ai.registry import (
    AiToolRegistry,
    discover_tools_from_viewset,
    get_ai_tools_for_request,
    _determine_tool_kind,
    _get_ai_tags,
    _check_requires_auth,
    _check_requires_admin,
)


# =============================================================================
# AiTool Model Tests
# =============================================================================

class TestAiToolModel:
    """Tests for AiTool Pydantic model."""
    
    def test_create_basic_tool(self):
        """AiTool can be created with required fields."""
        tool = AiTool(
            name="users_list",
            title="List Users",
            http_method="GET",
            path="/api/users/",
        )
        
        assert tool.name == "users_list"
        assert tool.title == "List Users"
        assert tool.http_method == "GET"
        assert tool.path == "/api/users/"
        assert tool.kind == "query"  # default
        assert tool.ai_exposed is True  # default
    
    def test_create_full_tool(self):
        """AiTool can be created with all fields."""
        tool = AiTool(
            name="users_create",
            title="Create User",
            description="Create a new user account",
            http_method="POST",
            path="/api/users/",
            kind="mutation",
            model="User",
            app_label="users",
            input_schema={
                "type": "object",
                "properties": {
                    "email": {"type": "string"},
                    "password": {"type": "string"},
                },
                "required": ["email", "password"],
            },
            output_schema={
                "type": "object",
                "properties": {"id": {"type": "string"}},
            },
            requires_auth=True,
            requires_admin=False,
            permissions=["IsAuthenticated"],
            ai_tags=["write", "mutation"],
            ai_exposed=True,
            model_schema_endpoint="/ai/schema/User",
        )
        
        assert tool.name == "users_create"
        assert tool.kind == "mutation"
        assert tool.model == "User"
        assert tool.requires_auth is True
        assert tool.requires_admin is False
        assert "IsAuthenticated" in tool.permissions
        assert "write" in tool.ai_tags
        assert tool.input_schema["required"] == ["email", "password"]
    
    def test_tool_model_dump(self):
        """AiTool.model_dump() returns serializable dict."""
        tool = AiTool(
            name="posts_list",
            title="List Posts",
            http_method="GET",
            path="/api/posts/",
            model="Post",
        )
        
        data = tool.model_dump()
        
        assert isinstance(data, dict)
        assert data["name"] == "posts_list"
        assert data["model"] == "Post"
        assert data["ai_exposed"] is True
    
    def test_tool_kinds(self):
        """ToolKind literal types are valid."""
        for kind in ["query", "mutation", "action", "admin", "utility"]:
            tool = AiTool(
                name=f"test_{kind}",
                title=f"Test {kind}",
                http_method="GET",
                path="/test/",
                kind=kind,
            )
            assert tool.kind == kind


class TestAiToolParam:
    """Tests for AiToolParam model."""
    
    def test_create_param(self):
        """AiToolParam can be created."""
        param = AiToolParam(
            name="limit",
            description="Maximum items to return",
            required=False,
            json_schema={"type": "integer", "default": 20},
        )
        
        assert param.name == "limit"
        assert param.description == "Maximum items to return"
        assert param.required is False
        assert param.json_schema["type"] == "integer"


# =============================================================================
# AiToolRegistry Tests
# =============================================================================

class TestAiToolRegistry:
    """Tests for AiToolRegistry."""
    
    def test_registry_init(self):
        """Registry initializes empty."""
        registry = AiToolRegistry()
        
        assert len(registry) == 0
        assert registry.all_tools() == []
    
    def test_register_tool(self):
        """Tools can be registered."""
        registry = AiToolRegistry()
        
        tool = AiTool(
            name="users_list",
            title="List Users",
            http_method="GET",
            path="/api/users/",
        )
        
        registry.register_tool(tool)
        
        assert len(registry) == 1
        assert "users_list" in registry
        assert registry.get_tool("users_list") == tool
    
    def test_register_multiple_tools(self):
        """Multiple tools can be registered."""
        registry = AiToolRegistry()
        
        tools = [
            AiTool(name="users_list", title="List Users", http_method="GET", path="/api/users/"),
            AiTool(name="users_create", title="Create User", http_method="POST", path="/api/users/"),
            AiTool(name="posts_list", title="List Posts", http_method="GET", path="/api/posts/"),
        ]
        
        for tool in tools:
            registry.register_tool(tool)
        
        assert len(registry) == 3
        all_tools = registry.all_tools()
        assert len(all_tools) == 3
    
    def test_get_nonexistent_tool(self):
        """Getting a nonexistent tool returns None."""
        registry = AiToolRegistry()
        
        assert registry.get_tool("nonexistent") is None
    
    def test_clear_registry(self):
        """Registry can be cleared."""
        registry = AiToolRegistry()
        
        registry.register_tool(AiTool(
            name="test", title="Test", http_method="GET", path="/test/",
        ))
        
        assert len(registry) == 1
        
        registry.clear()
        
        assert len(registry) == 0
    
    def test_overwrite_tool_logs_warning(self):
        """Registering duplicate tool logs a warning."""
        registry = AiToolRegistry()
        
        tool1 = AiTool(name="users_list", title="List Users v1", http_method="GET", path="/v1/users/")
        tool2 = AiTool(name="users_list", title="List Users v2", http_method="GET", path="/v2/users/")
        
        registry.register_tool(tool1)
        
        with patch("aksara.ai.registry.logger") as mock_logger:
            registry.register_tool(tool2)
            mock_logger.warning.assert_called_once()
        
        # Should have overwritten
        assert registry.get_tool("users_list").title == "List Users v2"


# =============================================================================
# Tool Kind Determination Tests
# =============================================================================

class TestDetermineToolKind:
    """Tests for _determine_tool_kind helper."""
    
    def test_list_is_query(self):
        """List action should be query."""
        kind = _determine_tool_kind("list", "GET", False, [])
        assert kind == "query"
    
    def test_retrieve_is_query(self):
        """Retrieve action should be query."""
        kind = _determine_tool_kind("retrieve", "GET", True, [])
        assert kind == "query"
    
    def test_create_is_mutation(self):
        """Create action should be mutation."""
        kind = _determine_tool_kind("create", "POST", False, [])
        assert kind == "mutation"
    
    def test_update_is_mutation(self):
        """Update action should be mutation."""
        kind = _determine_tool_kind("update", "PATCH", True, [])
        assert kind == "mutation"
    
    def test_delete_is_mutation(self):
        """Delete action should be mutation."""
        kind = _determine_tool_kind("delete", "DELETE", True, [])
        assert kind == "mutation"
    
    def test_admin_only_is_admin(self):
        """Action with IsAdminUser should be admin kind."""
        from aksara.permissions import IsAdminUser
        
        kind = _determine_tool_kind("custom", "GET", False, [IsAdminUser])
        assert kind == "admin"


class TestGetAiTags:
    """Tests for _get_ai_tags helper."""
    
    def test_get_tags_returns_read_only_for_get(self):
        """GET requests should have read_only tag."""
        tags = _get_ai_tags("GET", "query", False)
        assert "read_only" in tags
        assert "safe" in tags
    
    def test_get_tags_returns_write_for_post(self):
        """POST requests should have write tag."""
        tags = _get_ai_tags("POST", "mutation", False)
        assert "write" in tags
    
    def test_get_tags_returns_destructive_for_delete(self):
        """DELETE requests should have destructive tag."""
        tags = _get_ai_tags("DELETE", "mutation", False)
        assert "destructive" in tags
    
    def test_get_tags_includes_admin(self):
        """Admin-required tools should have admin tag."""
        tags = _get_ai_tags("GET", "admin", True)
        assert "admin" in tags


class TestCheckRequiresAuth:
    """Tests for _check_requires_auth helper."""
    
    def test_no_permissions_returns_false(self):
        """No permissions means no auth required."""
        assert _check_requires_auth([]) is False
    
    def test_allow_any_returns_false(self):
        """AllowAny doesn't require auth."""
        from aksara.permissions import AllowAny
        assert _check_requires_auth([AllowAny]) is False
    
    def test_is_authenticated_returns_true(self):
        """IsAuthenticated requires auth."""
        from aksara.permissions import IsAuthenticated
        assert _check_requires_auth([IsAuthenticated]) is True
    
    def test_is_admin_returns_true(self):
        """IsAdminUser requires auth."""
        from aksara.permissions import IsAdminUser
        assert _check_requires_auth([IsAdminUser]) is True


class TestCheckRequiresAdmin:
    """Tests for _check_requires_admin helper."""
    
    def test_no_permissions_returns_false(self):
        """No permissions means no admin required."""
        assert _check_requires_admin([]) is False
    
    def test_is_authenticated_returns_false(self):
        """IsAuthenticated doesn't require admin."""
        from aksara.permissions import IsAuthenticated
        assert _check_requires_admin([IsAuthenticated]) is False
    
    def test_is_admin_returns_true(self):
        """IsAdminUser requires admin."""
        from aksara.permissions import IsAdminUser
        assert _check_requires_admin([IsAdminUser]) is True


# =============================================================================
# ViewSet Tool Discovery Tests
# =============================================================================

class TestDiscoverToolsFromViewSet:
    """Tests for discover_tools_from_viewset."""
    
    def test_discover_from_ai_exposed_viewset(self):
        """Tools are discovered from ai_exposed=True ViewSets."""
        from aksara.api.viewsets import ModelViewSet
        from aksara.model.base import Model
        from aksara import fields
        
        # Create a test model
        class TestUser(Model):
            __tablename__ = "test_users"
            id = fields.UUID(primary_key=True)
            email = fields.String(max_length=255)
        
        # Create a test ViewSet
        class TestUserViewSet(ModelViewSet):
            model = TestUser
            prefix = "/api/users"
            ai_exposed = True
        
        tools = discover_tools_from_viewset(TestUserViewSet)
        
        # Should have CRUD tools: list, retrieve, create, update, delete
        assert len(tools) >= 5
        
        tool_names = [t.name for t in tools]
        assert "testuser_list" in tool_names
        assert "testuser_retrieve" in tool_names
        assert "testuser_create" in tool_names
        assert "testuser_update" in tool_names
        assert "testuser_delete" in tool_names
    
    def test_no_tools_from_non_exposed_viewset(self):
        """No tools from ai_exposed=False ViewSets."""
        from aksara.api.viewsets import ModelViewSet
        from aksara.model.base import Model
        from aksara import fields
        
        class HiddenModel(Model):
            __tablename__ = "hidden"
            id = fields.UUID(primary_key=True)
        
        class HiddenViewSet(ModelViewSet):
            model = HiddenModel
            prefix = "/api/hidden"
            ai_exposed = False
        
        tools = discover_tools_from_viewset(HiddenViewSet)
        
        assert len(tools) == 0

    def test_no_tools_from_model_hidden_from_ai(self):
        """No tools are discovered when the model is hidden from AI."""
        from aksara.api.viewsets import ModelViewSet
        from aksara.model.base import Model
        from aksara import fields

        class HiddenModel(Model):
            __tablename__ = "hidden_models"
            id = fields.UUID(primary_key=True)

            class Meta:
                ai_agent_exposed = False

        class HiddenModelViewSet(ModelViewSet):
            model = HiddenModel
            prefix = "/api/hidden-models"
            ai_exposed = True

        tools = discover_tools_from_viewset(HiddenModelViewSet)

        assert tools == []
    
    def test_discover_actions_from_viewset(self):
        """Custom @action methods are discovered."""
        from aksara.api.viewsets import ModelViewSet
        from aksara.api import action
        from aksara.model.base import Model
        from aksara import fields
        
        class ActionModel(Model):
            __tablename__ = "action_models"
            id = fields.UUID(primary_key=True)
            is_active = fields.Boolean(default=True)
        
        class ActionViewSet(ModelViewSet):
            model = ActionModel
            prefix = "/api/items"
            ai_exposed = True
            
            @action(detail=True, methods=["post"], summary="Activate Item")
            async def activate(self, pk, request):
                """Activate the item."""
                pass
            
            @action(detail=False, methods=["get"], summary="List Active")
            async def active(self, request):
                """List active items."""
                pass
        
        tools = discover_tools_from_viewset(ActionViewSet)
        
        tool_names = [t.name for t in tools]
        assert "actionmodel_activate" in tool_names
        assert "actionmodel_active" in tool_names
    
    def test_action_ai_exposed_false_skipped(self):
        """Actions with ai_exposed=False are skipped."""
        from aksara.api.viewsets import ModelViewSet
        from aksara.api import action
        from aksara.model.base import Model
        from aksara import fields
        
        class SecretModel(Model):
            __tablename__ = "secrets"
            id = fields.UUID(primary_key=True)
        
        class SecretViewSet(ModelViewSet):
            model = SecretModel
            prefix = "/api/secrets"
            ai_exposed = True
            
            @action(detail=True, methods=["post"], ai_exposed=False)
            async def sensitive(self, pk, request):
                """Sensitive action hidden from AI."""
                pass
            
            @action(detail=True, methods=["get"], ai_exposed=True)
            async def public(self, pk, request):
                """Public action visible to AI."""
                pass
        
        tools = discover_tools_from_viewset(SecretViewSet)
        
        tool_names = [t.name for t in tools]
        assert "secretmodel_sensitive" not in tool_names
        assert "secretmodel_public" in tool_names
    
    def test_tool_permissions_captured(self):
        """Permission classes are captured in tool metadata."""
        from aksara.api.viewsets import ModelViewSet
        from aksara.permissions import IsAuthenticated, IsAdminUser
        from aksara.model.base import Model
        from aksara import fields
        
        class AdminModel(Model):
            __tablename__ = "admin_items"
            id = fields.UUID(primary_key=True)
        
        class AdminViewSet(ModelViewSet):
            model = AdminModel
            prefix = "/api/admin"
            ai_exposed = True
            permission_classes = [IsAuthenticated, IsAdminUser]
        
        tools = discover_tools_from_viewset(AdminViewSet)
        
        for tool in tools:
            assert "IsAuthenticated" in tool.permissions
            assert "IsAdminUser" in tool.permissions
            assert tool.requires_auth is True
            assert tool.requires_admin is True


# =============================================================================
# Permission-aware Filtering Tests
# =============================================================================

class TestGetAiToolsForRequest:
    """Tests for get_ai_tools_for_request."""
    
    @pytest.mark.asyncio
    async def test_anonymous_user_gets_public_tools(self):
        """Anonymous users only get tools without auth requirements."""
        from aksara.ai.registry import AiToolRegistry
        
        registry = AiToolRegistry()
        
        # Public tool
        registry.register_tool(AiTool(
            name="public_list",
            title="Public List",
            http_method="GET",
            path="/api/public/",
            requires_auth=False,
        ))
        
        # Auth-required tool
        registry.register_tool(AiTool(
            name="users_list",
            title="List Users",
            http_method="GET",
            path="/api/users/",
            requires_auth=True,
            permissions=["IsAuthenticated"],
        ))
        
        # Create mock app with registry
        app = MagicMock()
        app.ai_registry = registry
        
        # Create anonymous request
        request = MagicMock()
        request.app = app
        request.state = MagicMock(spec=[])  # No user
        
        tools = await get_ai_tools_for_request(request, app)
        
        tool_names = [t.name for t in tools]
        assert "public_list" in tool_names
        assert "users_list" not in tool_names
    
    @pytest.mark.asyncio
    async def test_authenticated_user_gets_auth_tools(self):
        """Authenticated users get auth-required tools."""
        from aksara.ai.registry import AiToolRegistry
        
        registry = AiToolRegistry()
        
        registry.register_tool(AiTool(
            name="users_list",
            title="List Users",
            http_method="GET",
            path="/api/users/",
            requires_auth=True,
            permissions=["IsAuthenticated"],
        ))
        
        app = MagicMock()
        app.ai_registry = registry
        
        # Create authenticated request
        request = MagicMock()
        request.app = app
        
        user = MagicMock()
        user.is_authenticated = True
        request.state.user = user
        
        tools = await get_ai_tools_for_request(request, app)
        
        tool_names = [t.name for t in tools]
        assert "users_list" in tool_names
    
    @pytest.mark.asyncio
    async def test_admin_user_gets_admin_tools(self):
        """Admin users get admin-required tools."""
        from aksara.ai.registry import AiToolRegistry
        
        registry = AiToolRegistry()
        
        registry.register_tool(AiTool(
            name="admin_panel",
            title="Admin Panel",
            http_method="GET",
            path="/api/admin/",
            requires_auth=True,
            requires_admin=True,
            permissions=["IsAdminUser"],
        ))
        
        app = MagicMock()
        app.ai_registry = registry
        
        # Create admin request
        request = MagicMock()
        request.app = app
        
        user = MagicMock()
        user.is_authenticated = True
        user.is_staff = True
        request.state.user = user
        
        tools = await get_ai_tools_for_request(request, app)
        
        tool_names = [t.name for t in tools]
        assert "admin_panel" in tool_names
    
    @pytest.mark.asyncio
    async def test_non_admin_user_blocked_from_admin_tools(self):
        """Non-admin users don't get admin-required tools."""
        from aksara.ai.registry import AiToolRegistry
        
        registry = AiToolRegistry()
        
        registry.register_tool(AiTool(
            name="admin_panel",
            title="Admin Panel",
            http_method="GET",
            path="/api/admin/",
            requires_auth=True,
            requires_admin=True,
            permissions=["IsAdminUser"],
        ))
        
        app = MagicMock()
        app.ai_registry = registry
        
        # Create non-admin authenticated request
        request = MagicMock()
        request.app = app
        
        user = MagicMock()
        user.is_authenticated = True
        user.is_staff = False
        user.is_superuser = False
        request.state.user = user
        
        tools = await get_ai_tools_for_request(request, app)
        
        tool_names = [t.name for t in tools]
        assert "admin_panel" not in tool_names
    
    @pytest.mark.asyncio
    async def test_deny_ai_permission_blocks_tool(self):
        """Tools with DenyAI permission are not exposed."""
        from aksara.ai.registry import AiToolRegistry
        
        registry = AiToolRegistry()
        
        registry.register_tool(AiTool(
            name="sensitive",
            title="Sensitive",
            http_method="GET",
            path="/api/sensitive/",
            requires_auth=False,
            permissions=["DenyAI"],
        ))
        
        app = MagicMock()
        app.ai_registry = registry
        
        request = MagicMock()
        request.app = app
        request.state = MagicMock(spec=[])
        
        tools = await get_ai_tools_for_request(request, app)
        
        tool_names = [t.name for t in tools]
        assert "sensitive" not in tool_names
    
    @pytest.mark.asyncio
    async def test_no_registry_returns_empty(self):
        """Returns empty list if no registry on app."""
        app = MagicMock()
        app.ai_registry = None
        
        request = MagicMock()
        request.app = app
        
        tools = await get_ai_tools_for_request(request, app)
        
        assert tools == []
