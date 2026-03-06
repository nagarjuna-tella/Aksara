"""
Aksara AI Console Context Builder  (v0.5.31)

Enriches the raw context extracted by the intent router with data
from Aksara's registries (models, routes, migrations, diagnostics).

The builder NEVER executes any side-effects — it only reads metadata
from the in-memory registries and returns a plain dict suitable for
``ai_flows.execute_flow()``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("aksara.ai.console_context")


def enrich_context(
    flow_type: str,
    extracted: Dict[str, Any],
) -> Dict[str, Any]:
    """Enrich extracted context with live registry data.

    Parameters
    ----------
    flow_type : str
        One of: model, route, query, migration, diagnostic.
    extracted : dict
        Raw context from the intent router (e.g. ``{"model_name": "User"}``).

    Returns
    -------
    dict
        Enriched context ready for ``execute_flow()``.
    """
    ctx = dict(extracted)  # shallow copy

    try:
        if flow_type == "model":
            ctx = _enrich_model(ctx)
        elif flow_type == "route":
            ctx = _enrich_route(ctx)
        elif flow_type == "query":
            ctx = _enrich_query(ctx)
        elif flow_type == "migration":
            ctx = _enrich_migration(ctx)
        elif flow_type == "diagnostic":
            ctx = _enrich_diagnostic(ctx)
    except Exception as exc:
        logger.debug("Context enrichment failed for %s: %s", flow_type, exc)

    return ctx


# ─── Per-type enrichers ──────────────────────────────────────────────────────

def _enrich_model(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Try to resolve model_name from the registry."""
    model_name = ctx.get("model_name", "")
    if not model_name:
        # Pick the first registered model as a default
        model_name = _first_model_name()
        if model_name:
            ctx["model_name"] = model_name
    else:
        # Normalise to actual registered name (case-insensitive lookup)
        resolved = _resolve_model_name(model_name)
        if resolved:
            ctx["model_name"] = resolved
    return ctx


def _enrich_route(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure path + method are present; default method to GET."""
    if "method" not in ctx:
        ctx["method"] = "GET"
    if "path" not in ctx:
        ctx["path"] = ""
    return ctx


def _enrich_query(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Pass-through; sql is already extracted."""
    if "sql" not in ctx:
        ctx["sql"] = ""
    return ctx


def _enrich_migration(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Pass-through; app/name from intent router."""
    return ctx


def _enrich_diagnostic(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Pass-through; issue_id from intent router."""
    return ctx


# ─── v0.5.32: Graph context injection ────────────────────────────────────────

def inject_graph_context(
    ctx: Dict[str, Any],
    flow_type: str,
) -> Dict[str, Any]:
    """Inject project graph context into the enriched context dict.

    Called by the console engine after ``enrich_context()``.  This adds
    a ``_graph`` key with the compact graph payload.
    """
    try:
        from aksara.ai.graph_context import build_graph_console_context
        ctx["_graph"] = build_graph_console_context(flow_type=flow_type)
    except Exception:
        pass
    return ctx


# ─── Registry helpers ────────────────────────────────────────────────────────

def _first_model_name() -> str:
    """Return the first model name from the Aksara registry, or ''."""
    try:
        from aksara.registry import ModelRegistry
        names = list(ModelRegistry._models.keys())
        return names[0] if names else ""
    except Exception:
        return ""


def _resolve_model_name(name: str) -> str:
    """Case-insensitive lookup of a model name in the registry.

    Returns the canonical name if found, otherwise the original name
    unchanged (so the flow builder can report its own error).
    """
    try:
        from aksara.registry import ModelRegistry
        for registered in ModelRegistry._models:
            if registered.lower() == name.lower():
                return registered
        return name
    except Exception:
        return name
