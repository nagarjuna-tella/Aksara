"""
Aksara AI Project Graph  (v0.5.32)

Structured representation of the application as nodes and relationships
so AI can reason about: application structure, dependencies, related
failures, likely causes, recent changes, and issue prioritisation.

Usage::

    from aksara.ai.project_graph import build_project_graph

    graph = build_project_graph()          # cached for 5 s
    graph = build_project_graph(rebuild=True)  # force rebuild
    d     = graph.to_dict()
    s     = graph.to_summary_dict()
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aksara.ai.project_graph")

# ─── Node Data Models ────────────────────────────────────────────────────────


@dataclass
class ModelNode:
    name: str
    table: str
    fields: List[str] = field(default_factory=list)
    indexes: List[str] = field(default_factory=list)
    relations: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class RouteNode:
    method: str
    path: str
    name: str
    handler: str
    models: List[str] = field(default_factory=list)
    queries: List[str] = field(default_factory=list)
    diagnostics: List[str] = field(default_factory=list)


@dataclass
class QueryNode:
    name: str
    sql: str
    models: List[str] = field(default_factory=list)
    indexes_used: List[str] = field(default_factory=list)
    diagnostics: List[str] = field(default_factory=list)


@dataclass
class MigrationNode:
    name: str
    app: str
    operations: List[str] = field(default_factory=list)
    models: List[str] = field(default_factory=list)


@dataclass
class DiagnosticNode:
    code: str
    severity: str
    message: str
    related_models: List[str] = field(default_factory=list)
    related_routes: List[str] = field(default_factory=list)
    related_queries: List[str] = field(default_factory=list)


@dataclass
class GapNode:
    code: str
    severity: str
    summary: str
    category: str
    related_components: List[str] = field(default_factory=list)


@dataclass
class AiHubNode:
    providers: List[str] = field(default_factory=list)
    default_chat_model: Optional[str] = None
    default_code_model: Optional[str] = None
    default_embeddings_model: Optional[str] = None
    status: str = "unknown"


@dataclass
class AiFlowNode:
    action_key: str
    title: str
    flow_type: str
    risk: str


@dataclass
class GraphMetadata:
    version: str = ""
    generated_at: str = ""
    cache_ttl_seconds: int = 5
    model_count: int = 0
    route_count: int = 0
    query_count: int = 0
    migration_count: int = 0
    diagnostic_count: int = 0
    gap_count: int = 0
    event_count: int = 0


# ─── Project Graph ───────────────────────────────────────────────────────────


@dataclass
class ProjectGraph:
    models: List[ModelNode] = field(default_factory=list)
    routes: List[RouteNode] = field(default_factory=list)
    queries: List[QueryNode] = field(default_factory=list)
    migrations: List[MigrationNode] = field(default_factory=list)
    diagnostics: List[DiagnosticNode] = field(default_factory=list)
    gaps: List[GapNode] = field(default_factory=list)
    ai_hub: Optional[AiHubNode] = None
    flows: List[AiFlowNode] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    metadata: GraphMetadata = field(default_factory=GraphMetadata)

    def to_dict(self) -> Dict[str, Any]:
        """Full JSON-serialisable dict of the entire graph."""
        return asdict(self)

    def to_summary_dict(self) -> Dict[str, Any]:
        """Compact summary suitable for UI cards and CLI."""
        m = self.metadata
        return {
            "version": m.version,
            "generated_at": m.generated_at,
            "counts": {
                "models": m.model_count,
                "routes": m.route_count,
                "queries": m.query_count,
                "migrations": m.migration_count,
                "diagnostics": m.diagnostic_count,
                "gaps": m.gap_count,
                "events": m.event_count,
            },
            "ai_hub_status": self.ai_hub.status if self.ai_hub else "not_configured",
            "flow_count": len(self.flows),
        }

    def to_console_context(self) -> str:
        """Compact text for injection into AI Console prompts."""
        lines: List[str] = []
        lines.append("PROJECT GRAPH SUMMARY")
        lines.append(f"  Models: {self.metadata.model_count}")
        lines.append(f"  Routes: {self.metadata.route_count}")
        lines.append(f"  Queries: {self.metadata.query_count}")
        lines.append(f"  Migrations: {self.metadata.migration_count}")
        lines.append(f"  Diagnostics: {self.metadata.diagnostic_count}")
        lines.append(f"  Gaps: {self.metadata.gap_count}")
        lines.append(f"  Events: {self.metadata.event_count}")
        hub = self.ai_hub
        if hub:
            lines.append(f"  AI Hub: {hub.status} ({len(hub.providers)} providers)")

        # Model names
        if self.models:
            names = ", ".join(m.name for m in self.models[:20])
            lines.append(f"\nMODELS: {names}")

        # Recent events (last 5)
        if self.events:
            lines.append("\nRECENT EVENTS:")
            for ev in self.events[-5:]:
                sev = ev.get("severity", "info")
                kind = ev.get("kind", "?")
                msg = ev.get("message", "")
                lines.append(f"  [{sev}] {kind}: {msg}")

        return "\n".join(lines)


# ─── Graph Cache ─────────────────────────────────────────────────────────────

_CACHE_TTL = 5  # seconds
_cache_lock = threading.Lock()
_cached_graph: Optional[ProjectGraph] = None
_cached_at: float = 0.0


def _invalidate_cache() -> None:
    global _cached_graph, _cached_at
    with _cache_lock:
        _cached_graph = None
        _cached_at = 0.0


# ─── Graph Builder ───────────────────────────────────────────────────────────


def build_project_graph(rebuild: bool = False, *, app: Any = None) -> ProjectGraph:
    """Build (or return cached) project context graph.

    Parameters
    ----------
    rebuild : bool
        If True, bypass cache and force a fresh build.
    app : optional
        FastAPI application instance (used for route discovery).
    """
    global _cached_graph, _cached_at

    if not rebuild:
        with _cache_lock:
            if _cached_graph is not None and (time.monotonic() - _cached_at) < _CACHE_TTL:
                return _cached_graph

    graph = _build_graph(app=app)

    with _cache_lock:
        _cached_graph = graph
        _cached_at = time.monotonic()

    return graph


def _build_graph(*, app: Any = None) -> ProjectGraph:
    """Internal: gather data from all subsystems and assemble the graph."""
    import aksara

    graph = ProjectGraph()
    graph.metadata.version = aksara.__version__
    graph.metadata.generated_at = datetime.now(timezone.utc).isoformat()
    graph.metadata.cache_ttl_seconds = _CACHE_TTL

    # 1 — Models
    graph.models = _collect_models()
    graph.metadata.model_count = len(graph.models)

    # 2 — Routes
    graph.routes = _collect_routes(app=app)
    graph.metadata.route_count = len(graph.routes)

    # 3 — Queries (best-effort from DB tracing)
    graph.queries = _collect_queries()
    graph.metadata.query_count = len(graph.queries)

    # 4 — Migrations
    graph.migrations = _collect_migrations()
    graph.metadata.migration_count = len(graph.migrations)

    # 5 — Diagnostics (last cached report)
    graph.diagnostics = _collect_diagnostics()
    graph.metadata.diagnostic_count = len(graph.diagnostics)

    # 6 — Gaps
    graph.gaps = _collect_gaps()
    graph.metadata.gap_count = len(graph.gaps)

    # 7 — AI Hub
    graph.ai_hub = _collect_ai_hub()

    # 8 — Flows
    graph.flows = _collect_flows()

    # 9 — Events
    graph.events = _collect_events()
    graph.metadata.event_count = len(graph.events)

    return graph


# ─── Collector helpers ───────────────────────────────────────────────────────


def _collect_models() -> List[ModelNode]:
    """Gather models from the Aksara registry."""
    nodes: List[ModelNode] = []
    try:
        from aksara.registry import ModelRegistry

        for name, model_cls in ModelRegistry.all().items():
            table = getattr(model_cls, "__tablename__", name.lower())
            # Fields
            field_names: List[str] = []
            relations: List[str] = []
            for fname, fobj in getattr(model_cls, "_fields", {}).items():
                field_names.append(fname)
                # Detect FK relations
                ftype = type(fobj).__name__
                if ftype == "ForeignKey":
                    target = getattr(fobj, "_to", "")
                    if not isinstance(target, str):
                        target = getattr(target, "__name__", str(target))
                    relations.append(f"{fname} → {target}")

            # Indexes (from constraints / meta)
            indexes = _extract_indexes(model_cls)

            nodes.append(ModelNode(
                name=name,
                table=table,
                fields=field_names,
                indexes=indexes,
                relations=relations,
            ))
    except Exception as exc:
        logger.debug("_collect_models failed: %s", exc)
    return nodes


def _extract_indexes(model_cls: Any) -> List[str]:
    """Best-effort index extraction from model meta / _fields."""
    indexes: List[str] = []
    try:
        from aksara.inspectors.models import inspect_model
        summary = inspect_model(model_cls)
        for c in summary.constraints:
            if c.kind in ("index", "unique"):
                indexes.append(f"{c.kind}({', '.join(c.columns)})")
    except Exception:
        pass
    return indexes


def _collect_routes(*, app: Any = None) -> List[RouteNode]:
    """Gather routes from the Studio utility."""
    nodes: List[RouteNode] = []
    if app is None:
        return nodes
    try:
        from aksara.studio.utils import build_routes_info

        routes = build_routes_info(app)
        # Build a set of known model names for heuristic linking
        model_names = _known_model_names()

        for r in routes:
            path = getattr(r, "path", "")
            methods = getattr(r, "methods", ["GET"])
            name = getattr(r, "name", "") or ""
            handler = getattr(r, "handler", "") or name

            for method in methods:
                inferred_models = _infer_models_from_route(path, handler, model_names)
                nodes.append(RouteNode(
                    method=method,
                    path=path,
                    name=name,
                    handler=handler,
                    models=inferred_models,
                ))
    except Exception as exc:
        logger.debug("_collect_routes failed: %s", exc)
    return nodes


def _collect_queries() -> List[QueryNode]:
    """Gather recent queries from DB tracing if available."""
    nodes: List[QueryNode] = []
    try:
        from aksara.db.tracing import get_recent_queries
        model_names = _known_model_names()
        table_to_model = _table_to_model_map()

        for i, q in enumerate(get_recent_queries(limit=50)):
            sql = getattr(q, "sql", "") or (q if isinstance(q, str) else "")
            if isinstance(q, dict):
                sql = q.get("sql", "")
            label = f"query_{i}"
            related = _infer_models_from_sql(sql, table_to_model)
            nodes.append(QueryNode(
                name=label,
                sql=sql[:500],
                models=related,
            ))
    except Exception:
        pass
    return nodes


def _collect_migrations() -> List[MigrationNode]:
    """Gather migrations from the migration discovery system."""
    nodes: List[MigrationNode] = []
    try:
        from aksara.conf import settings
        from pathlib import Path as _Path
        from aksara.migrations import discover_all_migrations
        from aksara.migrations.executor import extract_app_label_from_name

        mig_dir = _Path(settings.migrations_dir)
        all_migs = discover_all_migrations(mig_dir, include_internal=True)
        model_names = _known_model_names()

        for mig_name, file_path in all_migs:
            app_label = extract_app_label_from_name(mig_name, file_path)
            # Infer touched models from migration name
            touched = _infer_models_from_migration_name(mig_name, model_names)
            nodes.append(MigrationNode(
                name=mig_name,
                app=app_label,
                operations=[],
                models=touched,
            ))
    except Exception as exc:
        logger.debug("_collect_migrations failed: %s", exc)
    return nodes


def _collect_diagnostics() -> List[DiagnosticNode]:
    """Return diagnostics from the last cached report, if any."""
    nodes: List[DiagnosticNode] = []
    try:
        from aksara.diagnostics import DiagnosticReport
        # We look for a cached report; running diagnostics is async and
        # potentially slow, so we only use what's already available.
        # The Studio endpoints / CLI doctor commands populate this.
        report = getattr(DiagnosticReport, "_last_report", None)
        if report is not None:
            for issue in getattr(report, "issues", []):
                nodes.append(DiagnosticNode(
                    code=getattr(issue, "kind", "general"),
                    severity=getattr(issue, "severity", "info"),
                    message=getattr(issue, "title", "") or getattr(issue, "message", ""),
                    related_models=[],
                    related_routes=[],
                    related_queries=[],
                ))
    except Exception as exc:
        logger.debug("_collect_diagnostics failed: %s", exc)
    return nodes


def _collect_gaps() -> List[GapNode]:
    """Gather gap analysis results if available."""
    nodes: List[GapNode] = []
    try:
        # The gap analysis module may cache a last report after running
        from aksara import gapanalysis
        report = getattr(gapanalysis, "_last_report", None)
        if report is not None:
            for gap in getattr(report, "issues", []):
                nodes.append(GapNode(
                    code=getattr(gap, "code", ""),
                    severity=getattr(gap, "severity", "info"),
                    summary=getattr(gap, "title", "") or getattr(gap, "message", ""),
                    category=getattr(gap, "category", "general"),
                    related_components=getattr(gap, "related_components", []),
                ))
    except Exception:
        pass
    return nodes


def _collect_ai_hub() -> Optional[AiHubNode]:
    """Read AI Hub settings summary."""
    try:
        from aksara.ai.hub_settings import load_aihub_settings
        hub = load_aihub_settings()
        configured = hub.configured_providers()
        return AiHubNode(
            providers=[p.kind for p in hub.providers],
            default_chat_model=hub.defaults.chat_model,
            default_code_model=hub.defaults.code_model,
            default_embeddings_model=hub.defaults.embeddings_model,
            status="ready" if configured else "not_configured",
        )
    except Exception:
        return AiHubNode(status="unavailable")


def _collect_flows() -> List[AiFlowNode]:
    """Expose the AI flow action registry as graph nodes."""
    nodes: List[AiFlowNode] = []
    try:
        from aksara.studio.ai_flows import AI_FLOW_ACTIONS
        for key, meta in AI_FLOW_ACTIONS.items():
            nodes.append(AiFlowNode(
                action_key=key,
                title=meta.get("title", key),
                flow_type=meta.get("kind", ""),
                risk=meta.get("risk", "low"),
            ))
    except Exception:
        pass
    return nodes


def _collect_events() -> List[Dict[str, Any]]:
    """Attach recent events from the graph event store."""
    try:
        from aksara.ai.graph_events import get_recent_graph_events
        return [e.to_dict() for e in get_recent_graph_events(limit=200)]
    except Exception:
        return []


# ─── Relationship Heuristics ─────────────────────────────────────────────────


def _known_model_names() -> List[str]:
    """Return list of all registered model names."""
    try:
        from aksara.registry import ModelRegistry
        return list(ModelRegistry.all().keys())
    except Exception:
        return []


def _table_to_model_map() -> Dict[str, str]:
    """Build table_name → model_name mapping."""
    mapping: Dict[str, str] = {}
    try:
        from aksara.registry import ModelRegistry
        for name, cls in ModelRegistry.all().items():
            table = getattr(cls, "__tablename__", name.lower())
            mapping[table] = name
    except Exception:
        pass
    return mapping


_SEGMENT_RE = re.compile(r"/(\w+)")


def _infer_models_from_route(
    path: str, handler: str, model_names: List[str],
) -> List[str]:
    """Best-effort model inference from route path/handler.

    Heuristics:
    - path segments matched against model names (singular/plural)
    - handler name matched against model names
    """
    found: List[str] = []
    lower_names = {n.lower(): n for n in model_names}

    # Check path segments
    segments = _SEGMENT_RE.findall(path.lower())
    for seg in segments:
        # Direct match
        if seg in lower_names:
            found.append(lower_names[seg])
            continue
        # Singular form (remove trailing 's')
        if seg.endswith("s") and seg[:-1] in lower_names:
            found.append(lower_names[seg[:-1]])

    # Check handler name
    handler_lower = handler.lower()
    for lname, canonical in lower_names.items():
        if lname in handler_lower and canonical not in found:
            found.append(canonical)

    return found


def _infer_models_from_sql(sql: str, table_to_model: Dict[str, str]) -> List[str]:
    """Infer model names from SQL by matching table names."""
    found: List[str] = []
    sql_lower = sql.lower()
    for table, model in table_to_model.items():
        if table.lower() in sql_lower and model not in found:
            found.append(model)
    return found


def _infer_models_from_migration_name(
    mig_name: str, model_names: List[str],
) -> List[str]:
    """Infer model names from migration file name."""
    found: List[str] = []
    name_lower = mig_name.lower()
    for m in model_names:
        if m.lower() in name_lower and m not in found:
            found.append(m)
    return found
