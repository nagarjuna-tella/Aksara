"""
Aksara AI Performance Analyzer  (v0.5.35)

Automated performance analysis pipeline that reads the Project Context
Graph, query inspector data, diagnostics, and event timeline to detect
slow queries, N+1 patterns, missing indexes, query explosions, heavy
joins, and route hotspots — then computes a performance score and
recommends improvements.

Usage::

    from aksara.ai.performance_analyzer import run_performance_analysis

    report = run_performance_analysis()
    print(f"Score: {report.score} ({report.grade})")

Pipeline steps:
    1.  Load Project Graph          (``build_project_graph``)
    2.  Collect query data          (queries, events, diagnostics)
    3.  Detect slow queries         (execution_time > 200 ms)
    4.  Detect N+1 patterns         (repeated param-only queries > 5)
    5.  Detect query explosions     (route with > 10 queries)
    6.  Detect missing indexes      (table-scan / WHERE-without-index diags)
    7.  Detect heavy joins          (JOIN count > 3)
    8.  Detect route hotspots       (routes appearing in slow-query logs)
    9.  Compute metrics             (totals, averages, max)
    10. Score & grade               (penalty-based scoring)

Safety:
    The analyzer NEVER modifies code, database, or files.  It only
    returns analysis, issues, and recommendations.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aksara.ai.performance_analyzer")

# ─── Data Models ─────────────────────────────────────────────────────────────


@dataclass
class PerformanceMetrics:
    """Computed performance metrics from the Project Graph."""

    total_routes: int = 0
    total_queries: int = 0
    slow_queries: int = 0
    n_plus_one_candidates: int = 0
    missing_indexes: int = 0
    avg_queries_per_route: float = 0.0
    max_queries_route: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceIssue:
    """A single performance issue detected during analysis."""

    issue_id: str
    severity: str  # "critical", "high", "medium", "low"
    title: str
    description: str
    route: Optional[str] = None
    model: Optional[str] = None
    query: Optional[str] = None
    category: str = "slow_query"
    # categories: slow_query, n_plus_one, missing_index, query_explosion,
    #             heavy_join, large_payload, route_hotspot

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceRecommendation:
    """A performance improvement recommendation."""

    recommendation_id: str
    title: str
    description: str
    impact: str = "medium"  # "high", "medium", "low"
    related_issue_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceReport:
    """Complete output of the AI Performance Analyzer pipeline."""

    score: int = 100
    grade: str = "A"
    issues: List[PerformanceIssue] = field(default_factory=list)
    recommendations: List[PerformanceRecommendation] = field(default_factory=list)
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    generated_at: str = ""
    elapsed_ms: float = 0.0
    ok: bool = True

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def recommendation_count(self) -> int:
        return len(self.recommendations)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["issue_count"] = self.issue_count
        d["recommendation_count"] = self.recommendation_count
        return d

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "score": self.score,
            "grade": self.grade,
            "issue_count": self.issue_count,
            "recommendation_count": self.recommendation_count,
            "top_issues": [
                {"title": i.title, "severity": i.severity, "category": i.category}
                for i in self.issues[:5]
            ],
            "top_recommendations": [
                {"title": r.title, "impact": r.impact}
                for r in self.recommendations[:5]
            ],
            "metrics": self.metrics.to_dict(),
            "elapsed_ms": self.elapsed_ms,
            "generated_at": self.generated_at,
        }


# ─── Penalty Table ───────────────────────────────────────────────────────────

_PENALTY: Dict[str, int] = {
    "slow_query": 10,
    "n_plus_one": 15,
    "missing_index": 10,
    "query_explosion": 10,
    "heavy_join": 5,
    "large_payload": 5,
    "route_hotspot": 10,
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


_ISSUE_COUNTER = 0


def _next_issue_id() -> str:
    global _ISSUE_COUNTER
    _ISSUE_COUNTER += 1
    return f"PERF-{_ISSUE_COUNTER:04d}"


_REC_COUNTER = 0


def _next_rec_id() -> str:
    global _REC_COUNTER
    _REC_COUNTER += 1
    return f"REC-{_REC_COUNTER:04d}"


def _reset_counters() -> None:
    global _ISSUE_COUNTER, _REC_COUNTER
    _ISSUE_COUNTER = 0
    _REC_COUNTER = 0


# ─── Query normalisation ────────────────────────────────────────────────────

_PARAM_RE = re.compile(r"=\s*(?:\?|%s|\$\d+|\d+|'[^']*')")


def _normalise_query(sql: str) -> str:
    """Normalise a SQL query by replacing parameter values with '?'."""
    return _PARAM_RE.sub("= ?", sql).strip()


_JOIN_RE = re.compile(r"\bJOIN\b", re.IGNORECASE)


def _count_joins(sql: str) -> int:
    """Count the number of JOINs in a SQL query."""
    return len(_JOIN_RE.findall(sql))


# ─── Main Entry Point ───────────────────────────────────────────────────────


def run_performance_analysis(
    *,
    app: Any = None,
) -> PerformanceReport:
    """Run the full AI Performance Analyzer pipeline.

    Parameters
    ----------
    app : Any, optional
        FastAPI app instance (passed to ``build_project_graph``).

    Returns
    -------
    PerformanceReport
        Structured report with score, grade, issues, recommendations,
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
        logger.warning("performance_analyzer: could not load project graph: %s", exc)
        return PerformanceReport(
            ok=False,
            score=0,
            grade="F",
            generated_at=now,
            elapsed_ms=_elapsed(t0),
        )

    # ── Step 2: Collect query data ────────────────────────────────────────
    query_data = _collect_query_data(graph)

    # ── Steps 3–8: Detect issues ──────────────────────────────────────────
    issues: List[PerformanceIssue] = []
    issues.extend(_detect_slow_queries(query_data, graph))
    issues.extend(_detect_n_plus_one(query_data, graph))
    issues.extend(_detect_query_explosions(graph))
    issues.extend(_detect_missing_indexes(graph))
    issues.extend(_detect_heavy_joins(query_data, graph))
    issues.extend(_detect_route_hotspots(query_data, graph))

    # ── Step 9: Compute metrics ───────────────────────────────────────────
    metrics = _compute_metrics(graph, issues, query_data)

    # ── Step 10: Score & grade ────────────────────────────────────────────
    score = _compute_score(issues)
    grade = _score_to_grade(score)

    # ── Generate recommendations ──────────────────────────────────────────
    recommendations = _generate_recommendations(issues, metrics)

    return PerformanceReport(
        ok=True,
        score=score,
        grade=grade,
        issues=issues,
        recommendations=recommendations,
        metrics=metrics,
        generated_at=now,
        elapsed_ms=_elapsed(t0),
    )


