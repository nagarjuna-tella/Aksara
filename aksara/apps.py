"""
App & Model Auto-Discovery

Provides automatic discovery and importing of models from configured apps.

v0.3.14: Developer Delight Pack 2

Usage:
    from aksara.apps import load_app_models, get_app_models
    
    # Auto-import all models from settings.apps
    load_app_models()
    
    # Get models for a specific app
    models = get_app_models("blog")
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple, Type

if TYPE_CHECKING:
    from aksara.model.base import Model


# Track which apps have been loaded (for idempotency)
_loaded_apps: Set[str] = set()

# Per-app model cache; invalidated when the global registry version changes.
# Maps app_label -> (registry_version_at_build, list_of_models).
_app_models_cache: Dict[str, Tuple[int, List[Type["Model"]]]] = {}


def load_app_models(apps: Optional[List[str]] = None) -> None:
    """
    Import `<app>.models` for all apps to ensure models are registered.
    
    This function is called automatically when Aksara app is instantiated.
    Safe to call multiple times (idempotent).
    
    Args:
        apps: Optional list of app labels to load. If not provided,
              loads from settings.apps.
    
    Example:
        # Load all models from configured apps
        load_app_models()
        
        # Load specific apps
        load_app_models(["blog", "users"])
    """
    if apps is None:
        from aksara.conf import settings
        apps = settings.apps
    
    for app_label in apps:
        if app_label in _loaded_apps:
            continue
        
        # Try multiple common patterns
        model_modules = [
            f"{app_label}.models",  # Standard: blog.models
            f"{app_label}",         # Direct: models module itself
        ]
        
        for module_path in model_modules:
            try:
                import_module(module_path)
                _loaded_apps.add(app_label)
                break  # Successfully imported, stop trying
            except ModuleNotFoundError:
                continue
            except ImportError as e:
                # Actual import error (not just missing module)
                # This could be a syntax error or missing dependency
                import warnings
                warnings.warn(
                    f"Error importing models from '{module_path}': {e}",
                    ImportWarning,
                    stacklevel=2,
                )
                break


def get_app_models(app_label: str) -> List[Type["Model"]]:
    """
    Return all model classes registered for the given app_label.
    
    Uses the global Aksara model registry. Models must have Meta.app_label
    set to be associated with an app.
    
    Args:
        app_label: The app label to get models for (e.g., "blog")
        
    Returns:
        List of Model classes belonging to this app
        
    Example:
        from aksara.apps import get_app_models
        
        blog_models = get_app_models("blog")
        for model in blog_models:
            print(f"{model.__name__}: {model.__tablename__}")
    """
    from aksara.registry import ModelRegistry

    version = ModelRegistry._version
    cached = _app_models_cache.get(app_label)
    if cached is not None and cached[0] == version:
        # Return a shallow copy so callers can't mutate the cached list.
        return list(cached[1])

    models: List[Type["Model"]] = []
    for model in ModelRegistry.all().values():
        meta_class = getattr(model, "Meta", None)
        if meta_class:
            model_app_label = getattr(meta_class, "app_label", None)
            if model_app_label == app_label:
                models.append(model)

    _app_models_cache[app_label] = (version, models)
    return list(models)


def get_all_app_labels() -> List[str]:
    """
    Get all configured app labels.
    
    Returns:
        List of app labels from settings.apps
    """
    from aksara.conf import settings
    return list(settings.apps)


def reset_loaded_apps() -> None:
    """
    Reset the loaded apps tracker.

    Useful for testing to force re-loading of models.
    """
    global _loaded_apps, _app_models_cache
    _loaded_apps = set()
    _app_models_cache = {}


__all__ = [
    "load_app_models",
    "get_app_models",
    "get_all_app_labels",
    "reset_loaded_apps",
]
