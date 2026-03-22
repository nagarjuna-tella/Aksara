"""
Daily Briefing Engine  (v0.5.40)

Auto-generated system health summary that answers:
"What's going on in my system?"

Aggregates signals from the project graph, performance analyser,
architecture review, debugger, and recent investigations into a
single, human-readable briefing.

Usage::

    from aksara.ai.daily_briefing import generate_daily_briefing, DailyBriefing

    briefing = generate_daily_briefing()
    print(briefing.summary)
    print(briefing.performance_score)

v0.5.40: New module — Daily Briefing Engine
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger("aksara.ai.daily_briefing")

# ─── Data Models ──────────────────────────────────────────────────────────────


@dataclass
class DailyBriefing:
    """Aggregated system health briefing.

    Attributes:
        summary: Human-readable one-paragraph summary.
        performance_score: Performance score 0–100 (or -1 if unavailable).
        architecture_score: Architecture score 0–100 (or -1 if unavailable).
        issues: List of notable issue descriptions.
        recommendations: Actionable next-step recommendations.
        debug_signals: Key debug signals detected.
        recent_investigations: Summary of recent investigation sessions.
        elapsed_ms: Time taken to generate the briefing.
        generated_at: ISO-8601 timestamp of generation.
    """

    summary: str = ""
    performance_score: float = -1.0
    architecture_score: float = -1.0
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    debug_signals: List[str] = field(default_factory=list)
    recent_investigations: List[Dict[str, Any]] = field(default_factory=list)
    elapsed_ms: float = 0.0
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        return {
            "summary": self.summary,
            "performance_score": self.performance_score,
            "architecture_score": self.architecture_score,
            "issues": self.issues,
            "recommendations": self.recommendations,
            "debug_signals": self.debug_signals,
            "recent_investigations": self.recent_investigations,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "generated_at": self.generated_at,
        }

    def to_summary_dict(self) -> Dict[str, Any]:
        """Compact summary for the UI card."""
        return {
            "summary": self.summary,
            "performance_score": self.performance_score,
            "architecture_score": self.architecture_score,
            "issue_count": len(self.issues),
            "recommendation_count": len(self.recommendations),
            "generated_at": self.generated_at,
        }


# ─── Grade Helpers ────────────────────────────────────────────────────────────


def _score_to_grade(score: float) -> str:
    """Convert a 0–100 score to a letter grade."""
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


# ─── Section Collectors ──────────────────────────────────────────────────────


def _collect_project_graph() -> Dict[str, Any]:
    """Gather project-graph metadata (model/route counts)."""
    try:
        from aksara.ai.project_graph import build_project_graph

        graph = build_project_graph(rebuild=False)
        return graph.to_summary_dict()
    except Exception as exc:
        logger.debug("Project graph unavailable: %s", exc)
        return {}


def _collect_performance() -> Dict[str, Any]:
    """Run lightweight performance analysis."""
    try:
        from aksara.ai.performance_analyzer import run_performance_analysis

        report = run_performance_analysis()
        return report.to_summary_dict()
    except Exception as exc:
        logger.debug("Performance analysis unavailable: %s", exc)
        return {}


def _collect_architecture() -> Dict[str, Any]:
    """Run lightweight architecture review."""
    try:
        from aksara.ai.architecture_review import run_architecture_review

        report = run_architecture_review()
        return report.to_summary_dict()
    except Exception as exc:
        logger.debug("Architecture review unavailable: %s", exc)
        return {}


def _collect_debug() -> Dict[str, Any]:
    """Run debugger for signal detection."""
    try:
        from aksara.ai.debugger import run_debugger

        report = run_debugger(query="system health check")
        return report.to_summary_dict()
    except Exception as exc:
        logger.debug("Debug analysis unavailable: %s", exc)
        return {}


def _collect_recent_investigations() -> List[Dict[str, Any]]:
    """Get summaries of recent investigation sessions."""
    try:
        from aksara.ai.session_store import list_sessions

        sessions = list_sessions()
        return [s.to_summary_dict() for s in sessions[:5]]
    except Exception as exc:
        logger.debug("Session store unavailable: %s", exc)
        return []


# ─── Summary Builder ─────────────────────────────────────────────────────────


def _build_summary(
    perf_score: float,
    arch_score: float,
    issues: List[str],
    graph_info: Dict[str, Any],
) -> str:
    """Compose a human-readable one-paragraph summary."""
    parts: List[str] = []

    counts = graph_info.get("counts", {})
    models = counts.get("models", 0)
    routes = counts.get("routes", 0)
    if models or routes:
        parts.append(f"Your project has {models} models and {routes} routes.")

    if perf_score >= 0:
        p_grade = _score_to_grade(perf_score)
        parts.append(f"Performance: {perf_score:.0f}/100 ({p_grade}).")
    if arch_score >= 0:
        a_grade = _score_to_grade(arch_score)
        parts.append(f"Architecture: {arch_score:.0f}/100 ({a_grade}).")

    if issues:
        parts.append(f"{len(issues)} issue(s) detected.")
    else:
        parts.append("No critical issues detected.")

    return " ".join(parts) if parts else "No data available for briefing."


def _build_recommendations(
    perf_score: float,
    arch_score: float,
    issues: List[str],
) -> List[str]:
    """Generate actionable recommendations based on scores and issues."""
    recs: List[str] = []
    if 0 <= perf_score < 70:
        recs.append("Run a performance investigation to identify bottlenecks.")
    if 0 <= arch_score < 70:
        recs.append("Run an architecture review to reduce coupling.")
    if issues:
        recs.append("Address the detected issues to improve system health.")
    if not recs:
        recs.append("System looks healthy. Keep monitoring with periodic briefings.")
    return recs


# ─── Public API ──────────────────────────────────────────────────────────────


def generate_daily_briefing() -> DailyBriefing:
    """Generate a full daily briefing by aggregating all analysis signals.

    This is a synchronous function that collects data from:
    - Project graph (model/route counts)
    - Performance analyser (score + issues)
    - Architecture review (score + findings)
    - Debugger (root-cause signals)
    - Recent investigation sessions

    Returns:
        A :class:`DailyBriefing` with scores, issues, and recommendations.

    Example::

        briefing = generate_daily_briefing()
        print(briefing.summary)
        print(f"Performance: {briefing.performance_score}")
    """
    from datetime import datetime, timezone

    t0 = time.monotonic()

    # Collect signals
    graph_info = _collect_project_graph()
    perf_info = _collect_performance()
    arch_info = _collect_architecture()
    debug_info = _collect_debug()
    recent = _collect_recent_investigations()

    # Extract scores
    perf_score = perf_info.get("score", -1.0)
    arch_score = arch_info.get("score", -1.0)
    if isinstance(perf_score, (int, float)):
        perf_score = float(perf_score)
    else:
        perf_score = -1.0
    if isinstance(arch_score, (int, float)):
        arch_score = float(arch_score)
    else:
        arch_score = -1.0

    # Gather issues
    issues: List[str] = []
    for ti in perf_info.get("top_issues", []):
        title = ti.get("title", "") if isinstance(ti, dict) else str(ti)
        if title:
            issues.append(f"Performance: {title}")
    for fi in arch_info.get("findings", arch_info.get("top_findings", [])):
        title = fi.get("title", "") if isinstance(fi, dict) else str(fi)
        if title:
            issues.append(f"Architecture: {title}")

    # Gather debug signals
    debug_signals: List[str] = []
    for rc in debug_info.get("top_root_causes", debug_info.get("root_causes", [])):
        title = rc.get("title", "") if isinstance(rc, dict) else str(rc)
        if title:
            debug_signals.append(title)

    # Build summary and recommendations
    summary = _build_summary(perf_score, arch_score, issues, graph_info)
    recommendations = _build_recommendations(perf_score, arch_score, issues)

    elapsed = (time.monotonic() - t0) * 1000

    return DailyBriefing(
        summary=summary,
        performance_score=perf_score,
        architecture_score=arch_score,
        issues=issues,
        recommendations=recommendations,
        debug_signals=debug_signals,
        recent_investigations=recent,
        elapsed_ms=elapsed,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