# ─── Step 2: Collect Query Data ─────────────────────────────────────────────


@dataclass
class _QueryRecord:
    """Internal record for a collected query."""

    sql: str = ""
    route: str = ""
    execution_time_ms: float = 0.0
    model: str = ""


def _collect_query_data(graph) -> List[_QueryRecord]:
    """Collect query data from the graph, events, and diagnostics."""
    records: List[_QueryRecord] = []

    # From graph queries
    for q in graph.queries:
        sql = getattr(q, "sql", "") or getattr(q, "query", "") or str(q)
        exec_time = getattr(q, "execution_time_ms", 0.0) or getattr(q, "duration_ms", 0.0) or 0.0
        route = getattr(q, "route", "") or ""
        model = getattr(q, "model", "") or ""
        records.append(_QueryRecord(sql=sql, route=route, execution_time_ms=exec_time, model=model))

    # From events (slow_query, query events)
    for ev in graph.events:
        kind = ev.get("kind", "").lower() if isinstance(ev, dict) else getattr(ev, "kind", "").lower()
        if "query" in kind or "slow" in kind:
            msg = ev.get("message", "") if isinstance(ev, dict) else getattr(ev, "message", "")
            exec_time = ev.get("duration_ms", 0.0) if isinstance(ev, dict) else getattr(ev, "duration_ms", 0.0)
            route = ev.get("route", "") if isinstance(ev, dict) else getattr(ev, "route", "")
            records.append(_QueryRecord(
                sql=msg,
                route=route,
                execution_time_ms=exec_time or 0.0,
                model="",
            ))

    return records


