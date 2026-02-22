"""
Aksara Agentic Workflows — Plans, Not Pushes.

v0.5.23: Structured workflow builder that combines diagnostics, search,
inspectors, and playbooks into actionable step-by-step plans.

All workflows are read-only / dry-run.  Nothing is auto-executed.
Commands and notes are for display only — humans review and apply.
"""

from __future__ import annotations

import hashlib
import time
from collections import Counter
from typing import Any, Dict, List, Optional

from aksara.studio.models import (
    AgentWorkflow,
    AgentWorkflowStep,
)


# =============================================================================
# Helpers
# =============================================================================


def _make_step_id(kind: str, index: int, goal: str) -> str:
    """Deterministic step ID from kind + index + goal hash."""
    h = hashlib.md5(f"{kind}:{index}:{goal}".encode()).hexdigest()[:8]
    return f"step-{kind}-{h}"


def _make_workflow_id(goal: str) -> str:
    """Deterministic workflow ID from goal hash + timestamp."""
    h = hashlib.md5(f"{goal}:{time.time()}".encode()).hexdigest()[:12]
    return f"wf-{h}"


def _risk_from_severity(severity: str) -> str:
    """Map diagnostic severity to risk level."""
    mapping = {"error": "high", "warning": "medium", "info": "low"}
    return mapping.get(severity, "low")


def _effort_from_kind(kind: str) -> str:
    """Estimate effort from step kind."""
    high_effort = {"edit_file", "run_migration"}
    medium_effort = {"run_query", "run_test", "config", "environment"}
    if kind in high_effort:
        return "high"
    if kind in medium_effort:
        return "medium"
    return "low"


# =============================================================================
# Lazy Import Helpers
# =============================================================================
# These helpers centralise deferred imports that would otherwise cause circular
# import chains at module-load time.  Using explicit helpers (rather than bare
# ``from … import …`` inside function bodies) gives tests a single, stable
# patch target:  ``aksara.ai.workflows._get_<name>``.
#
# Pattern:
#   def _get_foo():
#       from some.module import foo
#       return foo
#
# Test patch:
#   @patch("aksara.ai.workflows._get_foo", return_value=mock_foo)
# =============================================================================


def _get_run_all_checks():
    """Lazy import: aksara.diagnostics.run_all_checks.

    Deferred because diagnostics may pull in asyncpg/settings,
    and importing eagerly would create a circular chain via
    aksara.conf → models → diagnostics.
    """
    from aksara.diagnostics import run_all_checks
    return run_all_checks


def _get_search_index_and_builder():
    """Lazy import: aksara.search.engine.SearchIndex + indexers.build_full_index.

    Deferred because the search subsystem imports aksara.studio.utils
    for route info, which in turn imports this very module for workflow
    re-exports — creating a potential circular chain.
    """
    from aksara.search.engine import SearchIndex
    from aksara.search.indexers import build_full_index
    return SearchIndex, build_full_index


def _get_playbook(key: str):
    """Lazy import: aksara.ai.playbooks.get_playbook_by_key.

    Deferred to avoid a playbooks ↔ workflows cross-import cycle.
    Tests should patch ``aksara.ai.workflows._get_playbook``.
    """
    from aksara.ai.playbooks import get_playbook_by_key
    return get_playbook_by_key(key)


# =============================================================================
# Diagnostic Steps Builder
# =============================================================================


