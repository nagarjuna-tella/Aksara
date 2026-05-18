"""
Aksara AI Tool Registry

Central registry for discovering and managing AI tools from ViewSets and actions.

Provides:
- AiToolRegistry: Storage for discovered AI tools
- discover_tools_from_viewset: Introspect ViewSets to extract tools
- get_ai_tools_for_request: Permission-aware tool filtering
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, List, Optional, Type, TYPE_CHECKING

from fastapi import Request

from aksara.ai.models import AiTool, ToolKind

if TYPE_CHECKING:
    from aksara.api.viewsets import ModelViewSet
    from aksara.permissions import BasePermission

logger = logging.getLogger("aksara.ai")


class AiToolRegistry:
    """
    Central registry for AI tools.
    
    Stores all discovered AI tools and provides access methods.
    Should be attached to the Aksara app instance.
    
    Usage:
        registry = AiToolRegistry()
        registry.register_tool(tool)
        
        all_tools = registry.all_tools()
        specific_tool = registry.get_tool("users_list")
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._tools: Dict[str, AiTool] = {}
    
    def register_tool(self, tool: AiTool) -> None:
        """
        Register a tool in the registry.
        
        If a tool with the same name exists, it will be overwritten
        with a warning logged.
        
        Args:
            tool: The AiTool to register
        """
        if tool.name in self._tools:
            logger.warning(
                f"Tool '{tool.name}' already registered, overwriting"
            )
        self._tools[tool.name] = tool
    
    def all_tools(self) -> List[AiTool]:
        """
        Get all registered tools.
        
        Returns:
            List of all AiTool instances
        """
        return list(self._tools.values())
    
    def get_tool(self, name: str) -> Optional[AiTool]:
        """
        Get a tool by name.
        
        Args:
            name: The tool name
            
        Returns:
            The AiTool if found, None otherwise
        """
        return self._tools.get(name)
    
    def clear(self) -> None:
        """Clear all registered tools (useful for testing)."""
        self._tools.clear()
    
    def __len__(self) -> int:
        """Return number of registered tools."""
        return len(self._tools)
    
    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools


def _determine_tool_kind(
    action_name: str,
    http_method: str,
    is_detail: bool,
    permission_classes: List[Type["BasePermission"]],
) -> ToolKind:
    """
    Determine the kind of tool based on action and method.
    
    Args:
        action_name: The action name (list, retrieve, create, etc.)
        http_method: HTTP method
        is_detail: Whether it's a detail action
        permission_classes: List of permission classes
        
    Returns:
        The appropriate ToolKind
    """
    # Check for admin-only
    from aksara.permissions import IsAdminUser
    
    is_admin_only = any(
        perm is IsAdminUser or (isinstance(perm, type) and issubclass(perm, IsAdminUser))
        for perm in permission_classes
    )
    
    if is_admin_only:
        return "admin"
    
    # Standard CRUD mapping
    if action_name in ("list", "retrieve") or http_method == "GET":
        return "query"
    elif action_name in ("create", "update", "partial_update", "delete"):
        return "mutation"
    elif http_method in ("POST", "PATCH", "PUT", "DELETE"):
        return "mutation"
    else:
        return "action"


def _get_ai_tags(
    http_method: str,
    kind: ToolKind,
    requires_admin: bool,
) -> List[str]:
    """
    Generate AI tags based on tool characteristics.
    
    Args:
        http_method: HTTP method
        kind: Tool kind
        requires_admin: Whether admin is required
        
    Returns:
        List of AI tags
    """
    tags = []
    
    if http_method == "GET":
        tags.append("read_only")
        tags.append("safe")
    elif http_method in ("POST", "PUT", "PATCH"):
        tags.append("write")
    elif http_method == "DELETE":
        tags.append("write")
        tags.append("destructive")
    
    if kind == "query":
        tags.append("query")
    elif kind == "mutation":
        tags.append("mutation")
    
    if requires_admin:
        tags.append("admin")
    
    return tags


def _check_requires_auth(permission_classes: List[Type["BasePermission"]]) -> bool:
    """Check if any permission requires authentication."""
    from aksara.permissions import IsAuthenticated, IsAdminUser, IsActiveUser, IsOwnerOrReadOnly
    
    auth_permissions = (IsAuthenticated, IsAdminUser, IsActiveUser, IsOwnerOrReadOnly)
    
    for perm in permission_classes:
        if isinstance(perm, type):
            if issubclass(perm, auth_permissions):
                return True
        elif isinstance(perm, auth_permissions):
            return True
    
    return False


