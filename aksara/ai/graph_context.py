"""
Aksara AI Graph Context  (v0.5.32)

Transforms the Project Context Graph into AI-friendly payloads of
different shapes/sizes so we can inject the right amount of context
into Console prompts, debug sessions, or summary cards.

Usage::

    from aksara.ai.graph_context import (
        build_graph_console_context,
        build_graph_debug_context,
        build_graph_summary_context,
    )

    summary = build_graph_summary_context()
    console = build_graph_console_context(flow_type="model")
    debug   = build_graph_debug_context()
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_graph_summary_context() -> Dict[str, Any]:
    """Compact overview for UI summary cards and CLI."""
    from aksara.ai.project_graph import build_project_graph

    graph = build_project_graph()
    return graph.to_summary_dict()


def build_graph_console_context(
    *,
    flow_type: Optional[str] = None,
    include_events: bool = True,
    max_events: int = 10,
) -> Dict[str, Any]:
    """Context payload for AI Console prompts.

    Includes key node lists + recent events.  If *flow_type* is given,
    the relevant nodes are emphasised (e.g. models for model flows).
    """
    from aksara.ai.project_graph import build_project_graph

    graph = build_project_graph()

    ctx: Dict[str, Any] = {
        "graph_text": graph.to_console_context(),
        "model_names": [m.name for m in graph.models],
        "route_paths": [f"{r.method} {r.path}" for r in graph.routes[:30]],
        "diagnostic_count": graph.metadata.diagnostic_count,
        "gap_count": graph.metadata.gap_count,
    }

    # Emphasise relevant nodes
    if flow_type == "model" and graph.models:
        ctx["models_detail"] = [
            {"name": m.name, "table": m.table, "fields": m.fields[:15],
             "relations": m.relations}
            for m in graph.models[:10]
        ]
    elif flow_type == "route" and graph.routes:
        ctx["routes_detail"] = [
            {"method": r.method, "path": r.path, "name": r.name,
             "models": r.models}
            for r in graph.routes[:15]
        ]
    elif flow_type == "query" and graph.queries:
        ctx["queries_detail"] = [
            {"name": q.name, "sql": q.sql[:200], "models": q.models}
            for q in graph.queries[:10]
        ]
    elif flow_type == "diagnostic" and graph.diagnostics:
        ctx["diagnostics_detail"] = [
            {"code": d.code, "severity": d.severity, "message": d.message}
            for d in graph.diagnostics[:15]
        ]
    elif flow_type == "migration" and graph.migrations:
        ctx["migrations_detail"] = [
            {"name": m.name, "app": m.app, "models": m.models}
            for m in graph.migrations[:15]
        ]

    # Recent events
    if include_events and graph.events:
        ctx["recent_events"] = graph.events[-max_events:]

    return ctx


def build_graph_debug_context() -> Dict[str, Any]:
    """Focused payload for debug / diagnostic sessions.

    Emphasises diagnostics, queries, routes, and migrations.
    """
    from aksara.ai.project_graph import build_project_graph

    graph = build_project_graph()

    return {
        "diagnostics": [
            {"code": d.code, "severity": d.severity, "message": d.message,
             "related_models": d.related_models, "related_routes": d.related_routes,
             "related_queries": d.related_queries}
            for d in graph.diagnostics
        ],
        "gaps": [
            {"code": g.code, "severity": g.severity, "summary": g.summary,
             "category": g.category}
            for g in graph.gaps
        ],
        "queries": [
            {"name": q.name, "sql": q.sql[:300], "models": q.models,
             "diagnostics": q.diagnostics}
            for q in graph.queries[:20]
        ],
        "routes_with_diagnostics": [
            {"method": r.method, "path": r.path, "models": r.models,
             "diagnostics": r.diagnostics}
            for r in graph.routes if r.diagnostics
        ],
        "recent_events": graph.events[-20:],
        "model_count": graph.metadata.model_count,
        "ai_hub_status": graph.ai_hub.status if graph.ai_hub else "unknown",
    }


def build_graph_prompt_section(
    *,
    flow_type: Optional[str] = None,
    max_events: int = 5,
) -> str:
    """Return a formatted text block for injection into LLM prompts.

    Compact, bounded, and safe for inclusion in system/user prompts.
    """
    from aksara.ai.project_graph import build_project_graph

    graph = build_project_graph()
    lines: List[str] = []

    lines.append("PROJECT GRAPH SUMMARY:")
    lines.append(f"  Models: {graph.metadata.model_count}")
    lines.append(f"  Routes: {graph.metadata.route_count}")
    lines.append(f"  Queries: {graph.metadata.query_count}")
    lines.append(f"  Migrations: {graph.metadata.migration_count}")
    lines.append(f"  Diagnostics: {graph.metadata.diagnostic_count}")
    lines.append(f"  Gaps: {graph.metadata.gap_count}")

    if graph.models:
        names = ", ".join(m.name for m in graph.models[:15])
        lines.append(f"\nMODELS: {names}")

    # Flow-type specific nodes
    if flow_type == "model" and graph.models:
        lines.append("\nRELEVANT MODEL DETAIL:")
        for m in graph.models[:5]:
            rels = f" (relations: {', '.join(m.relations)})" if m.relations else ""
            lines.append(f"  {m.name} [{m.table}]: {len(m.fields)} fields{rels}")
    elif flow_type == "route" and graph.routes:
        lines.append("\nRELEVANT ROUTES:")
        for r in graph.routes[:10]:
            models_str = f" → {', '.join(r.models)}" if r.models else ""
            lines.append(f"  {r.method} {r.path}{models_str}")
    elif flow_type == "diagnostic" and graph.diagnostics:
        lines.append("\nDIAGNOSTIC ISSUES:")
        for d in graph.diagnostics[:10]:
            lines.append(f"  [{d.severity}] {d.code}: {d.message}")

    # Recent events
    if graph.events:
        lines.append("\nRECENT EVENTS:")
        for ev in graph.events[-max_events:]:
            sev = ev.get("severity", "info")
            kind = ev.get("kind", "?")
            msg = ev.get("message", "")[:80]
            lines.append(f"  [{sev}] {kind}: {msg}")

    return "\n".join(lines)
