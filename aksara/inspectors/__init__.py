"""
Aksara Inspectors

v0.5.21: Query & Model inspection tools for deep introspection.

Modules:
    models — Model schema inspector
    queries — Query plan and analysis utilities
"""

from aksara.inspectors.models import (
    ModelInspectorField,
    ModelInspectorRelationship,
    ModelInspectorConstraint,
    ModelInspectorSummary,
    inspect_model,
    inspect_all_models,
)
from aksara.inspectors.queries import (
    QueryPlanRequest,
    QueryPlanResult,
    QueryStats,
    explain_query,
    explain_query_async,
    get_query_stats,
)

__all__ = [
    # Model inspector
    "ModelInspectorField",
    "ModelInspectorRelationship",
    "ModelInspectorConstraint",
    "ModelInspectorSummary",
    "inspect_model",
    "inspect_all_models",
    # Query inspector
    "QueryPlanRequest",
    "QueryPlanResult",
    "QueryStats",
    "explain_query",
    "explain_query_async",
    "get_query_stats",
]