def _check_requires_admin(permission_classes: List[Type["BasePermission"]]) -> bool:
    """Check if admin permission is required."""
    from aksara.permissions import IsAdminUser
    
    for perm in permission_classes:
        if perm is IsAdminUser:
            return True
        if isinstance(perm, type) and issubclass(perm, IsAdminUser):
            return True
        if isinstance(perm, IsAdminUser):
            return True
    
    return False


def _get_permission_names(permission_classes: List[Type["BasePermission"]]) -> List[str]:
    """Get string names of permission classes."""
    names = []
    for perm in permission_classes:
        if isinstance(perm, type):
            names.append(perm.__name__)
        else:
            names.append(perm.__class__.__name__)
    return names


def _build_input_schema_for_crud(
    viewset: "ModelViewSet",
    action_name: str,
    http_method: str,
) -> Dict[str, Any]:
    """
    Build JSON Schema for CRUD operation input.
    
    Args:
        viewset: The ViewSet instance
        action_name: The action name
        http_method: HTTP method
        
    Returns:
        JSON Schema dict
    """

    def _get_ai_writable_input_names() -> set[str]:
        """Return AI-safe writable property names for CRUD input schemas."""
        from aksara.registry import get_model_fields

        allowed_names: set[str] = set()

        for field_meta in get_model_fields(
            viewset.model,
            include_sensitive=False,
            writable_only=True,
        ):
            allowed_names.add(field_meta["name"])
            allowed_names.add(field_meta["db_column"])

        for field_name, field in getattr(viewset.model, "_m2m_fields", {}).items():
            if getattr(field, "ai_sensitive", False):
                continue
            if not getattr(field, "ai_agent_writable", True):
                continue
            allowed_names.add(field_name)

        return allowed_names

    def _sanitize_mutation_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
        """Strip sensitive and non-writable fields from AI mutation schemas."""
        allowed_names = _get_ai_writable_input_names()
        sanitized_schema = dict(schema)
        properties = dict(schema.get("properties", {}))

        sanitized_schema["properties"] = {
            name: definition
            for name, definition in properties.items()
            if name in allowed_names
        }

        required = [
            name
            for name in schema.get("required", [])
            if name in sanitized_schema["properties"]
        ]
        if required:
            sanitized_schema["required"] = required
        else:
            sanitized_schema.pop("required", None)

        return sanitized_schema

    if http_method == "GET":
        # List/retrieve - query parameters
        if action_name == "list":
            return {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "default": viewset.default_limit,
                        "description": "Maximum number of items to return"
                    },
                    "offset": {
                        "type": "integer",
                        "default": 0,
                        "description": "Number of items to skip"
                    }
                }
            }
        else:
            # Retrieve by ID
            return {
                "type": "object",
                "properties": {
                    "pk": {
                        "type": "string",
                        "description": f"{viewset.model.__name__} ID"
                    }
                },
                "required": ["pk"]
            }
    
    elif http_method == "POST":
        # Create - use create schema
        try:
            schema_cls = viewset.create_schema
            if hasattr(schema_cls, "model_json_schema"):
                return _sanitize_mutation_schema(schema_cls.model_json_schema())
        except Exception:
            pass
        
        return {"type": "object", "properties": {}}
    
    elif http_method in ("PATCH", "PUT"):
        # Update - use update schema
        try:
            schema_cls = viewset.update_schema
            if hasattr(schema_cls, "model_json_schema"):
                schema = _sanitize_mutation_schema(schema_cls.model_json_schema())
                # Add pk to required
                schema.setdefault("properties", {})["pk"] = {
                    "type": "string",
                    "description": f"{viewset.model.__name__} ID"
                }
                return schema
        except Exception:
            pass
        
        return {
            "type": "object",
            "properties": {
                "pk": {"type": "string", "description": "ID of item to update"}
            },
            "required": ["pk"]
        }
    
    elif http_method == "DELETE":
        return {
            "type": "object",
            "properties": {
                "pk": {"type": "string", "description": "ID of item to delete"}
            },
            "required": ["pk"]
        }
    
    return {"type": "object", "properties": {}}


