"""
Aksara AI Connector Registry  (v0.5.30)

Maps provider names to connector classes and provides ``get_connector()``
for resolving a configured connector instance from AI Hub settings.

Usage::

    from aksara.ai.connectors.registry import get_connector

    connector = get_connector("openai")        # uses AI Hub config
    connector = get_connector("ollama")         # local Ollama
    connector = get_connector("openai", api_key="sk-...")  # explicit creds
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type

from aksara.ai.connectors.base import AIConnector

logger = logging.getLogger("aksara.ai.connectors.registry")

# ---------------------------------------------------------------------------
# Registry mapping
# ---------------------------------------------------------------------------

_CONNECTOR_CLASSES: Dict[str, Type[AIConnector]] = {}


def _ensure_registry() -> None:
    """Lazily populate the registry to avoid heavy imports at module load."""
    if _CONNECTOR_CLASSES:
        return
    from aksara.ai.connectors.openai import OpenAIConnector
    from aksara.ai.connectors.anthropic import AnthropicConnector
    from aksara.ai.connectors.ollama import OllamaConnector
    from aksara.ai.connectors.http import HttpConnector

    _CONNECTOR_CLASSES.update({
        "openai": OpenAIConnector,
        "azure": OpenAIConnector,       # Azure uses the same API shape
        "anthropic": AnthropicConnector,
        "ollama": OllamaConnector,
        "http": HttpConnector,
        "custom": HttpConnector,         # alias
    })


# Public read-only view
def _get_registry() -> Dict[str, Type[AIConnector]]:
    _ensure_registry()
    return dict(_CONNECTOR_CLASSES)


# Backward-compat name used in __init__
CONNECTOR_REGISTRY = property(lambda self: _get_registry())  # type: ignore[assignment]


def list_connectors() -> Dict[str, str]:
    """Return ``{provider: class_name}`` for all registered connectors."""
    _ensure_registry()
    return {k: v.__name__ for k, v in _CONNECTOR_CLASSES.items()}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_connector(
    provider: str,
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    hub_settings: Optional[Any] = None,
    **kwargs: Any,
) -> AIConnector:
    """Resolve and instantiate a connector for *provider*.

    Resolution order for credentials:
    1. Explicit ``api_key`` / ``base_url`` kwargs
    2. AI Hub settings (if passed or loadable)
    3. Environment variables (handled inside each connector)

    Returns a concrete ``AIConnector`` subclass instance.
    Raises ``ValueError`` if *provider* is unknown.
    """
    _ensure_registry()

    cls = _CONNECTOR_CLASSES.get(provider)
    if cls is None:
        raise ValueError(
            f"Unknown AI connector provider: '{provider}'. "
            f"Available: {', '.join(sorted(_CONNECTOR_CLASSES.keys()))}"
        )

    # Try to extract creds from AI Hub settings
    init_kwargs: Dict[str, Any] = {**kwargs}

    if hub_settings is not None:
        _merge_hub_config(hub_settings, provider, init_kwargs)
    else:
        try:
            from aksara.ai.hub_settings import load_aihub_settings
            hub = load_aihub_settings()
            _merge_hub_config(hub, provider, init_kwargs)
        except Exception:
            pass  # Fall through to env vars

    # Override with explicit args
    if api_key:
        init_kwargs["api_key"] = api_key
    if base_url:
        init_kwargs["base_url"] = base_url

    return cls(**init_kwargs)


def _merge_hub_config(hub: Any, provider: str, kwargs: Dict[str, Any]) -> None:
    """Extract provider config from AiHubSettings into *kwargs*."""
    pcfg = hub.get_provider(provider) if hasattr(hub, "get_provider") else None
    if pcfg is None:
        return

    cfg = pcfg.active_config
    if cfg is None:
        return

    # Map known config fields
    ak = getattr(cfg, "api_key", None)
    if ak and "api_key" not in kwargs:
        kwargs["api_key"] = ak

    bu = getattr(cfg, "base_url", None)
    if bu and "base_url" not in kwargs:
        kwargs["base_url"] = bu

    # Ollama uses base_url, HTTP uses endpoint
    if provider in ("http", "custom"):
        if bu and "endpoint" not in kwargs:
            kwargs["endpoint"] = bu

    # Azure extras
    if provider == "azure":
        org = getattr(cfg, "deployment", None)
        if org and "organization" not in kwargs:
            kwargs["organization"] = org

    # Custom headers
    hdrs = getattr(cfg, "headers", None)
    if hdrs and "headers" not in kwargs:
        kwargs["headers"] = hdrs


# Convenience alias for the dict form
CONNECTOR_REGISTRY: Dict[str, Type[AIConnector]] = {}  # type: ignore[assignment]


def _refresh_registry() -> Dict[str, Type[AIConnector]]:
    """Return a fresh copy of the registry dict."""
    _ensure_registry()
    return dict(_CONNECTOR_CLASSES)


# Populate on first real access (backward compat with ``from ... import CONNECTOR_REGISTRY``)
def __getattr__(name: str) -> Any:
    if name == "CONNECTOR_REGISTRY":
        return _refresh_registry()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
