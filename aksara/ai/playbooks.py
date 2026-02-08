"""
Aksara Agent Playbooks Registry

v0.5.20: Built-in playbooks — opinionated, reusable recipes for common
LLM-assisted development tasks.

Each playbook defines:
- A unique key and human-readable label
- A kind (from AgentPlaybookKind)
- Default goal template with {placeholders}
- Risk level and usage kind
- Ordered steps with recommended context sections
- Tags for search and filtering
"""

from __future__ import annotations

from typing import Dict, List, Optional

from aksara.studio.models import (
    AgentPlaybook,
    AgentPlaybookSet,
    AgentPlaybookStep,
)


# =============================================================================
# Built-in Playbook Definitions
# =============================================================================

_BUILTIN_PLAYBOOKS: List[AgentPlaybook] = [
    # -------------------------------------------------------------------------
    # 1. Add a Field to a Model
    # -------------------------------------------------------------------------
    AgentPlaybook(
        key="add_field_to_model",
        label="Add Field to Model",
        kind="add_field",
        description=(
            "Walk through adding a new field to an existing model — "
            "from schema change through migration and serializer update."
        ),
        category="schema",
        default_goal_template=(
            "Add a {field_type} field named '{field_name}' to the {model_name} model."
        ),
        risk_level="medium",
        usage_kind="write",
        default_sections=["models", "migrations", "schema_checksum"],
        steps=[
            AgentPlaybookStep(
                id="define_field",
                title="Define the field",
                description="Add the field to the model class with proper type and constraints.",
                recommended_sections=["models"],
                estimated_impact="schema change",
            ),
            AgentPlaybookStep(
                id="generate_migration",
                title="Generate migration",
                description="Create an Aksara migration to apply the schema change.",
                recommended_sections=["migrations"],
                estimated_impact="database migration",
            ),
            AgentPlaybookStep(
                id="update_serializer",
                title="Update serializer",
                description="Add the new field to the corresponding API serializer.",
                recommended_sections=["routes", "models"],
                estimated_impact="API response change",
            ),
            AgentPlaybookStep(
                id="verify",
                title="Verify",
                description="Run the migration and check the API response includes the new field.",
                recommended_sections=["diagnostics"],
                estimated_impact="low risk",
            ),
        ],
        tags=["field", "model", "schema", "migration", "serializer"],
        notes="Always generate a migration after adding the field.",
    ),

    # -------------------------------------------------------------------------
    # 2. Add an API Action to a ViewSet
    # -------------------------------------------------------------------------
    AgentPlaybook(
        key="add_api_action_to_viewset",
        label="Add API Action",
        kind="add_endpoint",
        description=(
            "Add a custom action endpoint to an existing viewset — "
            "define the route, handler, permissions, and serializer."
        ),
        category="api",
        default_goal_template=(
            "Add a '{action_name}' action to the {viewset_name} viewset."
        ),
        risk_level="medium",
        usage_kind="write",
        default_sections=["routes", "models", "ai_hints"],
        steps=[
            AgentPlaybookStep(
                id="define_action",
                title="Define the action method",
                description=(
                    "Add the action method to the viewset class with "
                    "proper decorator and request/response handling."
                ),
                recommended_sections=["routes", "models"],
                estimated_impact="new endpoint",
            ),
            AgentPlaybookStep(
                id="set_permissions",
                title="Set permissions",
                description="Configure appropriate permissions for the new action.",
                recommended_sections=["ai_hints"],
                estimated_impact="security scope",
            ),
            AgentPlaybookStep(
                id="add_serializer",
                title="Add request/response serializer",
                description=(
                    "Create or update serializers for the action's "
                    "input and output."
                ),
                recommended_sections=["models"],
                estimated_impact="API contract",
            ),
            AgentPlaybookStep(
                id="test_endpoint",
                title="Test the endpoint",
                description="Verify the new action is accessible and returns correct data.",
                recommended_sections=["routes", "diagnostics"],
                estimated_impact="low risk",
            ),
        ],
        tags=["action", "endpoint", "viewset", "api", "route"],
    ),

    # -------------------------------------------------------------------------
    # 3. Fix Migration Conflicts
    # -------------------------------------------------------------------------
    AgentPlaybook(
        key="fix_migration_conflicts",
        label="Fix Migration Conflicts",
        kind="fix_migrations",
        description=(
            "Resolve migration conflicts caused by divergent branches — "
            "identify the conflict, merge operations, and re-sequence."
        ),
        category="migrations",
        default_goal_template=(
            "Resolve migration conflicts in the {app_label} app."
        ),
        risk_level="high",
        usage_kind="admin",
        default_sections=["migrations", "models", "diagnostics"],
        steps=[
            AgentPlaybookStep(
                id="identify_conflicts",
                title="Identify conflicting migrations",
                description=(
                    "List migrations with duplicate sequence numbers "
                    "or broken dependency chains."
                ),
                recommended_sections=["migrations"],
                estimated_impact="diagnostic",
            ),
            AgentPlaybookStep(
                id="merge_operations",
                title="Merge operations",
                description=(
                    "Combine the conflicting migration operations into "
                    "a single consistent migration."
                ),
                recommended_sections=["migrations", "models"],
                estimated_impact="migration rewrite",
            ),
            AgentPlaybookStep(
                id="resequence",
                title="Re-sequence migrations",
                description="Fix the dependency graph so all migrations form a linear chain.",
                recommended_sections=["migrations"],
                estimated_impact="dependency change",
            ),
            AgentPlaybookStep(
                id="validate",
                title="Validate the migration graph",
                description=(
                    "Run diagnostics to confirm the migration graph "
                    "is clean and apply to a test database."
                ),
                recommended_sections=["diagnostics", "migrations"],
                estimated_impact="database state",
            ),
        ],
        tags=["migration", "conflict", "merge", "rebase", "graph"],
        notes="Back up the database before applying merged migrations.",
    ),

    # -------------------------------------------------------------------------
    # 4. Add a Validation Rule
    # -------------------------------------------------------------------------
    AgentPlaybook(
        key="add_validation_rule",
        label="Add Validation Rule",
        kind="add_validation",
        description=(
            "Add a field-level or model-level validation rule — "
            "define the constraint, add error messages, and test edge cases."
        ),
        category="schema",
        default_goal_template=(
            "Add a validation rule for '{field_name}' on the {model_name} model: {rule_description}."
        ),
        risk_level="low",
        usage_kind="write",
        default_sections=["models", "routes"],
        steps=[
            AgentPlaybookStep(
                id="define_validator",
                title="Define the validator",
                description=(
                    "Add a field validator or model validator method "
                    "with the constraint logic."
                ),
                recommended_sections=["models"],
                estimated_impact="validation logic",
            ),
            AgentPlaybookStep(
                id="error_messages",
                title="Add error messages",
                description="Provide clear, user-facing error messages for validation failures.",
                recommended_sections=["models"],
                estimated_impact="UX",
            ),
            AgentPlaybookStep(
                id="test_cases",
                title="Test edge cases",
                description=(
                    "Verify the validator accepts good input and "
                    "rejects bad input with correct error messages."
                ),
                recommended_sections=["models", "diagnostics"],
                estimated_impact="low risk",
            ),
        ],
        tags=["validation", "constraint", "field", "model", "rule"],
    ),

    # -------------------------------------------------------------------------
    # 5. Harden Endpoint Permissions
    # -------------------------------------------------------------------------
    AgentPlaybook(
        key="harden_endpoint_permissions",
        label="Harden Permissions",
        kind="harden_permissions",
        description=(
            "Review and tighten permissions on API endpoints — "
            "audit current access, add missing checks, and verify enforcement."
        ),
        category="api",
        default_goal_template=(
            "Review and harden permissions on the {endpoint_or_viewset} endpoint(s)."
        ),
        risk_level="medium",
        usage_kind="admin",
        default_sections=["routes", "ai_hints", "models"],
        steps=[
            AgentPlaybookStep(
                id="audit_current",
                title="Audit current permissions",
                description=(
                    "List all endpoints and their current permission "
                    "classes or decorators."
                ),
                recommended_sections=["routes", "ai_hints"],
                estimated_impact="diagnostic",
            ),
            AgentPlaybookStep(
                id="identify_gaps",
                title="Identify permission gaps",
                description=(
                    "Find endpoints lacking authentication, "
                    "authorization, or rate-limiting."
                ),
                recommended_sections=["ai_hints"],
                estimated_impact="security review",
            ),
            AgentPlaybookStep(
                id="apply_fixes",
                title="Apply permission fixes",
                description="Add or update permission classes on vulnerable endpoints.",
                recommended_sections=["routes", "models"],
                estimated_impact="access control change",
            ),
            AgentPlaybookStep(
                id="verify_enforcement",
                title="Verify enforcement",
                description=(
                    "Test that unauthenticated and unauthorized requests "
                    "are correctly rejected."
                ),
                recommended_sections=["diagnostics"],
                estimated_impact="security validation",
            ),
        ],
        tags=["permissions", "security", "auth", "access", "hardening"],
        notes="Review AI hints for high-risk routes first.",
    ),

    # -------------------------------------------------------------------------
    # 6. Debug Slow Queries
    # -------------------------------------------------------------------------
    AgentPlaybook(
        key="debug_slow_queries",
        label="Debug Slow Queries",
        kind="debug_queries",
        description=(
            "Investigate and optimize slow database queries — "
            "identify bottlenecks, add indexes, and verify improvements."
        ),
        category="diagnostics",
        default_goal_template=(
            "Investigate and optimize slow queries in the {area_or_endpoint} area."
        ),
        risk_level="low",
        usage_kind="read_only",
        default_sections=["db_queries", "models", "diagnostics"],
        steps=[
            AgentPlaybookStep(
                id="identify_slow",
                title="Identify slow queries",
                description=(
                    "Review the query inspector data for queries "
                    "exceeding acceptable duration thresholds."
                ),
                recommended_sections=["db_queries"],
                estimated_impact="diagnostic",
            ),
            AgentPlaybookStep(
                id="analyze_plans",
                title="Analyze query plans",
                description=(
                    "Check for missing indexes, sequential scans, "
                    "and excessive joins."
                ),
                recommended_sections=["db_queries", "models"],
                estimated_impact="analysis",
            ),
            AgentPlaybookStep(
                id="optimize",
                title="Apply optimizations",
                description=(
                    "Add indexes, optimize queryset usage, or "
                    "restructure queries for better performance."
                ),
                recommended_sections=["models"],
                estimated_impact="performance improvement",
            ),
            AgentPlaybookStep(
                id="measure",
                title="Measure improvement",
                description="Re-run the slow queries and compare timings before and after.",
                recommended_sections=["db_queries", "diagnostics"],
                estimated_impact="verification",
            ),
        ],
        tags=["query", "performance", "slow", "index", "database", "optimize"],
    ),

    # -------------------------------------------------------------------------
    # 7. Refactor Model and Serializer
    # -------------------------------------------------------------------------
    AgentPlaybook(
        key="refactor_model_and_serializer",
        label="Refactor Model & Serializer",
        kind="refactor_viewset",
        description=(
            "Refactor a model and its serializer together — "
            "rename fields, extract sub-models, and update all references."
        ),
        category="schema",
        default_goal_template=(
            "Refactor the {model_name} model: {refactor_description}."
        ),
        risk_level="medium",
        usage_kind="write",
        default_sections=["models", "routes", "migrations", "schema_checksum"],
        steps=[
            AgentPlaybookStep(
                id="plan_changes",
                title="Plan changes",
                description=(
                    "List all fields to rename, extract, or remove "
                    "and identify affected serializers and endpoints."
                ),
                recommended_sections=["models", "routes"],
                estimated_impact="planning",
            ),
            AgentPlaybookStep(
                id="update_model",
                title="Update the model",
                description="Apply field renames, extractions, or structural changes to the model.",
                recommended_sections=["models"],
                estimated_impact="schema change",
            ),
            AgentPlaybookStep(
                id="update_serializer",
                title="Update the serializer",
                description="Mirror model changes in the serializer and update field mappings.",
                recommended_sections=["routes", "models"],
                estimated_impact="API contract change",
            ),
            AgentPlaybookStep(
                id="generate_migration",
                title="Generate migration",
                description="Create a migration for the schema changes.",
                recommended_sections=["migrations"],
                estimated_impact="database migration",
            ),
            AgentPlaybookStep(
                id="update_references",
                title="Update references",
                description=(
                    "Find and update all code referencing the old "
                    "field names or model structure."
                ),
                recommended_sections=["routes", "models"],
                estimated_impact="code updates",
            ),
        ],
        tags=["refactor", "model", "serializer", "rename", "extract"],
        notes="Generate migrations after all model changes are applied.",
    ),

    # -------------------------------------------------------------------------
    # 8. Identify Root Cause from Search
    # -------------------------------------------------------------------------
    AgentPlaybook(
        key="identify_root_cause_from_search",
        label="Root Cause from Search",
        kind="debug_queries",
        description=(
            "Use semantic search to cross-reference models, routes, settings, "
            "and queries to identify the root cause of a bug or issue."
        ),
        category="diagnostics",
        default_goal_template=(
            "Search for the root cause of: {issue_description}. "
            "Cross-reference related models, routes, and settings."
        ),
        risk_level="low",
        usage_kind="read_only",
        default_sections=["semantic_index", "models", "routes", "diagnostics"],
        steps=[
            AgentPlaybookStep(
                id="search_codebase",
                title="Search the codebase",
                description=(
                    "Use semantic search to find all models, routes, settings, "
                    "and queries related to the reported issue."
                ),
                recommended_sections=["semantic_index"],
                estimated_impact="diagnostic",
            ),
            AgentPlaybookStep(
                id="cross_reference",
                title="Cross-reference results",
                description=(
                    "Correlate search results across different kinds "
                    "(models, routes, queries) to narrow down the cause."
                ),
                recommended_sections=["models", "routes", "db_queries"],
                estimated_impact="analysis",
            ),
            AgentPlaybookStep(
                id="check_settings",
                title="Check related settings",
                description=(
                    "Verify that related configuration settings are correct "
                    "and environment variables are properly set."
                ),
                recommended_sections=["semantic_index", "diagnostics"],
                estimated_impact="diagnostic",
            ),
            AgentPlaybookStep(
                id="propose_fix",
                title="Propose a fix",
                description=(
                    "Based on the cross-referenced evidence, propose a targeted "
                    "fix with the least possible side effects."
                ),
                recommended_sections=["models", "routes"],
                estimated_impact="recommended action",
            ),
        ],
        tags=["search", "debug", "root-cause", "cross-reference", "semantic"],
        notes="Uses the v0.5.22 semantic search index for cross-referencing.",
    ),
]