def _build_diagnostic_steps(
    goal: str,
    limit: int = 10,
    start_order: int = 1,
) -> List[AgentWorkflowStep]:
    """Build workflow steps from the diagnostics engine.

    Calls run_all_checks() and converts issues to workflow steps.
    """
    steps: List[AgentWorkflowStep] = []
    try:
        import asyncio
        run_all_checks = _get_run_all_checks()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in async context — can't await synchronously.
            # Return a single meta-step pointing at the check command.
            steps.append(AgentWorkflowStep(
                id=_make_step_id("diagnostics", 0, goal),
                kind="diagnostics",
                title="Run diagnostic health checks",
                description=(
                    "Execute the full diagnostics suite to identify issues "
                    "related to your goal."
                ),
                references={"goal": goal},
                estimated_effort="low",
                risk="low",
                commands=["aksara doctor --format table"],
                notes=["Review the doctor report for errors and warnings."],
                order=start_order,
            ))
            return steps

        report = asyncio.run(run_all_checks())

        if not report.issues:
            steps.append(AgentWorkflowStep(
                id=_make_step_id("diagnostics", 0, goal),
                kind="diagnostics",
                title="Run diagnostic health checks",
                description="All diagnostics passed — no issues found.",
                references={"status": "ok"},
                estimated_effort="low",
                risk="low",
                commands=["aksara doctor --format table"],
                notes=["Diagnostics are clean. Proceed to inspection."],
                order=start_order,
            ))
            return steps

        for i, issue in enumerate(report.issues[:limit]):
            refs: Dict[str, Any] = {"kind": issue.kind, "severity": issue.severity}
            if issue.meta:
                refs["meta"] = issue.meta

            cmds: List[str] = []
            notes: List[str] = []

            if issue.hint:
                notes.append(f"Hint: {issue.hint}")

            # Translate autoremediation actions to commands/notes
            for action in issue.actions:
                if action.kind == "run_command":
                    cmds.append(action.target)
                elif action.kind == "set_env":
                    cmds.append(f"export {action.target}={action.example or '...'}")
                    notes.append(action.title)
                elif action.kind == "edit_file":
                    notes.append(f"Edit: {action.target}")
                    if action.example:
                        notes.append(f"  Snippet: {action.example}")
                elif action.kind == "add_setting":
                    notes.append(f"Add setting: {action.target}")
                    if action.example:
                        notes.append(f"  Value: {action.example}")
                elif action.kind == "open_doc":
                    notes.append(f"See docs: {action.target}")

            if not cmds:
                cmds.append("aksara doctor --format table")

            steps.append(AgentWorkflowStep(
                id=_make_step_id("diagnostics", i, goal),
                kind="diagnostics",
                title=issue.title,
                description=issue.message,
                references=refs,
                estimated_effort=_effort_from_kind("diagnostics"),
                risk=_risk_from_severity(issue.severity),
                commands=cmds,
                notes=notes,
                order=start_order + i,
            ))
    except Exception:
        steps.append(AgentWorkflowStep(
            id=_make_step_id("diagnostics", 0, goal),
            kind="diagnostics",
            title="Run diagnostic health checks",
            description="Run the diagnostics suite to check project health.",
            references={"goal": goal},
            estimated_effort="low",
            risk="low",
            commands=["aksara doctor --format table"],
            notes=["Could not run diagnostics automatically."],
            order=start_order,
        ))

    return steps


# =============================================================================
# Search Steps Builder
# =============================================================================


def _build_search_steps(
    goal: str,
    search_query: Optional[str] = None,
    limit: int = 10,
    start_order: int = 100,
) -> List[AgentWorkflowStep]:
    """Build workflow steps from semantic search results."""
    steps: List[AgentWorkflowStep] = []
    query = search_query or goal

    try:
        _SearchIndex, build_full_index = _get_search_index_and_builder()

        index = build_full_index()
        results = index.search(query, top_k=limit, mode="hybrid")

        if not results:
            steps.append(AgentWorkflowStep(
                id=_make_step_id("search", 0, goal),
                kind="search",
                title="Search for related code",
                description=f"No search results found for: {query}",
                references={"query": query},
                estimated_effort="low",
                risk="low",
                commands=[f"aksara search query \"{query}\""],
                notes=["Try broadening your search terms."],
                order=start_order,
            ))
            return steps

        for i, result in enumerate(results):
            refs: Dict[str, Any] = {
                "query": query,
                "kind": result.document.kind,
                "title": result.document.title,
                "score": round(result.score, 3),
                "source": result.document.source,
            }
            if result.document.metadata:
                refs["metadata"] = result.document.metadata

            notes: List[str] = []
            if result.highlights:
                notes.append(f"Matches: {'; '.join(result.highlights[:3])}")
            notes.append("Review this item for relevance to your goal.")

            cmds: List[str] = []
            kind = result.document.kind
            if kind == "model":
                model_name = result.document.title
                cmds.append(f"aksara inspect models --model {model_name}")
            elif kind == "route":
                cmds.append(f"aksara inspect routes")
            elif kind == "query":
                cmds.append("aksara inspect queries --top 10")
            elif kind == "setting":
                cmds.append("aksara studio settings")
            elif kind == "playbook":
                pb_key = (result.document.metadata or {}).get("key", "")
                if pb_key:
                    cmds.append(f"aksara agent playbook-run --playbook {pb_key}")
            elif kind == "migration":
                cmds.append("aksara migrate --check")
            else:
                cmds.append(f"aksara search query \"{query}\"")

            steps.append(AgentWorkflowStep(
                id=_make_step_id("search", i, goal),
                kind="search",
                title=f"Review: {result.document.title} ({kind})",
                description=result.document.summary or result.document.content[:120],
                references=refs,
                estimated_effort="low",
                risk="low",
                commands=cmds,
                notes=notes,
                order=start_order + i,
            ))
    except Exception:
        steps.append(AgentWorkflowStep(
            id=_make_step_id("search", 0, goal),
            kind="search",
            title="Search for related code",
            description=f"Search for: {query}",
            references={"query": query},
            estimated_effort="low",
            risk="low",
            commands=[f"aksara search query \"{query}\""],
            notes=["Run the search command to find related items."],
            order=start_order,
        ))

    return steps


