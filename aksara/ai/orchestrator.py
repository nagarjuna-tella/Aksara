"""
Aksara AI Orchestrator  (v0.5.37)

Executes an ``ExecutionPlan`` by running each step in order, collecting
outputs from the existing analyzers, and assembling a unified
``OrchestrationResult``.

The orchestrator is the *only* module that calls analyzers directly.
It bridges the execution plan with the concrete implementations in
``debugger.py``, ``architecture_review.py``, and ``performance_analyzer.py``.

Usage::

    from aksara.ai.orchestrator import execute_plan
    result = execute_plan(plan)

Safety:
    The orchestrator NEVER modifies code, database, or files.  It only
    orchestrates read-only analysis pipelines.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aksara.ai.execution_planner import (
    STEP_ANALYZE_ROUTE,
    STEP_BUILD_PROJECT_GRAPH,
    STEP_EXPLAIN_SCHEMA,
    STEP_RUN_ARCHITECTURE_REVIEW,
    STEP_RUN_DEBUGGER,
    STEP_RUN_DIAGNOSTICS,
    STEP_RUN_PERFORMANCE_ANALYSIS,
    ExecutionPlan,
)

logger = logging.getLogger("aksara.ai.orchestrator")


# ─── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    """Result from a single pipeline step."""

    step: str
    ok: bool = True
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    elapsed_ms: float = 0.0


@dataclass
class OrchestrationResult:
    """Unified result from the full orchestration pipeline.

    Attributes
    ----------
    ok : bool
        True if at least one step succeeded.
    intent : str
        The intent that drove this orchestration.
    step_results : list[StepResult]
        Individual step outcomes.
    report : dict
        Assembled unified report with sections from each analyzer.
    summary : str
        Human-readable summary.
    elapsed_ms : float
        Total wall-clock time.
    generated_at : str
        ISO timestamp.
    """

    ok: bool = True
    intent: str = "unknown"
    step_results: List[StepResult] = field(default_factory=list)
    report: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    elapsed_ms: float = 0.0
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "intent": self.intent,
            "step_results": [
                {"step": s.step, "ok": s.ok, "error": s.error, "elapsed_ms": s.elapsed_ms}
                for s in self.step_results
            ],
            "report": self.report,
            "summary": self.summary,
            "elapsed_ms": self.elapsed_ms,
            "generated_at": self.generated_at,
        }

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "intent": self.intent,
            "summary": self.summary,
            "steps_ok": sum(1 for s in self.step_results if s.ok),
            "steps_total": len(self.step_results),
            "elapsed_ms": self.elapsed_ms,
            "generated_at": self.generated_at,
        }


# ─── Step Executors ──────────────────────────────────────────────────────────

def _exec_build_project_graph(ctx: Dict[str, Any]) -> StepResult:
    """Build the Project Context Graph."""
    t0 = time.monotonic()
    try:
        from aksara.ai.project_graph import build_project_graph
        graph = build_project_graph(rebuild=True)
        return StepResult(
            step=STEP_BUILD_PROJECT_GRAPH,
            ok=True,
            data={"graph_summary": graph.to_summary_dict()},
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
        )
    except Exception as exc:
        logger.warning("orchestrator: build_project_graph failed: %s", exc)
        return StepResult(
            step=STEP_BUILD_PROJECT_GRAPH,
            ok=False,
            error=str(exc),
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
        )


def _exec_run_architecture_review(ctx: Dict[str, Any]) -> StepResult:
    """Run the Architecture Review analyzer."""
    t0 = time.monotonic()
    try:
        from aksara.ai.architecture_review import run_architecture_review
        report = run_architecture_review()
        return StepResult(
            step=STEP_RUN_ARCHITECTURE_REVIEW,
            ok=report.ok,
            data={"architecture_report": report.to_summary_dict()},
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
        )
    except Exception as exc:
        logger.warning("orchestrator: architecture_review failed: %s", exc)
        return StepResult(
            step=STEP_RUN_ARCHITECTURE_REVIEW,
            ok=False,
            error=str(exc),
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
        )


def _exec_run_performance_analysis(ctx: Dict[str, Any]) -> StepResult:
    """Run the Performance Analyzer."""
    t0 = time.monotonic()
    try:
        from aksara.ai.performance_analyzer import run_performance_analysis
        report = run_performance_analysis()
        return StepResult(
            step=STEP_RUN_PERFORMANCE_ANALYSIS,
            ok=report.ok,
            data={"performance_report": report.to_summary_dict()},
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
        )
    except Exception as exc:
        logger.warning("orchestrator: performance_analysis failed: %s", exc)
        return StepResult(
            step=STEP_RUN_PERFORMANCE_ANALYSIS,
            ok=False,
            error=str(exc),
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
        )


def _exec_run_debugger(ctx: Dict[str, Any]) -> StepResult:
    """Run the AI Debugger."""
    t0 = time.monotonic()
    try:
        from aksara.ai.debugger import run_debugger
        query = ctx.get("route") or ctx.get("model") or None
        report = run_debugger(query=query)
        return StepResult(
            step=STEP_RUN_DEBUGGER,
            ok=report.ok,
            data={"debug_report": report.to_summary_dict()},
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
        )
    except Exception as exc:
        logger.warning("orchestrator: debugger failed: %s", exc)
        return StepResult(
            step=STEP_RUN_DEBUGGER,
            ok=False,
            error=str(exc),
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
        )


def _exec_run_diagnostics(ctx: Dict[str, Any]) -> StepResult:
    """Collect current diagnostics from the cached report."""
    t0 = time.monotonic()
    try:
        from aksara.ai.project_graph import build_project_graph
        graph = build_project_graph()
        diag_count = graph.metadata.diagnostic_count
        gap_count = graph.metadata.gap_count
        return StepResult(
            step=STEP_RUN_DIAGNOSTICS,
            ok=True,
            data={
                "diagnostic_count": diag_count,
                "gap_count": gap_count,
                "diagnostics": [
                    {"code": d.code, "severity": d.severity, "message": d.message}
                    for d in graph.diagnostics[:20]
                ],
            },
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
        )
    except Exception as exc:
        logger.warning("orchestrator: diagnostics failed: %s", exc)
        return StepResult(
            step=STEP_RUN_DIAGNOSTICS,
            ok=False,
            error=str(exc),
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
        )


def _exec_explain_schema(ctx: Dict[str, Any]) -> StepResult:
    """Explain schema / models from the Project Graph."""
    t0 = time.monotonic()
    try:
        from aksara.ai.project_graph import build_project_graph
        graph = build_project_graph()
        model_name = ctx.get("model")
        models_data = []
        for m in graph.models:
            if model_name and m.name.lower() != model_name.lower():
                continue
            models_data.append({
                "name": m.name,
                "table": m.table,
                "fields": [f.get("name", "") for f in m.fields] if isinstance(m.fields, list) else [],
                "relations": m.relations,
            })
        return StepResult(
            step=STEP_EXPLAIN_SCHEMA,
            ok=True,
            data={"models": models_data, "model_count": len(models_data)},
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
        )
    except Exception as exc:
        logger.warning("orchestrator: explain_schema failed: %s", exc)
        return StepResult(
            step=STEP_EXPLAIN_SCHEMA,
            ok=False,
            error=str(exc),
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
        )


def _exec_analyze_route(ctx: Dict[str, Any]) -> StepResult:
    """Analyze a specific route from the Project Graph."""
    t0 = time.monotonic()
    try:
        from aksara.ai.project_graph import build_project_graph
        graph = build_project_graph()
        target_path = ctx.get("route", "")
        routes_data = []
        for r in graph.routes:
            if target_path and target_path not in r.path:
                continue
            routes_data.append({
                "method": r.method,
                "path": r.path,
                "handler": r.handler,
                "linked_models": r.linked_models,
                "linked_queries": r.linked_queries,
            })
        return StepResult(
            step=STEP_ANALYZE_ROUTE,
            ok=True,
            data={"routes": routes_data, "route_count": len(routes_data)},
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
        )
    except Exception as exc:
        logger.warning("orchestrator: analyze_route failed: %s", exc)
        return StepResult(
            step=STEP_ANALYZE_ROUTE,
            ok=False,
            error=str(exc),
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
        )


# ─── Step Dispatcher ─────────────────────────────────────────────────────────

_STEP_EXECUTORS = {
    STEP_BUILD_PROJECT_GRAPH: _exec_build_project_graph,
    STEP_RUN_ARCHITECTURE_REVIEW: _exec_run_architecture_review,
    STEP_RUN_PERFORMANCE_ANALYSIS: _exec_run_performance_analysis,
    STEP_RUN_DEBUGGER: _exec_run_debugger,
    STEP_RUN_DIAGNOSTICS: _exec_run_diagnostics,
    STEP_EXPLAIN_SCHEMA: _exec_explain_schema,
    STEP_ANALYZE_ROUTE: _exec_analyze_route,
}


# ─── Report Assembly ─────────────────────────────────────────────────────────

def _assemble_report(step_results: List[StepResult]) -> Dict[str, Any]:
    """Merge step data into a unified report dict."""
    report: Dict[str, Any] = {}
    for sr in step_results:
        if sr.ok and sr.data:
            report.update(sr.data)
    return report


def _build_summary(intent: str, step_results: List[StepResult]) -> str:
    """Build a human-readable summary from step results."""
    ok_count = sum(1 for s in step_results if s.ok)
    total = len(step_results)
    parts: List[str] = []

    parts.append(f"Orchestration for '{intent}': {ok_count}/{total} steps succeeded.")

    for sr in step_results:
        if not sr.ok:
            parts.append(f"  - {sr.step} failed: {sr.error}")

    # Add key metrics from architecture review
    for sr in step_results:
        if sr.step == STEP_RUN_ARCHITECTURE_REVIEW and sr.ok:
            arch = sr.data.get("architecture_report", {})
            grade = arch.get("grade", "?")
            score = arch.get("score", "?")
            parts.append(f"  Architecture Score: {score} ({grade})")

    # Add key metrics from performance analysis
    for sr in step_results:
        if sr.step == STEP_RUN_PERFORMANCE_ANALYSIS and sr.ok:
            perf = sr.data.get("performance_report", {})
            grade = perf.get("grade", "?")
            score = perf.get("score", "?")
            issues = perf.get("issue_count", 0)
            parts.append(f"  Performance Score: {score} ({grade}), {issues} issues")

    # Add debug summary
    for sr in step_results:
        if sr.step == STEP_RUN_DEBUGGER and sr.ok:
            debug = sr.data.get("debug_report", {})
            rc_count = debug.get("root_cause_count", 0)
            parts.append(f"  Root Causes: {rc_count}")

    return "\n".join(parts)


# ─── Public API ──────────────────────────────────────────────────────────────

def execute_plan(plan: ExecutionPlan) -> OrchestrationResult:
    """Execute an ``ExecutionPlan`` and return a unified result.

    Parameters
    ----------
    plan : ExecutionPlan
        The plan produced by ``build_execution_plan``.

    Returns
    -------
    OrchestrationResult
    """
    t0 = time.monotonic()
    now = datetime.now(timezone.utc).isoformat()

    step_results: List[StepResult] = []

    for step_name in plan.steps:
        executor = _STEP_EXECUTORS.get(step_name)
        if executor is None:
            step_results.append(StepResult(
                step=step_name,
                ok=False,
                error=f"Unknown step: {step_name}",
            ))
            continue
        sr = executor(plan.context)
        step_results.append(sr)

    any_ok = any(sr.ok for sr in step_results) if step_results else False
    report = _assemble_report(step_results)
    summary = _build_summary(plan.intent, step_results)

    elapsed = round((time.monotonic() - t0) * 1000, 1)

    return OrchestrationResult(
        ok=any_ok,
        intent=plan.intent,
        step_results=step_results,
        report=report,
        summary=summary,
        elapsed_ms=elapsed,
        generated_at=now,
    )