# =============================================================================
# Registry Functions
# =============================================================================


def _build_aggregate_counts(
    playbooks: List[AgentPlaybook],
) -> Dict[str, Dict[str, int]]:
    """Build by_category, by_risk_level, by_usage_kind aggregate count dicts."""
    by_category: Dict[str, int] = {}
    by_risk_level: Dict[str, int] = {}
    by_usage_kind: Dict[str, int] = {}
    for pb in playbooks:
        by_category[pb.category] = by_category.get(pb.category, 0) + 1
        by_risk_level[pb.risk_level] = by_risk_level.get(pb.risk_level, 0) + 1
        by_usage_kind[pb.usage_kind] = by_usage_kind.get(pb.usage_kind, 0) + 1
    return {
        "by_category": by_category,
        "by_risk_level": by_risk_level,
        "by_usage_kind": by_usage_kind,
    }


def build_playbook_set(
    playbooks: List[AgentPlaybook],
) -> AgentPlaybookSet:
    """Wrap a list of playbooks into an AgentPlaybookSet with aggregates."""
    agg = _build_aggregate_counts(playbooks)
    return AgentPlaybookSet(
        playbooks=playbooks,
        total_count=len(playbooks),
        by_category=agg["by_category"],
        by_risk_level=agg["by_risk_level"],
        by_usage_kind=agg["by_usage_kind"],
    )