def discover_tools_from_viewset(
    viewset_cls: Type["ModelViewSet"],
    prefix_override: Optional[str] = None,
) -> List[AiTool]:
    """
    Discover AI tools from a ModelViewSet class.
    
    Inspects the ViewSet for:
    - CRUD endpoints (list, retrieve, create, update, delete)
    - Custom @action decorated methods
    
    Only includes tools where ai_exposed=True on both the ViewSet
    and individual actions.
    
    Args:
        viewset_cls: The ModelViewSet class to inspect
        prefix_override: Optional URL prefix override
        
    Returns:
        List of discovered AiTool instances
    """
    from aksara.api.actions import get_action_metadata, is_action_ai_exposed
    
    tools = []
    
    # Skip if ViewSet is not AI-exposed
    if not getattr(viewset_cls, "ai_exposed", True):
        logger.debug(f"Skipping ViewSet {viewset_cls.__name__}: ai_exposed=False")
        return tools
    
    # Instantiate ViewSet to access properties
    try:
        viewset = viewset_cls()
    except Exception as e:
        logger.warning(f"Could not instantiate {viewset_cls.__name__}: {e}")
        return tools
    
    model = viewset.model
    if model is None:
        logger.warning(f"ViewSet {viewset_cls.__name__} has no model")
        return tools

    # Match model-level AI exposure rules: hidden models expose no tools.
    if not getattr(getattr(model, "_ai_meta", None), "ai_agent_exposed", True):
        logger.debug(f"Skipping ViewSet {viewset_cls.__name__}: model ai_agent_exposed=False")
        return tools
    
    model_name = model.__name__
    prefix = prefix_override or viewset.prefix.rstrip("/")
    permission_classes = viewset.permission_classes
    
    requires_auth = _check_requires_auth(permission_classes)
    requires_admin = _check_requires_admin(permission_classes)
    permission_names = _get_permission_names(permission_classes)
    
    # Base tool kwargs
    base_kwargs = {
        "model": model_name,
        "requires_auth": requires_auth,
        "requires_admin": requires_admin,
        "permissions": permission_names,
        "ai_exposed": True,
        "model_schema_endpoint": f"/ai/schema/{model_name}",
    }
    
    # =========================================================================
    # CRUD Tools
    # =========================================================================
    
    crud_operations = [
        ("list", "GET", f"{prefix}/", False, f"List {model_name}", f"Get a paginated list of {model_name} records"),
        ("retrieve", "GET", f"{prefix}/{{pk}}", True, f"Get {model_name}", f"Retrieve a single {model_name} by ID"),
        ("create", "POST", f"{prefix}/", False, f"Create {model_name}", f"Create a new {model_name}"),
        ("update", "PATCH", f"{prefix}/{{pk}}", True, f"Update {model_name}", f"Partially update a {model_name}"),
        ("delete", "DELETE", f"{prefix}/{{pk}}", True, f"Delete {model_name}", f"Delete a {model_name}"),
    ]
    
    for action_name, http_method, path, is_detail, title, description in crud_operations:
        kind = _determine_tool_kind(action_name, http_method, is_detail, permission_classes)
        ai_tags = _get_ai_tags(http_method, kind, requires_admin)
        
        tool = AiTool(
            name=f"{model_name.lower()}_{action_name}",
            title=title,
            description=description,
            http_method=http_method,
            path=path,
            kind=kind,
            input_schema=_build_input_schema_for_crud(viewset, action_name, http_method),
            ai_tags=ai_tags,
            **base_kwargs,
        )
        tools.append(tool)
    
    # =========================================================================
    # Custom @action Tools
    # =========================================================================
    
    for attr_name in dir(viewset):
        if attr_name.startswith("_"):
            continue
        
        try:
            method = getattr(viewset, attr_name)
        except AttributeError:
            continue
        
        if not callable(method):
            continue
        
        meta = get_action_metadata(method)
        if meta is None:
            continue
        
        # Check action-level ai_exposed
        if not meta.get("ai_exposed", True):
            logger.debug(f"Skipping action {attr_name}: ai_exposed=False")
            continue
        
        # Get action-specific permissions
        action_permissions = meta.get("permission_classes")
        if action_permissions is not None:
            action_requires_auth = _check_requires_auth(action_permissions)
            action_requires_admin = _check_requires_admin(action_permissions)
            action_permission_names = _get_permission_names(action_permissions)
        else:
            # Inherit from ViewSet
            action_requires_auth = requires_auth
            action_requires_admin = requires_admin
            action_permission_names = permission_names
        
        # Build action path
        action_path = meta["path"]
        is_detail = meta["detail"]
        
        if is_detail:
            full_path = f"{prefix}/{{pk}}/{action_path}"
        else:
            full_path = f"{prefix}/{action_path}"
        
        # Action can have multiple methods
        for http_method in meta["methods"]:
            kind = _determine_tool_kind(attr_name, http_method, is_detail, 
                                       action_permissions or permission_classes)
            ai_tags = _get_ai_tags(http_method, kind, action_requires_admin)
            
            # Try to get docstring for description
            docstring = method.__doc__ or ""
            summary = meta.get("summary") or docstring.split("\n")[0].strip() or f"{attr_name} action"
            
            # Build action name
            action_tool_name = f"{model_name.lower()}_{attr_name}"
            if len(meta["methods"]) > 1:
                action_tool_name += f"_{http_method.lower()}"
            
            # Build input schema from function signature
            input_schema = {"type": "object", "properties": {}}
            if is_detail:
                input_schema["properties"]["pk"] = {
                    "type": "string",
                    "description": f"{model_name} ID"
                }
                input_schema["required"] = ["pk"]
            
            tool = AiTool(
                name=action_tool_name,
                title=meta.get("summary") or attr_name.replace("_", " ").title(),
                description=summary,
                http_method=http_method,
                path=full_path,
                kind=kind,
                model=model_name,
                input_schema=input_schema,
                requires_auth=action_requires_auth,
                requires_admin=action_requires_admin,
                permissions=action_permission_names,
                ai_tags=ai_tags,
                ai_exposed=True,
                model_schema_endpoint=f"/ai/schema/{model_name}",
            )
            tools.append(tool)
    
    return tools


