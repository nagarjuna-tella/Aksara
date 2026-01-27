"""
Aksara Auto-Discovery Module

Provides utilities for automatically discovering ViewSets from modules and apps.

Usage:
    from aksara.core.discovery import discover_viewsets_from_module, discover_viewsets_from_apps
    
    # Single module discovery
    import myapp.views
    viewsets = discover_viewsets_from_module(myapp.views)
    
    # Multi-app discovery
    viewsets = discover_viewsets_from_apps(["app", "blog", "accounts"])
"""

from __future__ import annotations

import logging
from importlib import import_module
from typing import List, Optional, Set, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from aksara.api.viewsets import ModelViewSet

logger = logging.getLogger(__name__)


def import_module_safely(path: str) -> Optional[object]:
    """
    Import module by path. If import fails, return None instead of raising.
    
    Args:
        path: Dotted import path (e.g., "app.views")
        
    Returns:
        Module object if import succeeds, None otherwise
    """
    try:
        return import_module(path)
    except ImportError as e:
        logger.debug(f"Could not import module '{path}': {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error importing module '{path}': {e}")
        return None


def discover_viewsets_from_module(module) -> List[Type["ModelViewSet"]]:
    """
    Inspect a module and return a list of ModelViewSet subclasses.
    
    Only includes classes that:
    - Are subclasses of ModelViewSet
    - Are not the base ModelViewSet itself
    - Have a model attribute defined (not None)
    
    Args:
        module: Python module object to inspect
        
    Returns:
        List of ModelViewSet subclasses found in the module
    """
    # Import here to avoid circular imports
    from aksara.api.viewsets import ModelViewSet
    
    viewsets: List[Type[ModelViewSet]] = []
    seen: Set[Type[ModelViewSet]] = set()
    
    for name in dir(module):
        # Skip private/dunder attributes
        if name.startswith("_"):
            continue
        
        try:
            attr = getattr(module, name)
        except AttributeError:
            continue
        
        # Check if it's a class
        if not isinstance(attr, type):
            continue
        
        # Check if it's a ModelViewSet subclass (but not the base class)
        if not issubclass(attr, ModelViewSet):
            continue
        
        if attr is ModelViewSet:
            continue
        
        # Check if model is defined
        model = getattr(attr, "model", None)
        if model is None:
            continue
        
        # Deduplicate (same class might be assigned to multiple names)
        if attr in seen:
            continue
        seen.add(attr)
        
        viewsets.append(attr)
    
    return viewsets


def discover_viewsets_from_apps(
    apps: List[str],
    views_suffix: str = "views",
) -> List[Type["ModelViewSet"]]:
    """
    Discover ViewSets from multiple apps.
    
    For each app in the list, tries to import `{app}.{views_suffix}` and
    discovers any ModelViewSet subclasses within.
    
    Args:
        apps: List of app module paths (e.g., ["app", "blog", "accounts"])
        views_suffix: Module name to look for within each app (default: "views")
        
    Returns:
        List of all ModelViewSet subclasses found across all apps
    """
    all_viewsets: List[Type["ModelViewSet"]] = []
    seen: Set[Type["ModelViewSet"]] = set()
    
    for app_label in apps:
        # Construct views module path
        views_module_path = f"{app_label}.{views_suffix}"
        
        # Try to import the views module
        module = import_module_safely(views_module_path)
        
        if module is None:
            logger.debug(f"No views module found for app '{app_label}'")
            continue
        
        # Discover viewsets in this module
        viewsets = discover_viewsets_from_module(module)
        
        # Add unique viewsets (avoid duplicates)
        for vs in viewsets:
            if vs not in seen:
                seen.add(vs)
                all_viewsets.append(vs)
                logger.debug(f"Discovered ViewSet: {vs.__name__} from {views_module_path}")
    
    return all_viewsets


def auto_discover_viewsets(
    views_module: Optional[str] = None,
) -> List[Type["ModelViewSet"]]:
    """
    Auto-discover ViewSets from apps configured in settings.
    
    This is the main entry point for ViewSet auto-discovery.
    
    If views_module is provided, discovers from that single module only.
    Otherwise, discovers from all apps in settings.apps.
    
    Args:
        views_module: Optional specific module path to discover from.
                     If not provided, uses settings.apps.
        
    Returns:
        List of ModelViewSet subclasses found.
        
    Example:
        # Discover from settings.apps
        viewsets = auto_discover_viewsets()
        
        # Discover from specific module
        viewsets = auto_discover_viewsets(views_module="myapp.views")
    """
    if views_module:
        # Single module discovery
        module = import_module_safely(views_module)
        if module is None:
            logger.warning(f"Could not import views module: {views_module}")
            return []
        return discover_viewsets_from_module(module)
    
    # Multi-app discovery from settings
    from aksara.conf import settings
    
    if not settings.apps:
        return []
    
    return discover_viewsets_from_apps(settings.apps)


__all__ = [
    "discover_viewsets_from_module",
    "import_module_safely",
    "discover_viewsets_from_apps",
    "auto_discover_viewsets",
]