# =============================================================================
# Inspector Steps Builder
# =============================================================================


def _build_inspector_steps(
    goal: str,
    playbook_kind: Optional[str] = None,
    start_order: int = 50,
) -> List[AgentWorkflowStep]:
    """Build workflow steps for inspecting models and queries."""
    steps: List[AgentWorkflowStep] = []

    # Model inspection step
    steps.append(AgentWorkflowStep(
        id=_make_step_id("inspect", 0, goal),
        kind="inspect",
        title="Inspect registered models",
        description=(
            "Review model schemas, fields, relationships, and constraints "
            "to understand the data layer relevant to your goal."
        ),
        references={"target": "models", "goal": goal},
        estimated_effort="low",
        risk="low",
        commands=[
            "aksara inspect models",
            "aksara inspect models --format json",
        ],
        notes=["Check field types, relationships, and constraints."],
        order=start_order,
    ))

    # Query inspection step
    query_targets = {"debug_slow_queries", "optimize_query", "run_query"}
    if playbook_kind in query_targets or "query" in goal.lower() or "slow" in goal.lower():
        steps.append(AgentWorkflowStep(
            id=_make_step_id("inspect", 1, goal),
            kind="inspect",
            title="Inspect slow queries",
            description="Analyse the slowest queries for potential optimisation.",
            references={"target": "queries", "goal": goal},
            estimated_effort="medium",
            risk="low",
            commands=[
                "aksara inspect queries --top 10",
                "aksara inspect queries --format table",
            ],
            notes=[
                "Look for missing indexes, full table scans, and N+1 patterns.",
            ],
            order=start_order + 1,
        ))

    return steps


# =============================================================================
# Playbook Steps Builder
# =============================================================================


def _build_playbook_steps(
    playbook_key: str,
    goal: str,
    start_order: int = 200,
) -> List[AgentWorkflowStep]:
    """Convert playbook steps into workflow steps."""
    steps: List[AgentWorkflowStep] = []
    try:
        pb = _get_playbook(playbook_key)
        if pb is None:
            return steps

        for i, ps in enumerate(pb.steps):
            steps.append(AgentWorkflowStep(
                id=_make_step_id("config", i, f"{playbook_key}:{goal}"),
                kind=_map_playbook_step_kind(ps.key),
                title=ps.title,
                description=ps.description,
                references={
                    "playbook": playbook_key,
                    "step_key": ps.key,
                },
                estimated_effort=_effort_from_kind(
                    _map_playbook_step_kind(ps.key)
                ),
                risk=pb.risk_level,
                commands=[],
                notes=[],
                order=start_order + i,
            ))
    except Exception:
        pass

    return steps


def _map_playbook_step_kind(step_key: str) -> str:
    """Map a playbook step key to a workflow step kind."""
    mapping = {
        "inspect": "inspect",
        "search": "search",
        "edit": "edit_file",
        "migrat": "run_migration",
        "test": "run_test",
        "query": "run_query",
        "env": "environment",
        "config": "config",
        "diagnos": "diagnostics",
        "doc": "doc_reading",
    }
    step_lower = step_key.lower()
    for prefix, kind in mapping.items():
        if prefix in step_lower:
            return kind
    return "config"


# =============================================================================
# Test Steps Builder
# =============================================================================


def _build_test_step(goal: str, start_order: int = 300) -> AgentWorkflowStep:
    """Build a final 'run tests' step."""
    return AgentWorkflowStep(
        id=_make_step_id("run_test", 0, goal),
        kind="run_test",
        title="Run test suite",
        description="Verify changes by running the project test suite.",
        references={"goal": goal},
        estimated_effort="medium",
        risk="low",
        commands=[
            "python -m pytest -x -q",
            "aksara test",
        ],
        notes=[
            "Run after applying any changes to ensure nothing is broken.",
        ],
        order=start_order,
    )


# =============================================================================
# Core Builder
# =============================================================================