def _check_permission_allows_ai(permission_classes: List[Type["BasePermission"]]) -> bool:
    """
    Check if permission classes allow AI access.
    
    Returns False if any permission has ai_allow=False.
    """
    from aksara.permissions import DenyAI
    
    for perm_cls in permission_classes:
        # Check for DenyAI
        if perm_cls is DenyAI:
            return False
        if isinstance(perm_cls, type) and issubclass(perm_cls, DenyAI):
            return False
        
        # Check ai_allow attribute
        if isinstance(perm_cls, type):
            instance = perm_cls()
        else:
            instance = perm_cls
        
        if not getattr(instance, "ai_allow", True):
            return False
    
    return True


async def _check_permission_for_request(
    request: Request,
    permission_classes: List[Type["BasePermission"]],
) -> bool:
    """
    Check if request passes permission checks.
    
    Args:
        request: The incoming request
        permission_classes: List of permission classes to check
        
    Returns:
        True if all permissions pass, False otherwise
    """
    for perm_cls in permission_classes:
        if isinstance(perm_cls, type):
            perm = perm_cls()
        else:
            perm = perm_cls
        
        # Check ai_allow first
        if not getattr(perm, "ai_allow", True):
            return False
        
        # Check has_permission
        if not perm.has_permission(request, None):
            return False
    
    return True


async def get_ai_tools_for_request(
    request: Request,
    app: Any,
) -> List[AiTool]:
    """
    Get AI tools filtered by permissions for the current request.
    
    This function:
    1. Gets all tools from the registry
    2. Filters out tools where ai_exposed=False
    3. Filters out tools blocked by DenyAI or ai_allow=False
    4. Filters based on authentication/authorization requirements
    
    Args:
        request: The incoming FastAPI request
        app: The Aksara app instance (must have ai_registry attribute)
        
    Returns:
        List of AiTool instances the current user can access
    """
    # Get registry from app
    registry: Optional[AiToolRegistry] = getattr(app, "ai_registry", None)
    if registry is None:
        logger.warning("No AI registry found on app")
        return []
    
    all_tools = registry.all_tools()
    filtered_tools = []
    
    # Helper to safely get user from request
    def get_user():
        """Extract user from request, handling Starlette's assertion."""
        # Try request.state.user first (Aksara/Starlette style)
        if hasattr(request, "state") and hasattr(request.state, "user"):
            return request.state.user
        
        # Try request.user but catch assertion error
        # Starlette raises AssertionError if AuthenticationMiddleware is not installed
        try:
            if hasattr(request, "user") and "user" in getattr(request, "scope", {}):
                return request.user
        except (AssertionError, AttributeError):
            pass
        
        return None
    
    user = get_user()
    
    for tool in all_tools:
        # Skip if not AI-exposed
        if not tool.ai_exposed:
            continue
        
        # Skip if DenyAI is in permissions
        if "DenyAI" in tool.permissions:
            continue
        
        # Check authentication requirement
        if tool.requires_auth:
            is_authenticated = (
                user is not None and 
                getattr(user, "is_authenticated", False)
            )
            
            if not is_authenticated:
                continue
        
        # Check admin requirement
        if tool.requires_admin:
            is_admin = (
                user is not None and
                (getattr(user, "is_staff", False) or 
                 getattr(user, "is_superuser", False))
            )
            
            if not is_admin:
                continue
        
        filtered_tools.append(tool)
    
    return filtered_tools
