"""
Aksara AI Hints - Per-View Route-Level AI Metadata

v0.5.13: Developer API for declaring AI hints on views/routes.

This module provides:
- @ai_route_hint decorator for annotating viewset actions/route handlers
- Helper functions for extracting hints from viewsets and routes
- Building AiHintSet from discovered hints

Usage:
    from aksara.ai import ai_route_hint
    
    class PostViewSet(AksaraViewSet):
        @action(detail=True, methods=["post"])
        @ai_route_hint(
            title="Publish a blog post",
            description="Marks the given post as published.",
            usage_kind="write",
            risk_level="medium",
            example_prompt="User says: 'Publish my draft about async APIs'",
            example_input={"id": 42},
            example_output={"id": 42, "is_published": True},
        )
        async def publish(self, request, id: int):
            ...
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, TypeVar

from aksara.ai.models import (
    AiHintSet,
    AiRiskLevel,
    AiRouteHint,
    AiUsageKind,
)
from aksara.routing import iter_routes

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("aksara.ai.hints")

F = TypeVar('F', bound=Callable[..., Any])

# Attribute name for storing hints on functions and classes
HINT_ATTR = "_aksara_ai_hint"
DEFAULT_HINT_ATTR = "_aksara_ai_default_hint"


# =============================================================================
# Decorator API
# =============================================================================

def ai_route_hint(
    *,
    title: str,
    description: str = "",
    usage_kind: AiUsageKind = "read_only",
    risk_level: AiRiskLevel = "low",
    example_prompt: Optional[str] = None,
    example_input: Optional[Dict[str, Any]] = None,
    example_output: Optional[Dict[str, Any]] = None,
    recommended_model: Optional[str] = None,
    recommended_provider: Optional[str] = None,
) -> Callable[[F], F]:
    """
    Decorator to attach AI metadata to viewset actions or route handlers.
    
    This metadata helps LLMs understand what the route does, how risky it is,
    and provides examples for prompting. No provider coupling - pure metadata.
    
    Args:
        title: Short label for the route (e.g., "Publish blog post")
        description: 1-3 sentence AI-facing description
        usage_kind: "read_only", "write", or "admin"
        risk_level: "low", "medium", or "high"
        example_prompt: Example user prompt that would trigger this route
        example_input: Example request body/parameters
        example_output: Example response body
        recommended_model: Optional recommended AI model name
        recommended_provider: Optional recommended AI provider name
    
    Returns:
        Decorated function with _aksara_ai_hint attribute
    
    Example:
        @action(detail=True, methods=["post"])
        @ai_route_hint(
            title="Publish a blog post",
            description="Marks the given post as published.",
            usage_kind="write",
            risk_level="medium",
        )
        async def publish(self, request, id: int):
            ...
    """
    def decorator(fn: F) -> F:
        hint_data = {
            "title": title,
            "description": description,
            "usage_kind": usage_kind,
            "risk_level": risk_level,
            "example_prompt": example_prompt,
            "example_input": example_input,
            "example_output": example_output,
            "recommended_model": recommended_model,
            "recommended_provider": recommended_provider,
        }
        setattr(fn, HINT_ATTR, hint_data)
        return fn
    
    return decorator


def set_view_default_hint(
    viewset_cls: type,
    *,
    title: str,
    description: str = "",
    usage_kind: AiUsageKind = "read_only",
    risk_level: AiRiskLevel = "low",
    recommended_model: Optional[str] = None,
    recommended_provider: Optional[str] = None,
) -> None:
    """
    Set a default AI hint for all actions in a viewset.
    
    Individual action hints (via @ai_route_hint) will override this default.
    
    Args:
        viewset_cls: ViewSet class to set the default on
        title: Default title for routes in this viewset
        description: Default description
        usage_kind: Default usage classification
        risk_level: Default risk level
        recommended_model: Optional default recommended model
        recommended_provider: Optional default recommended provider
    
    Example:
        class PostViewSet(AksaraViewSet):
            ...
        
        set_view_default_hint(
            PostViewSet,
            title="Blog posts API",
            description="Read and manage blog posts.",
            usage_kind="read_only",
            risk_level="low",
        )
    """
    hint_data = {
        "title": title,
        "description": description,
        "usage_kind": usage_kind,
        "risk_level": risk_level,
        "recommended_model": recommended_model,
        "recommended_provider": recommended_provider,
    }
    setattr(viewset_cls, DEFAULT_HINT_ATTR, hint_data)


def get_hint_from_callable(fn: Callable) -> Optional[Dict[str, Any]]:
    """Extract hint data from a decorated callable."""
    return getattr(fn, HINT_ATTR, None)


# Alias for public API
get_ai_route_hint = get_hint_from_callable


def get_default_hint_from_class(cls: type) -> Optional[Dict[str, Any]]:
    """Extract default hint from a viewset class."""
    return getattr(cls, DEFAULT_HINT_ATTR, None)


# =============================================================================
# Hint Extraction from Application
# =============================================================================

def extract_hints_from_app(app: "FastAPI") -> List[AiRouteHint]:
    """
    Extract all AI hints from a FastAPI application.
    
    Inspects:
    - Registered Aksara viewsets and their actions
    - FastAPI route handlers
    - Looks for _aksara_ai_hint and _aksara_ai_default_hint attributes
    
    Args:
        app: The FastAPI/Aksara application instance
        
    Returns:
        List of AiRouteHint objects for all hinted routes
    """
    hints: List[AiRouteHint] = []
    
    # Track processed routes to avoid duplicates
    processed_paths: set = set()
    
    # First, check for registered viewsets
    viewset_registry = getattr(app.state, 'viewset_registry', None)
    if viewset_registry:
        for vs_cls in viewset_registry:
            hints.extend(_extract_hints_from_viewset(vs_cls))
            
            # Mark viewset routes as processed
            prefix = getattr(vs_cls, 'prefix', '') or vs_cls.__name__.lower().replace('viewset', '')
            processed_paths.add(f"/api/{prefix}")
    
    # Then, check direct FastAPI routes
    for route in iter_routes(app):
        path = getattr(route, 'path', '')
        if not path or path in processed_paths:
            continue
        
        # Skip internal routes
        if path in ('/', '/docs', '/redoc', '/openapi.json'):
            continue
        
        # Get the route endpoint handler
        endpoint = getattr(route, 'endpoint', None)
        if endpoint is None:
            continue
        
        hint_data = get_hint_from_callable(endpoint)
        if hint_data is None:
            continue
        
        methods = list(getattr(route, 'methods', None) or []) or ['GET']
        name = getattr(route, 'name', None) or path.replace('/', '_').strip('_')
        
        hint = AiRouteHint(
            app_label="",
            view_name=endpoint.__qualname__ if hasattr(endpoint, '__qualname__') else str(endpoint),
            route_name=name,
            path=path,
            methods=methods,
            title=hint_data.get("title", name),
            description=hint_data.get("description", ""),
            usage_kind=hint_data.get("usage_kind", "read_only"),
            risk_level=hint_data.get("risk_level", "low"),
            example_prompt=hint_data.get("example_prompt"),
            example_input=hint_data.get("example_input"),
            example_output=hint_data.get("example_output"),
            recommended_model=hint_data.get("recommended_model"),
            recommended_provider=hint_data.get("recommended_provider"),
        )
        hints.append(hint)
        processed_paths.add(path)
    
    # Sort deterministically
    hints.sort(key=lambda h: (h.view_name, h.route_name, h.path))
    
    return hints


def _extract_hints_from_viewset(viewset_cls: type) -> List[AiRouteHint]:
    """Extract hints from a single viewset class."""
    from aksara.api.actions import get_action_metadata

    hints: List[AiRouteHint] = []
    
    # Get viewset metadata
    view_name = viewset_cls.__name__
    app_label = getattr(viewset_cls, 'app_label', '') or ""
    prefix = getattr(viewset_cls, 'prefix', '') or view_name.lower().replace('viewset', '')
    
    # Get default hint if any
    default_hint = get_default_hint_from_class(viewset_cls) or {}
    
    # Standard CRUD operations to check
    crud_operations = [
        ('list', 'GET', f'/api/{prefix}/', f'{prefix}-list'),
        ('retrieve', 'GET', f'/api/{prefix}/{{id}}/', f'{prefix}-detail'),
        ('create', 'POST', f'/api/{prefix}/', f'{prefix}-create'),
        ('update', 'PUT', f'/api/{prefix}/{{id}}/', f'{prefix}-update'),
        ('partial_update', 'PATCH', f'/api/{prefix}/{{id}}/', f'{prefix}-partial-update'),
        ('destroy', 'DELETE', f'/api/{prefix}/{{id}}/', f'{prefix}-delete'),
    ]
    
    for method_name, http_method, path, route_name in crud_operations:
        method = getattr(viewset_cls, method_name, None)
        if method is None:
            continue
        
        hint_data = get_hint_from_callable(method)
        if hint_data is None and not default_hint:
            continue
        
        # Merge with default hint
        merged = {**default_hint}
        if hint_data:
            merged.update({k: v for k, v in hint_data.items() if v is not None})
        
        if not merged.get("title"):
            continue  # No hint defined
        
        hint = AiRouteHint(
            app_label=app_label,
            view_name=view_name,
            route_name=route_name,
            path=path,
            methods=[http_method],
            title=merged.get("title", route_name),
            description=merged.get("description", ""),
            usage_kind=merged.get("usage_kind", "read_only"),
            risk_level=merged.get("risk_level", "low"),
            example_prompt=merged.get("example_prompt"),
            example_input=merged.get("example_input"),
            example_output=merged.get("example_output"),
            recommended_model=merged.get("recommended_model"),
            recommended_provider=merged.get("recommended_provider"),
        )
        hints.append(hint)
    
    # Check for custom @action methods
    for attr_name in dir(viewset_cls):
        if attr_name.startswith('_'):
            continue
        
        attr = getattr(viewset_cls, attr_name, None)
        if not callable(attr):
            continue
        
        # Skip standard CRUD
        if attr_name in ('list', 'retrieve', 'create', 'update', 'partial_update', 'destroy'):
            continue
        
        hint_data = get_hint_from_callable(attr)
        if hint_data is None:
            continue

        action_meta = get_action_metadata(attr)
        if action_meta is None:
            continue
        
        # Use the stored action metadata so detail/path/methods stay accurate.
        action_detail = action_meta["detail"]
        action_methods = action_meta["methods"]
        action_url_path = action_meta["path"]
        
        if action_detail:
            path = f'/api/{prefix}/{{id}}/{action_url_path}/'
        else:
            path = f'/api/{prefix}/{action_url_path}/'
        
        route_name = f'{prefix}-{attr_name}'
        
        hint = AiRouteHint(
            app_label=app_label,
            view_name=view_name,
            route_name=route_name,
            path=path,
            methods=list(action_methods) if isinstance(action_methods, (list, tuple)) else [action_methods],
            title=hint_data.get("title", attr_name),
            description=hint_data.get("description", ""),
            usage_kind=hint_data.get("usage_kind", "read_only"),
            risk_level=hint_data.get("risk_level", "low"),
            example_prompt=hint_data.get("example_prompt"),
            example_input=hint_data.get("example_input"),
            example_output=hint_data.get("example_output"),
            recommended_model=hint_data.get("recommended_model"),
            recommended_provider=hint_data.get("recommended_provider"),
        )
        hints.append(hint)
    
    return hints


# Public alias for viewset extraction
extract_hints_from_viewset = _extract_hints_from_viewset


# =============================================================================
# Build Hint Set
# =============================================================================

def build_ai_hint_set(app: "FastAPI") -> AiHintSet:
    """
    Build a complete AiHintSet from the application.
    
    Args:
        app: The FastAPI/Aksara application instance
        
    Returns:
        AiHintSet with all discovered hints and computed stats
    """
    hints = extract_hints_from_app(app)
    
    # Compute stats
    read_only_count = sum(1 for h in hints if h.usage_kind == "read_only")
    write_count = sum(1 for h in hints if h.usage_kind == "write")
    admin_count = sum(1 for h in hints if h.usage_kind == "admin")
    
    low_risk_count = sum(1 for h in hints if h.risk_level == "low")
    medium_risk_count = sum(1 for h in hints if h.risk_level == "medium")
    high_risk_count = sum(1 for h in hints if h.risk_level == "high")
    
    return AiHintSet(
        routes=hints,
        total_count=len(hints),
        read_only_count=read_only_count,
        write_count=write_count,
        admin_count=admin_count,
        low_risk_count=low_risk_count,
        medium_risk_count=medium_risk_count,
        high_risk_count=high_risk_count,
    )


def build_ai_hint_set_sync(app: "FastAPI") -> AiHintSet:
    """
    Synchronous version of build_ai_hint_set.
    
    For use in CLI and other sync contexts.
    """
    return build_ai_hint_set(app)


__all__ = [
    # Decorator
    "ai_route_hint",
    # Helpers
    "set_view_default_hint",
    "get_hint_from_callable",
    "get_default_hint_from_class",
    # Extraction
    "extract_hints_from_app",
    "build_ai_hint_set",
    "build_ai_hint_set_sync",
    # Constants
    "HINT_ATTR",
    "DEFAULT_HINT_ATTR",
]
