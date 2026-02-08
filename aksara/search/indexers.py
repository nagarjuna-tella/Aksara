"""
Aksara Search — Index Builders.

v0.5.22: Build SearchDocument lists from models, routes, migrations,
queries, settings, playbooks, and agent context.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from aksara.search.engine import SearchDocument, SearchIndex

if TYPE_CHECKING:
    pass


# =============================================================================
# Lazy Import Helpers
# =============================================================================
# These helpers centralise deferred imports to avoid circular chains at
# module-load time and to give tests a single, stable patch target:
#   aksara.search.indexers._get_<name>
#
# Why lazy?  indexers.py is imported by aksara.studio.utils, which is also
# imported by several of the modules below (ModelRegistry, MigrationGraph,
# etc.).  Eager top-level imports would trigger a circular import error.
# =============================================================================


def _get_model_registry():
    """Lazy import: aksara.registry.ModelRegistry."""
    from aksara.registry import ModelRegistry
    return ModelRegistry


def _get_routes_builder():
    """Lazy import: aksara.studio.utils.build_routes_info."""
    from aksara.studio.utils import build_routes_info
    return build_routes_info


def _get_migration_graph():
    """Lazy import: aksara.migrations.graph.MigrationGraph."""
    from aksara.migrations.graph import MigrationGraph
    return MigrationGraph


def _get_query_stats():
    """Lazy import: aksara.inspectors.queries.get_query_stats."""
    from aksara.inspectors.queries import get_query_stats
    return get_query_stats


def _get_settings():
    """Lazy import: aksara.conf.settings."""
    from aksara.conf import settings
    return settings


def _get_builtin_playbooks():
    """Lazy import: aksara.ai.playbooks.get_builtin_playbooks."""
    from aksara.ai.playbooks import get_builtin_playbooks
    return get_builtin_playbooks


# =============================================================================
# Model Indexer
# =============================================================================

def build_model_documents() -> List[SearchDocument]:
    """
    Build search documents from all registered models.

    Each model produces a document with fields, relationships,
    and AI metadata.
    """
    docs: List[SearchDocument] = []
    try:
        ModelRegistry = _get_model_registry()

        for name, model_cls in ModelRegistry.all().items():
            fields_info: List[str] = []
            field_names: List[str] = []
            for fname, fobj in getattr(model_cls, "_fields", {}).items():
                ftype = getattr(fobj, "field_type", type(fobj).__name__)
                fields_info.append(f"{fname}: {ftype}")
                field_names.append(fname)

            table_name = getattr(model_cls, "__tablename__", None) or getattr(model_cls, "_table_name", name.lower())
            ai_desc = getattr(model_cls, "_ai_description", "")

            relations: List[str] = []
            for fname, fobj in getattr(model_cls, "_fields", {}).items():
                if getattr(fobj, "is_relation", False):
                    target = getattr(fobj, "related_model_name", "?")
                    relations.append(f"{fname} -> {target}")

            content_parts = [
                f"Model: {name}",
                f"Table: {table_name}",
                f"Fields: {', '.join(field_names)}" if field_names else "No fields",
            ]
            if relations:
                content_parts.append(f"Relations: {', '.join(relations)}")
            if ai_desc:
                content_parts.append(f"AI Description: {ai_desc}")

            summary = f"{name} model ({table_name}) with {len(field_names)} fields"
            if relations:
                summary += f" and {len(relations)} relations"

            docs.append(SearchDocument(
                kind="model",
                title=name,
                summary=summary,
                content="\n".join(content_parts),
                metadata={
                    "table_name": table_name,
                    "field_count": len(field_names),
                    "relation_count": len(relations),
                    "fields": field_names,
                },
                tags=["model", table_name] + field_names[:5],
                source=f"model:{name}",
            ))
    except Exception:
        pass

    return docs


# =============================================================================
# Route Indexer
# =============================================================================

def build_route_documents(app: Optional[Any] = None) -> List[SearchDocument]:
    """
    Build search documents from application routes.

    If app is provided, extracts routes from the FastAPI app.
    Otherwise returns an empty list.
    """
    docs: List[SearchDocument] = []
    if app is None:
        return docs

    try:
        build_routes_info = _get_routes_builder()

        routes = build_routes_info(app)
        for route_info in routes:
            if hasattr(route_info, "model_dump"):
                rd = route_info.model_dump()
            elif isinstance(route_info, dict):
                rd = route_info
            else:
                continue

            path = rd.get("path", "")
            methods = rd.get("methods", [])
            name = rd.get("name", "")
            tags = rd.get("tags", [])

            method_str = ", ".join(methods) if isinstance(methods, list) else str(methods)
            content = f"Route: {method_str} {path}\nName: {name}"
            if tags:
                content += f"\nTags: {', '.join(tags)}"

            docs.append(SearchDocument(
                kind="route",
                title=f"{method_str} {path}",
                summary=f"API endpoint {path} ({method_str})",
                content=content,
                metadata=rd,
                tags=["route"] + (tags if isinstance(tags, list) else []),
                source=f"route:{path}",
            ))
    except Exception:
        pass

    return docs


# =============================================================================
# Migration Indexer
# =============================================================================

def build_migration_documents() -> List[SearchDocument]:
    """
    Build search documents from migration metadata.

    Indexes migration files with status and app information.
    """
    docs: List[SearchDocument] = []
    try:
        MigrationGraph = _get_migration_graph()

        graph = MigrationGraph()
        graph.discover()

        for node in graph.nodes:
            app = getattr(node, "app_label", "default")
            name = getattr(node, "name", str(node))
            deps = getattr(node, "dependencies", [])

            content_parts = [
                f"Migration: {name}",
                f"App: {app}",
            ]
            if deps:
                content_parts.append(f"Dependencies: {', '.join(str(d) for d in deps)}")

            docs.append(SearchDocument(
                kind="migration",
                title=name,
                summary=f"Migration {name} for app {app}",
                content="\n".join(content_parts),
                metadata={"app_label": app, "dependencies": [str(d) for d in deps]},
                tags=["migration", app],
                source=f"migration:{app}:{name}",
            ))
    except Exception:
        pass

    return docs


# =============================================================================
# Query Indexer
# =============================================================================

def build_query_documents() -> List[SearchDocument]:
    """
    Build search documents from recent query statistics.
    """
    docs: List[SearchDocument] = []
    try:
        get_query_stats = _get_query_stats()

        stats = get_query_stats(limit_slow=20)
        if hasattr(stats, "slow_queries"):
            for sq in stats.slow_queries:
                sq_dict = sq.model_dump() if hasattr(sq, "model_dump") else sq
                sql = sq_dict.get("sql", "")
                table = sq_dict.get("table", "unknown")
                duration = sq_dict.get("duration_ms", 0)
                operation = sq_dict.get("operation", "SELECT")

                docs.append(SearchDocument(
                    kind="query",
                    title=f"{operation} on {table} ({duration:.1f}ms)",
                    summary=f"Slow query: {operation} on {table}, {duration:.1f}ms",
                    content=sql[:500] if sql else "",
                    metadata=sq_dict,
                    tags=["query", "slow", table, operation.lower()],
                    source=f"query:{table}:{operation}",
                ))
    except Exception:
        pass

    return docs


# =============================================================================
# Settings Indexer
# =============================================================================

def build_settings_documents() -> List[SearchDocument]:
    """
    Build search documents from current settings.
    """
    docs: List[SearchDocument] = []
    try:
        settings = _get_settings()
        from dataclasses import fields as dc_fields

        for f in dc_fields(settings):
            if f.name.startswith("_"):
                continue
            value = getattr(settings, f.name, None)
            value_repr = repr(value) if value is not None else "None"

            # Look for env var override
            env_key = f"AKSARA_{f.name.upper()}"

            docs.append(SearchDocument(
                kind="setting",
                title=f.name,
                summary=f"Setting: {f.name} = {value_repr[:60]}",
                content=f"Setting: {f.name}\nValue: {value_repr}\nType: {f.type}\nEnv: {env_key}",
                metadata={"name": f.name, "type": str(f.type), "env_key": env_key},
                tags=["setting", f.name],
                source=f"setting:{f.name}",
            ))
    except Exception:
        pass

    return docs


# =============================================================================
# Playbook Indexer
# =============================================================================

def build_playbook_documents() -> List[SearchDocument]:
    """
    Build search documents from built-in agent playbooks.
    """
    docs: List[SearchDocument] = []
    try:
        get_builtin_playbooks = _get_builtin_playbooks()

        pset = get_builtin_playbooks()
        for pb in pset.playbooks:
            steps_text = "\n".join(
                f"  {i+1}. {s.title}: {s.description}"
                for i, s in enumerate(pb.steps)
            )
            content = (
                f"Playbook: {pb.label}\n"
                f"Kind: {pb.kind}\n"
                f"Category: {pb.category}\n"
                f"Risk: {pb.risk_level}\n"
                f"Description: {pb.description}\n"
                f"Steps:\n{steps_text}"
            )

            docs.append(SearchDocument(
                kind="playbook",
                title=pb.label,
                summary=pb.description[:120],
                content=content,
                metadata={
                    "key": pb.key,
                    "kind": pb.kind,
                    "category": pb.category,
                    "risk_level": pb.risk_level,
                    "step_count": len(pb.steps),
                },
                tags=["playbook", pb.category, pb.risk_level] + (pb.tags or []),
                source=f"playbook:{pb.key}",
            ))
    except Exception:
        pass

    return docs


# =============================================================================
# Full Index Builder
# =============================================================================

def build_full_index(
    app: Optional[Any] = None,
    *,
    include_models: bool = True,
    include_routes: bool = True,
    include_migrations: bool = True,
    include_queries: bool = True,
    include_settings: bool = True,
    include_playbooks: bool = True,
) -> SearchIndex:
    """
    Build a complete search index from all available sources.

    Args:
        app: Optional FastAPI app instance (needed for routes).
        include_models: Index registered models.
        include_routes: Index API routes.
        include_migrations: Index migration metadata.
        include_queries: Index recent query statistics.
        include_settings: Index current settings.
        include_playbooks: Index agent playbooks.

    Returns:
        A populated SearchIndex instance.
    """
    index = SearchIndex()

    if include_models:
        index.add_many(build_model_documents())

    if include_routes:
        index.add_many(build_route_documents(app))

    if include_migrations:
        index.add_many(build_migration_documents())

    if include_queries:
        index.add_many(build_query_documents())

    if include_settings:
        index.add_many(build_settings_documents())

    if include_playbooks:
        index.add_many(build_playbook_documents())

    return index