# ─── Step 3: Detect Slow Queries ────────────────────────────────────────────

_SLOW_QUERY_THRESHOLD_MS = 200.0


def _detect_slow_queries(
    query_data: List[_QueryRecord],
    graph,
) -> List[PerformanceIssue]:
    """Detect queries with execution time > 200ms."""
    issues: List[PerformanceIssue] = []

    for qr in query_data:
        if qr.execution_time_ms > _SLOW_QUERY_THRESHOLD_MS:
            issues.append(PerformanceIssue(
                issue_id=_next_issue_id(),
                severity="medium",
                title="Slow query detected",
                description=(
                    f"Query took {qr.execution_time_ms:.0f}ms "
                    f"(threshold: {_SLOW_QUERY_THRESHOLD_MS:.0f}ms). "
                    f"SQL: {qr.sql[:120]}"
                ),
                route=qr.route or None,
                model=qr.model or None,
                query=qr.sql[:200] if qr.sql else None,
                category="slow_query",
            ))

    # Also check diagnostics for slow-query indicators
    for diag in graph.diagnostics:
        msg = (diag.message or "").lower()
        if "slow" in msg and "query" in msg:
            issues.append(PerformanceIssue(
                issue_id=_next_issue_id(),
                severity="medium",
                title="Slow query flagged by diagnostics",
                description=diag.message,
                route=None,
                model=None,
                query=None,
                category="slow_query",
            ))

    return issues


# ─── Step 4: Detect N+1 Patterns ────────────────────────────────────────────

_N_PLUS_ONE_THRESHOLD = 5


def _detect_n_plus_one(
    query_data: List[_QueryRecord],
    graph,
) -> List[PerformanceIssue]:
    """Detect N+1 query patterns: repeated queries differing only in params."""
    issues: List[PerformanceIssue] = []

    # Group queries by normalised SQL + route
    grouped: Dict[str, List[_QueryRecord]] = {}
    for qr in query_data:
        if not qr.sql:
            continue
        key = (_normalise_query(qr.sql), qr.route)
        grouped.setdefault(str(key), []).append(qr)

    for key, records in grouped.items():
        if len(records) > _N_PLUS_ONE_THRESHOLD:
            sample = records[0]
            issues.append(PerformanceIssue(
                issue_id=_next_issue_id(),
                severity="high",
                title="N+1 query pattern detected",
                description=(
                    f"Query executed {len(records)} times with only "
                    f"parameter changes (threshold: {_N_PLUS_ONE_THRESHOLD}). "
                    f"Pattern: {_normalise_query(sample.sql)[:100]}"
                ),
                route=sample.route or None,
                model=sample.model or None,
                query=_normalise_query(sample.sql)[:200],
                category="n_plus_one",
            ))

    # Also check diagnostics for N+1 indicators
    for diag in graph.diagnostics:
        msg = (diag.message or "").lower()
        if "n+1" in msg or "n plus one" in msg or "prefetch" in msg:
            issues.append(PerformanceIssue(
                issue_id=_next_issue_id(),
                severity="high",
                title="N+1 pattern flagged by diagnostics",
                description=diag.message,
                route=None,
                model=None,
                query=None,
                category="n_plus_one",
            ))

    return issues


# ─── Step 5: Detect Query Explosions ────────────────────────────────────────

_QUERY_EXPLOSION_THRESHOLD = 10