def build_agent_workflow(
    goal: str,
    *,
    playbook: Optional[str] = None,
    include_diagnostics: bool = True,
    include_search: bool = True,
    search_query: Optional[str] = None,
    search_limit: int = 10,
    diagnostics_limit: int = 10,
) -> AgentWorkflow:
    """Build a structured agent workflow from existing systems.

    Combines diagnostics, inspectors, semantic search, and playbooks
    into an ordered sequence of actionable steps.

    Args:
        goal: What the user wants to accomplish.
        playbook: Optional playbook key to guide step generation.
        include_diagnostics: Run diagnostics and include issue steps.
        include_search: Run semantic search and include result steps.
        search_query: Custom search query (defaults to goal).
        search_limit: Max search results to include.
        diagnostics_limit: Max diagnostic issues to include.

    Returns:
        AgentWorkflow with ordered steps.
    """
    all_steps: List[AgentWorkflowStep] = []
    metadata: Dict[str, Any] = {"goal": goal}
    source = "manual"

    # Resolve playbook metadata
    playbook_kind: Optional[str] = None
    if playbook:
        try:
            pb = _get_playbook(playbook)
            if pb:
                playbook_kind = pb.kind
                metadata["playbook_key"] = playbook
                metadata["playbook_label"] = pb.label
                metadata["playbook_risk"] = pb.risk_level
        except Exception:
            pass

    # v0.5.28: Inject AI Hub defaults into metadata
    try:
        from aksara.ai.hub_settings import load_aihub_settings
        hub = load_aihub_settings()
        metadata["ai_hub"] = {
            "active_provider": hub.active_provider,
            "chat_model": hub.defaults.chat_model if hub.defaults else None,
            "code_model": hub.defaults.code_model if hub.defaults else None,
            "embeddings_model": hub.defaults.embeddings_model if hub.defaults else None,
        }
    except Exception:
        pass

    # 1. Diagnostics (order 1–N)
    if include_diagnostics:
        diag_steps = _build_diagnostic_steps(
            goal, limit=diagnostics_limit, start_order=1
        )
        all_steps.extend(diag_steps)
        if diag_steps:
            source = "doctor"

    # 2. Inspectors (order 50–59)
    inspector_steps = _build_inspector_steps(
        goal, playbook_kind=playbook_kind, start_order=50
    )
    all_steps.extend(inspector_steps)

    # 3. Search (order 100–N)
    if include_search:
        search_steps = _build_search_steps(
            goal,
            search_query=search_query,
            limit=search_limit,
            start_order=100,
        )
        all_steps.extend(search_steps)
        if source == "doctor":
            source = "mixed"
        elif source == "manual":
            source = "search"
        metadata["search_query"] = search_query or goal

    # 4. Playbook steps (order 200–N)
    if playbook:
        pb_steps = _build_playbook_steps(playbook, goal, start_order=200)
        all_steps.extend(pb_steps)
        if pb_steps:
            source = "mixed"

    # 5. Final test step (order 300)
    all_steps.append(_build_test_step(goal, start_order=300))

    # Sort by order
    all_steps.sort(key=lambda s: s.order)

    return AgentWorkflow(
        id=_make_workflow_id(goal),
        goal=goal,
        playbook=playbook,
        source=source,
        steps=all_steps,
        metadata=metadata,
    )


# =============================================================================
# Helpers: Summary & Stats
# =============================================================================


def summarize_agent_workflow(workflow: AgentWorkflow) -> str:
    """Generate a 1-3 sentence natural-language summary of a workflow."""
    n = len(workflow.steps)
    kinds = Counter(s.kind for s in workflow.steps)
    top_kinds = ", ".join(
        f"{count} {kind}" for kind, count in kinds.most_common(3)
    )

    parts = [f"Workflow for \"{workflow.goal}\" with {n} steps ({top_kinds})."]

    high_risk = sum(1 for s in workflow.steps if s.risk == "high")
    if high_risk:
        parts.append(f"{high_risk} step(s) are high-risk — review carefully.")

    if workflow.playbook:
        parts.append(f"Guided by playbook: {workflow.playbook}.")

    return " ".join(parts)


def workflow_stats(workflow: AgentWorkflow) -> Dict[str, Any]:
    """Compute step counts by kind, risk, and effort."""
    by_kind: Dict[str, int] = {}
    by_risk: Dict[str, int] = {}
    by_effort: Dict[str, int] = {}

    for step in workflow.steps:
        by_kind[step.kind] = by_kind.get(step.kind, 0) + 1
        risk_key = step.risk or "none"
        by_risk[risk_key] = by_risk.get(risk_key, 0) + 1
        by_effort[step.estimated_effort] = by_effort.get(step.estimated_effort, 0) + 1

    return {
        "total_steps": len(workflow.steps),
        "by_kind": by_kind,
        "by_risk": by_risk,
        "by_effort": by_effort,
        "has_high_risk": by_risk.get("high", 0) > 0,
        "playbook": workflow.playbook,
        "source": workflow.source,
    }
