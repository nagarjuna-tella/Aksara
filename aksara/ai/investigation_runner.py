"""
AI Investigation Runner  (v0.5.39)

Executes an investigation plan step-by-step, calling the appropriate
analyser for each step and collecting results into the session.

The runner is **synchronous** (like the rest of the AI engine pipeline)
and uses lazy imports to avoid circular dependencies.

Usage::

    from aksara.ai.investigation_runner import execute_investigation
    session = execute_investigation(session)

Steps are executed in order.  If a step fails, it is marked as
``"failed"`` and execution continues with the remaining steps.
The session is updated in the store after each step completes.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

from aksara.ai.investigation import InvestigationSession
from aksara.ai.plan_builder import (
    STEP_ARCHITECTURE,
    STEP_DEBUG,
    STEP_PERFORMANCE,
    STEP_PROJECT_GRAPH,
    STEP_SUMMARISE,
)

logger = logging.getLogger("aksara.ai.investigation_runner")


# ─── Step Executors ──────────────────────────────────────────────────────────


def _run_project_graph() -> Dict[str, Any]:
    """Execute the project graph step."""
    from aksara.ai.project_graph import build_project_graph

    graph = build_project_graph(rebuild=True)
    return graph.to_summary_dict()


def _run_performance_analysis() -> Dict[str, Any]:
    """Execute the performance analysis step."""
    from aksara.ai.performance_analyzer import run_performance_analysis

    report = run_performance_analysis()
    return report.to_summary_dict()


def _run_architecture_review() -> Dict[str, Any]:
    """Execute the architecture review step."""
    from aksara.ai.architecture_review import run_architecture_review

    report = run_architecture_review()
    return report.to_summary_dict()


def _run_debug_analysis(goal: str) -> Dict[str, Any]:
    """Execute the debug analysis step."""
    from aksara.ai.debugger import run_debugger

    report = run_debugger(query=goal)
    return report.to_summary_dict()


def _run_summarise(session: InvestigationSession) -> Dict[str, Any]:
    """Build a summary from the completed steps."""
    completed = []
    for step in (session.plan.steps if session.plan else []):
        if step.status == "done" and step.result:
            completed.append(
                {"step": step.name, "result_keys": list(step.result.keys())}
            )
    return {
        "completed_steps": len(completed),
        "total_findings": len(session.findings),
        "steps_summary": completed,
    }


# ─── Step Dispatch ───────────────────────────────────────────────────────────

_STEP_DISPATCH = {
    STEP_PROJECT_GRAPH: lambda _goal, _session: _run_project_graph(),
    STEP_PERFORMANCE: lambda _goal, _session: _run_performance_analysis(),
    STEP_ARCHITECTURE: lambda _goal, _session: _run_architecture_review(),
    STEP_DEBUG: lambda goal, _session: _run_debug_analysis(goal),
    STEP_SUMMARISE: lambda _goal, session: _run_summarise(session),
}


# ─── Public API ──────────────────────────────────────────────────────────────


def execute_investigation(session: InvestigationSession) -> InvestigationSession:
    """Execute all pending steps in the session's plan.

    Steps are executed sequentially.  Each step is marked as
    ``"running"`` → ``"done"`` or ``"failed"``.  Key findings are
    extracted and appended to ``session.findings``.

    The session is persisted via the session store after each step.

    Args:
        session: The investigation session to execute.

    Returns:
        The updated session with step results and findings.
    """
    from aksara.ai.session_store import update_session

    if not session.plan or not session.plan.steps:
        session.status = "failed"
        update_session(session)
        return session

    session.status = "running"
    update_session(session)

    for step in session.plan.steps:
        if step.status != "pending":
            continue

        step.status = "running"
        step.started_at = datetime.now(timezone.utc).isoformat()
        update_session(session)

        executor = _STEP_DISPATCH.get(step.name)
        if executor is None:
            step.status = "skipped"
            step.error = f"Unknown step: {step.name}"
            step.completed_at = datetime.now(timezone.utc).isoformat()
            update_session(session)
            continue

        try:
            result = executor(session.goal, session)
            step.result = result
            step.status = "done"
            step.completed_at = datetime.now(timezone.utc).isoformat()

            # Extract a finding from the result.
            finding = _extract_finding(step.name, result)
            if finding:
                session.add_finding(finding)

        except Exception as exc:
            step.status = "failed"
            step.error = str(exc)
            step.completed_at = datetime.now(timezone.utc).isoformat()
            logger.warning("Step %s failed: %s", step.name, exc)

        update_session(session)

    # Determine final status.
    statuses = {s.status for s in session.plan.steps}
    if all(s == "done" for s in statuses):
        session.status = "completed"
    elif "failed" in statuses and "done" in statuses:
        session.status = "completed"  # partial success is still "completed"
    elif all(s == "failed" for s in statuses):
        session.status = "failed"
    else:
        session.status = "completed"

    update_session(session)
    return session


def execute_next_step(session: InvestigationSession) -> InvestigationSession:
    """Execute only the next pending step.

    Useful for step-by-step interactive execution from the UI.

    Args:
        session: The investigation session.

    Returns:
        The updated session.
    """
    from aksara.ai.session_store import update_session

    if not session.plan or not session.plan.steps:
        return session

    if session.status == "created":
        session.status = "running"

    for step in session.plan.steps:
        if step.status != "pending":
            continue

        step.status = "running"
        step.started_at = datetime.now(timezone.utc).isoformat()
        update_session(session)

        executor = _STEP_DISPATCH.get(step.name)
        if executor is None:
            step.status = "skipped"
            step.error = f"Unknown step: {step.name}"
            step.completed_at = datetime.now(timezone.utc).isoformat()
            update_session(session)
            return session

        try:
            result = executor(session.goal, session)
            step.result = result
            step.status = "done"
            step.completed_at = datetime.now(timezone.utc).isoformat()
            finding = _extract_finding(step.name, result)
            if finding:
                session.add_finding(finding)
        except Exception as exc:
            step.status = "failed"
            step.error = str(exc)
            step.completed_at = datetime.now(timezone.utc).isoformat()
            logger.warning("Step %s failed: %s", step.name, exc)

        update_session(session)
        break  # only one step

    # Check if all steps are done.
    pending = [s for s in session.plan.steps if s.status == "pending"]
    if not pending:
        session.status = "completed"
        update_session(session)

    return session


# ─── Finding Extraction ──────────────────────────────────────────────────────


def _extract_finding(step_name: str, result: Dict[str, Any]) -> str | None:
    """Extract a human-readable finding from a step result."""
    if step_name == STEP_PROJECT_GRAPH:
        counts = result.get("counts", {})
        models = counts.get("models", 0)
        routes = counts.get("routes", 0)
        return f"Project has {models} models and {routes} routes."

    if step_name == STEP_PERFORMANCE:
        score = result.get("score")
        grade = result.get("grade", "?")
        if score is not None:
            return f"Performance score: {score}/100 (grade {grade})."
        return None

    if step_name == STEP_ARCHITECTURE:
        score = result.get("score")
        grade = result.get("grade", "?")
        if score is not None:
            return f"Architecture score: {score}/100 (grade {grade})."
        return None

    if step_name == STEP_DEBUG:
        ok = result.get("ok")
        issues = result.get("issues_count", result.get("issue_count", 0))
        return f"Debug analysis: {'clean' if ok else f'{issues} issue(s) found'}."

    if step_name == STEP_SUMMARISE:
        total = result.get("total_findings", 0)
        return f"Investigation complete with {total} findings."

    return None