def _detect_query_explosions(graph) -> List[PerformanceIssue]:
    """Detect routes executing more than 10 queries."""
    issues: List[PerformanceIssue] = []

    for route in graph.routes:
        query_count = len(route.queries)
        if query_count > _QUERY_EXPLOSION_THRESHOLD:
            issues.append(PerformanceIssue(
                issue_id=_next_issue_id(),
                severity="high",
                title="Query explosion on route",
                description=(
                    f"Route {route.method} {route.path} executes "
                    f"{query_count} queries (threshold: "
                    f"{_QUERY_EXPLOSION_THRESHOLD}). Consider batching "
                    f"or using eager loading."
                ),
                route=f"{route.method} {route.path}",
                model=None,
                query=None,
                category="query_explosion",
            ))

    return issues


# ─── Step 6: Detect Missing Indexes ─────────────────────────────────────────


def _detect_missing_indexes(graph) -> List[PerformanceIssue]:
    """Detect missing indexes from diagnostics and query patterns."""
    issues: List[PerformanceIssue] = []

    for diag in graph.diagnostics:
        msg = (diag.message or "").lower()
        code = (diag.code or "").lower()
        if ("index" in msg or "index" in code
                or "table scan" in msg or "seq scan" in msg
                or "without index" in msg):
            issues.append(PerformanceIssue(
                issue_id=_next_issue_id(),
                severity="high",
                title="Missing index detected",
                description=diag.message,
                route=None,
                model=diag.related_models[0] if diag.related_models else None,
                query=None,
                category="missing_index",
            ))

    return issues


# ─── Step 7: Detect Heavy Joins ─────────────────────────────────────────────

_HEAVY_JOIN_THRESHOLD = 3


def _detect_heavy_joins(
    query_data: List[_QueryRecord],
    graph,
) -> List[PerformanceIssue]:
    """Detect queries with more than 3 JOINs."""
    issues: List[PerformanceIssue] = []
    seen_sql: set = set()

    for qr in query_data:
        if not qr.sql:
            continue
        normalised = _normalise_query(qr.sql)
        if normalised in seen_sql:
            continue

        join_count = _count_joins(qr.sql)
        if join_count > _HEAVY_JOIN_THRESHOLD:
            seen_sql.add(normalised)
            issues.append(PerformanceIssue(
                issue_id=_next_issue_id(),
                severity="medium",
                title="Heavy join query detected",
                description=(
                    f"Query contains {join_count} JOINs "
                    f"(threshold: {_HEAVY_JOIN_THRESHOLD}). "
                    f"Consider denormalising or splitting."
                ),
                route=qr.route or None,
                model=qr.model or None,
                query=qr.sql[:200],
                category="heavy_join",
            ))

    return issues


# ─── Step 8: Detect Route Hotspots ──────────────────────────────────────────


def _detect_route_hotspots(
    query_data: List[_QueryRecord],
    graph,
) -> List[PerformanceIssue]:
    """Detect routes that repeatedly appear in slow query logs."""
    issues: List[PerformanceIssue] = []

    # Count slow queries per route
    route_slow_count: Dict[str, int] = {}
    for qr in query_data:
        if qr.execution_time_ms > _SLOW_QUERY_THRESHOLD_MS and qr.route:
            route_slow_count[qr.route] = route_slow_count.get(qr.route, 0) + 1

    for route_path, count in route_slow_count.items():
        if count >= 2:
            issues.append(PerformanceIssue(
                issue_id=_next_issue_id(),
                severity="high",
                title="Route hotspot detected",
                description=(
                    f"Route '{route_path}' is associated with "
                    f"{count} slow queries. This endpoint may be "
                    f"a performance bottleneck."
                ),
                route=route_path,
                model=None,
                query=None,
                category="route_hotspot",
            ))

    return issues


# ─── Step 9: Compute Metrics ────────────────────────────────────────────────


