"""
Aksara AI Architecture Review  (v0.5.34)

Automated architectural analysis pipeline that reads the Project Context
Graph to identify anti-patterns, coupling risks, schema design issues,
API design problems, migration risks, and performance concerns — then
computes a health score and suggests improvements.

Usage::

    from aksara.ai.architecture_review import run_architecture_review

    report = run_architecture_review()
    print(f"Score: {report.score} ({report.grade})")

Pipeline steps:
    1. Load Project Graph  (``build_project_graph``)
    2. Compute metrics     (counts, averages, coupling score)
    3. Detect coupling     (route-model, query-route, model hotspots)
    4. Schema design       (large models, missing indexes, many relations)
    5. API design          (route explosion, deep nesting)
    6. Migration risks     (churn, recent schema events)
    7. Performance risks   (slow queries, diagnostic warnings)
    8. Score & grade       (penalty-based scoring)
    9. Generate suggestions

Safety:
    The review NEVER modifies code, database, or files.  It only
    returns analysis, findings, and suggestions.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aksara.ai.architecture_review")

# ─── Data Models ─────────────────────────────────────────────────────────────


@dataclass
class ArchitectureMetrics:
    """Computed metrics from the Project Graph."""

    model_count: int = 0
    route_count: int = 0
    query_count: int = 0
    migration_count: int = 0
    diagnostic_count: int = 0
    avg_models_per_route: float = 0.0
    avg_queries_per_route: float = 0.0
    coupling_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArchitectureFinding:
    """A single architectural issue detected during the review."""

    id: str
    severity: str  # "critical", "error", "warning", "info"
    title: str
    description: str
    related_nodes: List[str] = field(default_factory=list)
    category: str = "general"  # coupling, complexity, performance, schema_design, api_design, migration_risk, security

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArchitectureSuggestion:
    """A refactoring or improvement suggestion."""

    suggestion_id: str
    title: str
    description: str
    impact: str = "medium"  # "high", "medium", "low"
    related_findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArchitectureReport:
    """Complete output of the AI Architecture Review pipeline."""

    score: int = 100
    grade: str = "A"
    findings: List[ArchitectureFinding] = field(default_factory=list)
    suggestions: List[ArchitectureSuggestion] = field(default_factory=list)
    metrics: ArchitectureMetrics = field(default_factory=ArchitectureMetrics)
    generated_at: str = ""
    elapsed_ms: float = 0.0
    ok: bool = True

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def suggestion_count(self) -> int:
        return len(self.suggestions)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["finding_count"] = self.finding_count
        d["suggestion_count"] = self.suggestion_count
        return d

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "score": self.score,
            "grade": self.grade,
            "finding_count": self.finding_count,
            "suggestion_count": self.suggestion_count,
            "top_findings": [
                {"title": f.title, "severity": f.severity, "category": f.category}
                for f in self.findings[:5]
            ],
            "top_suggestions": [
                {"title": s.title, "impact": s.impact}
                for s in self.suggestions[:5]
            ],
            "metrics": self.metrics.to_dict(),
            "elapsed_ms": self.elapsed_ms,
            "generated_at": self.generated_at,
        }


# ─── Penalty Table ───────────────────────────────────────────────────────────

_PENALTY = {
    "high_coupling_route_model": 10,
    "high_coupling_route_queries": 10,
    "model_hotspot": 5,
    "large_model": 5,
    "missing_index": 10,
    "many_relations": 5,
    "route_explosion": 10,
    "deep_nesting": 5,
    "migration_churn": 5,
    "recent_migration_event": 5,
    "slow_query": 15,
    "performance_diagnostic": 10,
    "security_issue": 10,
}

# ─── Grade Map ───────────────────────────────────────────────────────────────


def _score_to_grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _elapsed(t0: float) -> float:
    return round((time.monotonic() - t0) * 1000, 2)


_FINDING_COUNTER = 0


def _next_finding_id() -> str:
    global _FINDING_COUNTER
    _FINDING_COUNTER += 1
    return f"ARCH-{_FINDING_COUNTER:04d}"


_SUGGESTION_COUNTER = 0


def _next_suggestion_id() -> str:
    global _SUGGESTION_COUNTER
    _SUGGESTION_COUNTER += 1
    return f"SUG-{_SUGGESTION_COUNTER:04d}"


def _reset_counters() -> None:
    global _FINDING_COUNTER, _SUGGESTION_COUNTER
    _FINDING_COUNTER = 0
    _SUGGESTION_COUNTER = 0


# ─── Main Entry Point ───────────────────────────────────────────────────────


def run_architecture_review(
    *,
    app: Any = None,
) -> ArchitectureReport:
    """Run the full AI Architecture Review pipeline.

    Parameters
    ----------
    app : Any, optional
        FastAPI app instance (passed to ``build_project_graph``).

    Returns
    -------
    ArchitectureReport
        Structured review with score, grade, findings, suggestions,
        and computed metrics.
    """
    t0 = time.monotonic()
    now = datetime.now(timezone.utc).isoformat()
    _reset_counters()

    # ── Step 1: Load Project Graph ────────────────────────────────────────
    try:
        from aksara.ai.project_graph import build_project_graph
        graph = build_project_graph(app=app)
    except Exception as exc:
        logger.warning("architecture_review: could not load project graph: %s", exc)
        return ArchitectureReport(
            ok=False, score=0, grade="F",
            generated_at=now,
            elapsed_ms=_elapsed(t0),
        )

    # ── Step 2: Compute Metrics ───────────────────────────────────────────
    metrics = _compute_metrics(graph)

    # ── Step 3–7: Detect Findings ─────────────────────────────────────────
    findings: List[ArchitectureFinding] = []
    findings.extend(_detect_coupling(graph, metrics))
    findings.extend(_detect_schema_issues(graph))
    findings.extend(_detect_api_issues(graph))
    findings.extend(_detect_migration_risks(graph))
    findings.extend(_detect_performance_risks(graph))

    # ── Step 8: Score & Grade ─────────────────────────────────────────────
    score = _compute_score(findings)
    grade = _score_to_grade(score)

    # ── Step 9: Generate Suggestions ──────────────────────────────────────
    suggestions = _generate_suggestions(findings, metrics)

    return ArchitectureReport(
        ok=True,
        score=score,
        grade=grade,
        findings=findings,
        suggestions=suggestions,
        metrics=metrics,
        generated_at=now,
        elapsed_ms=_elapsed(t0),
    )


# ─── Step 2: Compute Metrics ────────────────────────────────────────────────


def _compute_metrics(graph) -> ArchitectureMetrics:
    """Calculate metrics from the project graph."""
    model_count = len(graph.models)
    route_count = len(graph.routes)
    query_count = len(graph.queries)
    migration_count = len(graph.migrations)
    diagnostic_count = len(graph.diagnostics)

    # Average models per route
    if route_count > 0:
        total_models_in_routes = sum(len(r.models) for r in graph.routes)
        avg_models_per_route = round(total_models_in_routes / route_count, 2)
    else:
        avg_models_per_route = 0.0

    # Average queries per route
    if route_count > 0:
        total_queries_in_routes = sum(len(r.queries) for r in graph.routes)
        avg_queries_per_route = round(total_queries_in_routes / route_count, 2)
    else:
        avg_queries_per_route = 0.0

    # Coupling score: avg(models_per_route) + avg(queries_per_route) normalised
    coupling_score = round(
        min(1.0, (avg_models_per_route / 10.0 + avg_queries_per_route / 20.0)),
        2,
    )

    return ArchitectureMetrics(
        model_count=model_count,
        route_count=route_count,
        query_count=query_count,
        migration_count=migration_count,
        diagnostic_count=diagnostic_count,
        avg_models_per_route=avg_models_per_route,
        avg_queries_per_route=avg_queries_per_route,
        coupling_score=coupling_score,
    )


# ─── Step 3: Detect Coupling ────────────────────────────────────────────────


def _detect_coupling(graph, metrics: ArchitectureMetrics) -> List[ArchitectureFinding]:
    """Detect coupling anti-patterns."""
    findings: List[ArchitectureFinding] = []

    # 3a. Routes using too many models (> 3)
    for route in graph.routes:
        if len(route.models) > 3:
            findings.append(ArchitectureFinding(
                id=_next_finding_id(),
                severity="warning",
                title="High route-to-model coupling",
                description=(
                    f"Route {route.method} {route.path} references "
                    f"{len(route.models)} models. Consider introducing a "
                    f"service layer to reduce direct coupling."
                ),
                related_nodes=[route.path] + route.models,
                category="coupling",
            ))

    # 3b. Routes with too many queries (> 5)
    for route in graph.routes:
        if len(route.queries) > 5:
            findings.append(ArchitectureFinding(
                id=_next_finding_id(),
                severity="warning",
                title="Route performing excessive database work",
                description=(
                    f"Route {route.method} {route.path} uses "
                    f"{len(route.queries)} queries. Consider optimising "
                    f"with eager loading or caching."
                ),
                related_nodes=[route.path] + route.queries,
                category="coupling",
            ))

    # 3c. Model referenced by too many routes (> 10)
    model_route_count: Dict[str, List[str]] = {}
    for route in graph.routes:
        for model_name in route.models:
            model_route_count.setdefault(model_name, []).append(route.path)

    for model_name, routes in model_route_count.items():
        if len(routes) > 10:
            findings.append(ArchitectureFinding(
                id=_next_finding_id(),
                severity="warning",
                title="Model acting as shared dependency hotspot",
                description=(
                    f"Model '{model_name}' is referenced by "
                    f"{len(routes)} routes. This may create a bottleneck."
                ),
                related_nodes=[model_name] + routes[:5],
                category="coupling",
            ))

    return findings


# ─── Step 4: Schema Design Issues ───────────────────────────────────────────


def _detect_schema_issues(graph) -> List[ArchitectureFinding]:
    """Detect schema design anti-patterns."""
    findings: List[ArchitectureFinding] = []

    for model in graph.models:
        # 4a. Large models (> 20 fields)
        if len(model.fields) > 20:
            findings.append(ArchitectureFinding(
                id=_next_finding_id(),
                severity="warning",
                title="Model may be overloaded",
                description=(
                    f"Model '{model.name}' has {len(model.fields)} fields. "
                    f"Consider splitting into smaller, focused models."
                ),
                related_nodes=[model.name],
                category="schema_design",
            ))

        # 4b. Many relations (> 8)
        if len(model.relations) > 8:
            findings.append(ArchitectureFinding(
                id=_next_finding_id(),
                severity="warning",
                title="Complex relational graph",
                description=(
                    f"Model '{model.name}' has {len(model.relations)} "
                    f"relations. High relational complexity may hinder "
                    f"maintainability."
                ),
                related_nodes=[model.name] + model.relations[:5],
                category="schema_design",
            ))

    # 4c. Missing indexes (from diagnostics)
    for diag in graph.diagnostics:
        msg_lower = (diag.message or "").lower()
        code_lower = (diag.code or "").lower()
        if "index" in msg_lower or "index" in code_lower:
            findings.append(ArchitectureFinding(
                id=_next_finding_id(),
                severity="error",
                title="Schema lacks indexes on frequently queried columns",
                description=diag.message,
                related_nodes=diag.related_models + diag.related_queries,
                category="schema_design",
            ))

    return findings


# ─── Step 5: API Design Issues ──────────────────────────────────────────────


def _detect_api_issues(graph) -> List[ArchitectureFinding]:
    """Detect API surface anti-patterns."""
    findings: List[ArchitectureFinding] = []

    # 5a. Route explosion (> 100 routes)
    if len(graph.routes) > 100:
        findings.append(ArchitectureFinding(
            id=_next_finding_id(),
            severity="warning",
            title="API surface becoming large",
            description=(
                f"Application has {len(graph.routes)} routes. "
                f"Consider grouping related endpoints or versioning."
            ),
            related_nodes=[],
            category="api_design",
        ))

    # 5b. Deep path nesting (> 4 segments)
    for route in graph.routes:
        segments = [s for s in route.path.strip("/").split("/") if s]
        if len(segments) > 4:
            findings.append(ArchitectureFinding(
                id=_next_finding_id(),
                severity="info",
                title="Deep route nesting",
                description=(
                    f"Route {route.method} {route.path} has "
                    f"{len(segments)} path segments. Deep nesting may "
                    f"indicate poor resource modeling."
                ),
                related_nodes=[route.path],
                category="api_design",
            ))

    return findings


# ─── Step 6: Migration Risks ────────────────────────────────────────────────


def _detect_migration_risks(graph) -> List[ArchitectureFinding]:
    """Detect migration-related risks."""
    findings: List[ArchitectureFinding] = []

    # 6a. Migration churn: many migrations touching same model (> 10)
    model_migration_count: Dict[str, int] = {}
    for mig in graph.migrations:
        for model_name in mig.models:
            model_migration_count[model_name] = model_migration_count.get(model_name, 0) + 1

    for model_name, count in model_migration_count.items():
        if count > 10:
            findings.append(ArchitectureFinding(
                id=_next_finding_id(),
                severity="warning",
                title="Frequent schema churn",
                description=(
                    f"Model '{model_name}' has {count} migrations. "
                    f"Frequent schema changes affect stability."
                ),
                related_nodes=[model_name],
                category="migration_risk",
            ))

    # 6b. Recent migration events from the event timeline
    migration_events = [
        ev for ev in graph.events
        if ev.get("kind", "").lower() in ("migration", "schema_change", "migrate")
    ]
    if migration_events:
        findings.append(ArchitectureFinding(
            id=_next_finding_id(),
            severity="info",
            title="Recent schema change detected",
            description=(
                f"{len(migration_events)} recent migration event(s) "
                f"in the timeline. Recent schema changes may affect stability."
            ),
            related_nodes=[ev.get("message", "")[:60] for ev in migration_events[:3]],
            category="migration_risk",
        ))

    return findings


# ─── Step 7: Performance Risks ──────────────────────────────────────────────


def _detect_performance_risks(graph) -> List[ArchitectureFinding]:
    """Detect performance-related risks."""
    findings: List[ArchitectureFinding] = []

    # 7a. Slow query events
    slow_events = [
        ev for ev in graph.events
        if "slow" in ev.get("kind", "").lower()
        or "slow" in ev.get("message", "").lower()
    ]
    if slow_events:
        findings.append(ArchitectureFinding(
            id=_next_finding_id(),
            severity="error",
            title="Slow query events detected",
            description=(
                f"{len(slow_events)} slow query event(s) in the timeline. "
                f"Database performance risks are present."
            ),
            related_nodes=[ev.get("message", "")[:60] for ev in slow_events[:3]],
            category="performance",
        ))

    # 7b. Performance-related diagnostics
    perf_diags = [
        d for d in graph.diagnostics
        if any(kw in (d.message or "").lower()
               for kw in ("slow", "performance", "timeout", "n+1", "prefetch"))
    ]
    if perf_diags:
        findings.append(ArchitectureFinding(
            id=_next_finding_id(),
            severity="warning",
            title="Performance diagnostics detected",
            description=(
                f"{len(perf_diags)} performance-related diagnostic(s). "
                f"Review query patterns and indexing strategy."
            ),
            related_nodes=[d.code for d in perf_diags[:5]],
            category="performance",
        ))

    # 7c. Security-related diagnostics
    sec_diags = [
        d for d in graph.diagnostics
        if any(kw in (d.message or "").lower()
               for kw in ("security", "permission", "auth", "csrf", "xss", "injection"))
    ]
    if sec_diags:
        findings.append(ArchitectureFinding(
            id=_next_finding_id(),
            severity="error",
            title="Security concerns detected",
            description=(
                f"{len(sec_diags)} security-related diagnostic(s). "
                f"Review authentication and authorisation patterns."
            ),
            related_nodes=[d.code for d in sec_diags[:5]],
            category="security",
        ))

    return findings


# ─── Step 8: Score Calculation ───────────────────────────────────────────────

_CATEGORY_PENALTY_KEY = {
    "coupling": {
        "High route-to-model coupling": "high_coupling_route_model",
        "Route performing excessive database work": "high_coupling_route_queries",
        "Model acting as shared dependency hotspot": "model_hotspot",
    },
    "schema_design": {
        "Model may be overloaded": "large_model",
        "Schema lacks indexes on frequently queried columns": "missing_index",
        "Complex relational graph": "many_relations",
    },
    "api_design": {
        "API surface becoming large": "route_explosion",
        "Deep route nesting": "deep_nesting",
    },
    "migration_risk": {
        "Frequent schema churn": "migration_churn",
        "Recent schema change detected": "recent_migration_event",
    },
    "performance": {
        "Slow query events detected": "slow_query",
        "Performance diagnostics detected": "performance_diagnostic",
    },
    "security": {
        "Security concerns detected": "security_issue",
    },
}


def _compute_score(findings: List[ArchitectureFinding]) -> int:
    """Compute architecture score starting from 100, applying penalties."""
    score = 100

    for finding in findings:
        cat_map = _CATEGORY_PENALTY_KEY.get(finding.category, {})
        penalty_key = cat_map.get(finding.title)
        if penalty_key:
            score -= _PENALTY.get(penalty_key, 5)
        else:
            # Default penalty based on severity
            if finding.severity == "critical":
                score -= 15
            elif finding.severity == "error":
                score -= 10
            elif finding.severity == "warning":
                score -= 5
            else:
                score -= 2

    return max(0, score)


# ─── Step 9: Generate Suggestions ───────────────────────────────────────────


def _generate_suggestions(
    findings: List[ArchitectureFinding],
    metrics: ArchitectureMetrics,
) -> List[ArchitectureSuggestion]:
    """Generate actionable improvement suggestions based on findings."""
    suggestions: List[ArchitectureSuggestion] = []
    seen_titles: set = set()

    for finding in findings:
        sugs = _suggestions_for_finding(finding)
        for title, desc, impact in sugs:
            if title in seen_titles:
                continue
            seen_titles.add(title)
            suggestions.append(ArchitectureSuggestion(
                suggestion_id=_next_suggestion_id(),
                title=title,
                description=desc,
                impact=impact,
                related_findings=[finding.id],
            ))

    # Sort by impact: high > medium > low
    impact_order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda s: impact_order.get(s.impact, 1))

    return suggestions


def _suggestions_for_finding(finding: ArchitectureFinding) -> List[tuple]:
    """Return (title, description, impact) tuples for a finding."""
    cat = finding.category
    title = finding.title

    if cat == "coupling":
        if "route-to-model" in title.lower():
            return [
                (
                    "Introduce service layer",
                    "Create service classes to mediate between routes and models, "
                    "reducing direct coupling and improving testability.",
                    "high",
                ),
            ]
        if "excessive database" in title.lower():
            return [
                (
                    "Optimise query patterns",
                    "Use eager loading (select_related/prefetch_related) or "
                    "caching to reduce per-request query count.",
                    "high",
                ),
            ]
        if "hotspot" in title.lower():
            return [
                (
                    "Decompose shared model",
                    "Consider splitting the heavily-referenced model into "
                    "focused sub-models or introducing a read model.",
                    "medium",
                ),
            ]

    if cat == "schema_design":
        if "overloaded" in title.lower():
            return [
                (
                    "Split model responsibilities",
                    "Extract related field groups into separate models "
                    "with clear single-responsibility boundaries.",
                    "medium",
                ),
            ]
        if "index" in title.lower():
            return [
                (
                    "Add missing database indexes",
                    "Create indexes on frequently queried columns "
                    "to improve query performance.",
                    "high",
                ),
            ]
        if "relational" in title.lower():
            return [
                (
                    "Simplify relational graph",
                    "Review whether all relations are necessary. "
                    "Consider denormalisation for read-heavy paths.",
                    "medium",
                ),
            ]

    if cat == "api_design":
        if "large" in title.lower():
            return [
                (
                    "Group or version API endpoints",
                    "Organise routes into versioned groups and consider "
                    "deprecating unused endpoints.",
                    "medium",
                ),
            ]
        if "nesting" in title.lower():
            return [
                (
                    "Flatten route hierarchy",
                    "Use flatter URL structures with query parameters "
                    "instead of deeply nested path segments.",
                    "low",
                ),
            ]

    if cat == "migration_risk":
        if "churn" in title.lower():
            return [
                (
                    "Stabilise schema design",
                    "Plan schema changes carefully, batch related changes, "
                    "and squash migrations when safe.",
                    "medium",
                ),
            ]
        if "recent" in title.lower():
            return [
                (
                    "Monitor post-migration stability",
                    "Watch for regressions after recent schema changes. "
                    "Run full test suite and check query performance.",
                    "low",
                ),
            ]

    if cat == "performance":
        if "slow" in title.lower():
            return [
                (
                    "Investigate slow queries",
                    "Profile the slow queries with EXPLAIN ANALYZE and "
                    "add indexes or rewrite as needed.",
                    "high",
                ),
            ]
        if "diagnostic" in title.lower():
            return [
                (
                    "Address performance diagnostics",
                    "Review flagged performance diagnostics and apply "
                    "recommended optimisations.",
                    "high",
                ),
            ]

    if cat == "security":
        return [
            (
                "Review security configuration",
                "Audit authentication, authorisation, and input validation "
                "patterns across the application.",
                "high",
            ),
        ]

    return []