def get_builtin_playbooks(
    *,
    category: Optional[str] = None,
    risk_level: Optional[str] = None,
    usage_kind: Optional[str] = None,
) -> AgentPlaybookSet:
    """
    Return the set of built-in playbooks, optionally filtered.

    Args:
        category: Filter by category (e.g. "schema", "api", "migrations").
        risk_level: Filter by risk level ("low", "medium", "high").
        usage_kind: Filter by usage kind ("read_only", "write", "admin").

    Returns:
        AgentPlaybookSet with matching playbooks and aggregate counts.
    """
    filtered = list(_BUILTIN_PLAYBOOKS)
    if category:
        filtered = [p for p in filtered if p.category == category]
    if risk_level:
        filtered = [p for p in filtered if p.risk_level == risk_level]
    if usage_kind:
        filtered = [p for p in filtered if p.usage_kind == usage_kind]
    return build_playbook_set(filtered)


def get_playbook_by_key(key: str) -> Optional[AgentPlaybook]:
    """
    Look up a single built-in playbook by its unique key.

    Args:
        key: The playbook key (e.g. "add_field_to_model").

    Returns:
        The matching AgentPlaybook or None if not found.
    """
    for pb in _BUILTIN_PLAYBOOKS:
        if pb.key == key:
            return pb
    return None