def _compute_metrics(
    graph,
    issues: List[PerformanceIssue],
    query_data: List[_QueryRecord],
) -> PerformanceMetrics:
    """Compute performance metrics from the graph and detected issues."""
    total_routes = len(graph.routes)
    total_queries = len(graph.queries)

    slow_queries = sum(1 for i in issues if i.category == "slow_query")
    n_plus_one_candidates = sum(1 for i in issues if i.category == "n_plus_one")
    missing_indexes = sum(1 for i in issues if i.category == "missing_index")

    # Average queries per route
    if total_routes > 0:
        total_q_per_route = sum(len(r.queries) for r in graph.routes)
        avg_queries_per_route = round(total_q_per_route / total_routes, 2)
    else:
        avg_queries_per_route = 0.0

    # Route with most queries
    max_queries_route: Optional[str] = None
    max_q = 0
    for route in graph.routes:
        q_count = len(route.queries)
        if q_count > max_q:
            max_q = q_count
            max_queries_route = f"{route.method} {route.path}"

    return PerformanceMetrics(
        total_routes=total_routes,
        total_queries=total_queries,
        slow_queries=slow_queries,
        n_plus_one_candidates=n_plus_one_candidates,
        missing_indexes=missing_indexes,
        avg_queries_per_route=avg_queries_per_route,
        max_queries_route=max_queries_route,
    )


# ─── Step 10: Score Calculation ──────────────────────────────────────────────


def _compute_score(issues: List[PerformanceIssue]) -> int:
    """Compute performance score starting from 100, applying penalties."""
    score = 100

    for issue in issues:
        penalty = _PENALTY.get(issue.category, 5)
        score -= penalty

    return max(0, score)


# ─── Recommendations ────────────────────────────────────────────────────────


def _generate_recommendations(
    issues: List[PerformanceIssue],
    metrics: PerformanceMetrics,
) -> List[PerformanceRecommendation]:
    """Generate actionable recommendations based on detected issues."""
    recommendations: List[PerformanceRecommendation] = []
    seen_titles: set = set()

    for issue in issues:
        recs = _recommendations_for_issue(issue)
        for title, desc, impact in recs:
            if title in seen_titles:
                continue
            seen_titles.add(title)
            recommendations.append(PerformanceRecommendation(
                recommendation_id=_next_rec_id(),
                title=title,
                description=desc,
                impact=impact,
                related_issue_ids=[issue.issue_id],
            ))

    # Sort by impact: high > medium > low
    impact_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda r: impact_order.get(r.impact, 1))

    return recommendations


def _recommendations_for_issue(issue: PerformanceIssue) -> List[tuple]:
    """Return (title, description, impact) tuples for an issue."""
    cat = issue.category

    if cat == "slow_query":
        return [(
            "Optimise slow queries",
            "Review execution plans and add indexes for slow queries. "
            "Consider query rewriting or caching for frequently-hit paths.",
            "high",
        )]
    if cat == "n_plus_one":
        return [(
            "Use eager loading to eliminate N+1 patterns",
            "Use select_related / prefetch_related or batch loading to "
            "fetch related data in a single query instead of N separate ones.",
            "high",
        )]
    if cat == "missing_index":
        model_hint = f" on {issue.model}" if issue.model else ""
        return [(
            f"Add missing database index{model_hint}",
            "Create indexes on columns used in WHERE, ORDER BY, and JOIN "
            "clauses to avoid full table scans.",
            "high",
        )]
    if cat == "query_explosion":
        return [(
            "Reduce per-request query count",
            "Batch related queries, use eager loading, or introduce "
            "caching to reduce the number of queries per request.",
            "high",
        )]
    if cat == "heavy_join":
        return [(
            "Simplify heavy join queries",
            "Consider denormalising data, using materialised views, or "
            "splitting into multiple simpler queries.",
            "medium",
        )]
    if cat == "route_hotspot":
        route_hint = f" for {issue.route}" if issue.route else ""
        return [(
            f"Introduce caching{route_hint}",
            "Add response caching, query caching, or rate limiting "
            "to reduce load on frequently-hit slow endpoints.",
            "high",
        )]
    if cat == "large_payload":
        return [(
            "Reduce response payload size",
            "Use pagination, field selection, or response compression "
            "to reduce payload size for large responses.",
            "medium",
        )]

    return [(
        "Review performance concern",
        issue.description,
        "medium",
    )]
