"""
Aksara AI Debugger  (v0.5.33)

Automated root-cause analysis pipeline that reads the Project Context
Graph, diagnostics, gap analysis, and event timeline to identify,
cluster, rank and explain issues — then suggests safe fix plans.

Usage::

    from aksara.ai.debugger import run_debugger

    report = run_debugger()                     # full analysis
    report = run_debugger(query="why is /api/users failing?")

Pipeline steps:
    1. Load Project Graph  (``build_project_graph``)
    2. Build issue pool    (diagnostics + gaps + events)
    3. Cluster issues      (by model / route / query / migration / time)
    4. Detect root causes  (evidence-based heuristic)
    5. Rank by score       (severity + evidence + recency + cluster size)
    6. Suggest fixes       (safe, read-only suggestions)

Safety:
    The debugger NEVER modifies code, database, or files.  It only
    returns analysis, evidence, and suggestions.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aksara.ai.debugger")

# ─── Severity Weights ────────────────────────────────────────────────────────

_SEVERITY_WEIGHT: Dict[str, float] = {
    "error": 1.0,
    "warning": 0.6,
    "info": 0.2,
}

# ─── Data Models ─────────────────────────────────────────────────────────────


@dataclass
class DebugIssue:
    """A single issue extracted from diagnostics, gaps, or events."""

    id: str
    source: str  # "diagnostic", "gap", "event"
    severity: str
    title: str
    message: str
    related_models: List[str] = field(default_factory=list)
    related_routes: List[str] = field(default_factory=list)
    related_queries: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IssueCluster:
    """A group of related issues sharing a common component."""

    cluster_id: str
    label: str
    component_type: str  # "model", "route", "query", "migration", "general"
    component_name: str
    issue_ids: List[str] = field(default_factory=list)
    severity: str = "info"
    size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RootCause:
    """A detected root cause with evidence and confidence score."""

    cause_id: str
    title: str
    description: str
    confidence: float  # 0.0 – 1.0
    severity: str
    evidence: List[str] = field(default_factory=list)
    related_issues: List[str] = field(default_factory=list)
    related_clusters: List[str] = field(default_factory=list)
    category: str = "general"
    fix_suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DebugReport:
    """Complete output of the AI Debugger pipeline."""

    ok: bool
    query: Optional[str]
    issues: List[DebugIssue] = field(default_factory=list)
    clusters: List[IssueCluster] = field(default_factory=list)
    root_causes: List[RootCause] = field(default_factory=list)
    summary: str = ""
    issue_count: int = 0
    cluster_count: int = 0
    root_cause_count: int = 0
    elapsed_ms: float = 0.0
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "query": self.query,
            "issue_count": self.issue_count,
            "cluster_count": self.cluster_count,
            "root_cause_count": self.root_cause_count,
            "top_root_causes": [
                {"title": rc.title, "confidence": rc.confidence, "severity": rc.severity}
                for rc in self.root_causes[:5]
            ],
            "summary": self.summary,
            "elapsed_ms": self.elapsed_ms,
            "generated_at": self.generated_at,
        }


# ─── Main Entry Point ───────────────────────────────────────────────────────


def run_debugger(
    query: Optional[str] = None,
    *,
    app: Any = None,
) -> DebugReport:
    """Run the full AI Debugger pipeline.

    Parameters
    ----------
    query : str, optional
        Natural-language question, e.g. "why is /api/users failing?".
        If ``None``, analyses the whole project.
    app : Any, optional
        FastAPI app instance (passed to ``build_project_graph``).

    Returns
    -------
    DebugReport
        Structured debug analysis with issues, clusters, root causes,
        and fix suggestions.
    """
    t0 = time.monotonic()
    now = datetime.now(timezone.utc).isoformat()

    # ── Step 1: Load Project Graph ────────────────────────────────────────
    try:
        from aksara.ai.project_graph import build_project_graph
        graph = build_project_graph(app=app)
    except Exception as exc:
        logger.warning("debugger: could not load project graph: %s", exc)
        return DebugReport(
            ok=False, query=query,
            summary=f"Could not load project graph: {exc}",
            generated_at=now,
            elapsed_ms=_elapsed(t0),
        )

    # ── Step 2: Build issue pool ──────────────────────────────────────────
    issues = _build_issue_pool(graph, query=query)

    # ── Step 3: Cluster issues ────────────────────────────────────────────
    clusters = _cluster_issues(issues)

    # ── Step 4: Detect root causes ────────────────────────────────────────
    root_causes = _detect_root_causes(issues, clusters, graph)

    # ── Step 5: Rank ──────────────────────────────────────────────────────
    root_causes = _rank_root_causes(root_causes)

    # ── Step 6: Fix suggestions ───────────────────────────────────────────
    root_causes = _generate_fix_suggestions(root_causes, issues, graph)

    # ── Build summary ─────────────────────────────────────────────────────
    summary = _build_summary(issues, clusters, root_causes, query)
    elapsed = _elapsed(t0)

    return DebugReport(
        ok=True,
        query=query,
        issues=issues,
        clusters=clusters,
        root_causes=root_causes,
        summary=summary,
        issue_count=len(issues),
        cluster_count=len(clusters),
        root_cause_count=len(root_causes),
        elapsed_ms=elapsed,
        generated_at=now,
    )


# ─── Step 2: Build Issue Pool ────────────────────────────────────────────────


def _build_issue_pool(graph, *, query: Optional[str] = None) -> List[DebugIssue]:
    """Extract issues from diagnostics, gaps, and events."""
    issues: List[DebugIssue] = []
    idx = 0

    # From diagnostics
    for d in graph.diagnostics:
        idx += 1
        issues.append(DebugIssue(
            id=f"diag-{idx}",
            source="diagnostic",
            severity=d.severity,
            title=d.code,
            message=d.message,
            related_models=list(d.related_models),
            related_routes=list(d.related_routes),
            related_queries=list(d.related_queries),
            meta={"code": d.code},
        ))

    # From gaps
    for g in graph.gaps:
        idx += 1
        issues.append(DebugIssue(
            id=f"gap-{idx}",
            source="gap",
            severity=g.severity,
            title=g.code,
            message=g.summary,
            related_models=[c for c in g.related_components if not c.startswith("/")],
            related_routes=[c for c in g.related_components if c.startswith("/")],
            meta={"category": g.category, "code": g.code},
        ))

    # From events (errors and warnings only)
    for ev_dict in graph.events:
        sev = ev_dict.get("severity", "info") if isinstance(ev_dict, dict) else getattr(ev_dict, "severity", "info")
        if sev not in ("error", "warning"):
            continue
        idx += 1
        kind = ev_dict.get("kind", "") if isinstance(ev_dict, dict) else getattr(ev_dict, "kind", "")
        msg = ev_dict.get("message", "") if isinstance(ev_dict, dict) else getattr(ev_dict, "message", "")
        ts = ev_dict.get("timestamp", "") if isinstance(ev_dict, dict) else getattr(ev_dict, "timestamp", "")
        src_id = ev_dict.get("source_id", "") if isinstance(ev_dict, dict) else getattr(ev_dict, "source_id", "")
        src_type = ev_dict.get("source_type", "") if isinstance(ev_dict, dict) else getattr(ev_dict, "source_type", "")
        issues.append(DebugIssue(
            id=f"evt-{idx}",
            source="event",
            severity=sev,
            title=kind,
            message=msg,
            timestamp=ts,
            related_routes=[src_id] if src_type == "route" else [],
            related_models=[src_id] if src_type == "model" else [],
            related_queries=[src_id] if src_type == "query" else [],
            meta={"kind": kind, "source_type": src_type, "source_id": src_id},
        ))

    # Filter by query if provided
    if query:
        issues = _filter_by_query(issues, query)

    return issues


def _filter_by_query(issues: List[DebugIssue], query: str) -> List[DebugIssue]:
    """Filter issues relevant to the user's query."""
    keywords = set(re.findall(r'\b\w{3,}\b', query.lower()))
    if not keywords:
        return issues

    filtered = []
    for issue in issues:
        text = f"{issue.title} {issue.message} {' '.join(issue.related_models)} {' '.join(issue.related_routes)}".lower()
        if any(kw in text for kw in keywords):
            filtered.append(issue)

    # If filter is too aggressive, return all
    return filtered if filtered else issues


# ─── Step 3: Cluster Issues ──────────────────────────────────────────────────


def _cluster_issues(issues: List[DebugIssue]) -> List[IssueCluster]:
    """Group related issues by shared component (model, route, query)."""
    component_map: Dict[str, List[DebugIssue]] = {}

    for issue in issues:
        components_found = False
        for model in issue.related_models:
            key = f"model:{model}"
            component_map.setdefault(key, []).append(issue)
            components_found = True
        for route in issue.related_routes:
            key = f"route:{route}"
            component_map.setdefault(key, []).append(issue)
            components_found = True
        for query in issue.related_queries:
            key = f"query:{query}"
            component_map.setdefault(key, []).append(issue)
            components_found = True
        if not components_found:
            component_map.setdefault("general:uncategorised", []).append(issue)

    clusters: List[IssueCluster] = []
    cidx = 0
    for key, grouped in sorted(component_map.items(), key=lambda kv: -len(kv[1])):
        cidx += 1
        ctype, cname = key.split(":", 1)
        worst_sev = _worst_severity([i.severity for i in grouped])
        clusters.append(IssueCluster(
            cluster_id=f"cluster-{cidx}",
            label=f"{ctype.title()}: {cname}",
            component_type=ctype,
            component_name=cname,
            issue_ids=[i.id for i in grouped],
            severity=worst_sev,
            size=len(grouped),
        ))

    return clusters


# ─── Step 4: Detect Root Causes ──────────────────────────────────────────────


def _detect_root_causes(
    issues: List[DebugIssue],
    clusters: List[IssueCluster],
    graph,
) -> List[RootCause]:
    """Heuristic root-cause detection based on issue patterns."""
    root_causes: List[RootCause] = []
    rcidx = 0

    # Pattern 1: Database connectivity issues
    db_issues = [i for i in issues if _is_db_issue(i)]
    if db_issues:
        rcidx += 1
        root_causes.append(RootCause(
            cause_id=f"rc-{rcidx}",
            title="Database connectivity problem",
            description="Multiple issues related to database connectivity or missing configuration detected.",
            confidence=0.0,  # scored in ranking step
            severity=_worst_severity([i.severity for i in db_issues]),
            evidence=[f"[{i.severity}] {i.title}: {i.message}" for i in db_issues[:5]],
            related_issues=[i.id for i in db_issues],
            related_clusters=[c.cluster_id for c in clusters if any(iid in c.issue_ids for iid in [i.id for i in db_issues])],
            category="database",
        ))

    # Pattern 2: Migration issues
    mig_issues = [i for i in issues if _is_migration_issue(i)]
    if mig_issues:
        rcidx += 1
        root_causes.append(RootCause(
            cause_id=f"rc-{rcidx}",
            title="Migration state issue",
            description="Pending or conflicting migrations detected that may cause schema drift.",
            confidence=0.0,
            severity=_worst_severity([i.severity for i in mig_issues]),
            evidence=[f"[{i.severity}] {i.title}: {i.message}" for i in mig_issues[:5]],
            related_issues=[i.id for i in mig_issues],
            related_clusters=[c.cluster_id for c in clusters if any(iid in c.issue_ids for iid in [i.id for i in mig_issues])],
            category="migration",
        ))

    # Pattern 3: AI provider issues
    ai_issues = [i for i in issues if _is_ai_issue(i)]
    if ai_issues:
        rcidx += 1
        root_causes.append(RootCause(
            cause_id=f"rc-{rcidx}",
            title="AI provider configuration issue",
            description="AI provider missing, misconfigured, or unreachable.",
            confidence=0.0,
            severity=_worst_severity([i.severity for i in ai_issues]),
            evidence=[f"[{i.severity}] {i.title}: {i.message}" for i in ai_issues[:5]],
            related_issues=[i.id for i in ai_issues],
            related_clusters=[c.cluster_id for c in clusters if any(iid in c.issue_ids for iid in [i.id for i in ai_issues])],
            category="ai_provider",
        ))

    # Pattern 4: Route error clusters
    route_clusters = [c for c in clusters if c.component_type == "route" and c.severity == "error"]
    for rc_cluster in route_clusters:
        rcidx += 1
        cluster_issues = [i for i in issues if i.id in rc_cluster.issue_ids]
        root_causes.append(RootCause(
            cause_id=f"rc-{rcidx}",
            title=f"Route failures: {rc_cluster.component_name}",
            description=f"Multiple error-level issues clustered around route {rc_cluster.component_name}.",
            confidence=0.0,
            severity="error",
            evidence=[f"[{i.severity}] {i.title}: {i.message}" for i in cluster_issues[:5]],
            related_issues=[i.id for i in cluster_issues],
            related_clusters=[rc_cluster.cluster_id],
            category="route",
        ))

    # Pattern 5: Security warnings
    sec_issues = [i for i in issues if _is_security_issue(i)]
    if sec_issues:
        rcidx += 1
        root_causes.append(RootCause(
            cause_id=f"rc-{rcidx}",
            title="Security configuration issues",
            description="Security-related diagnostic or gap detected.",
            confidence=0.0,
            severity=_worst_severity([i.severity for i in sec_issues]),
            evidence=[f"[{i.severity}] {i.title}: {i.message}" for i in sec_issues[:5]],
            related_issues=[i.id for i in sec_issues],
            related_clusters=[c.cluster_id for c in clusters if any(iid in c.issue_ids for iid in [i.id for i in sec_issues])],
            category="security",
        ))

    # Pattern 6: Large clusters (>= 3 issues) without a specific root cause
    assigned = {iid for rc in root_causes for iid in rc.related_issues}
    for cluster in clusters:
        if cluster.size >= 3:
            unassigned = [iid for iid in cluster.issue_ids if iid not in assigned]
            if len(unassigned) >= 2:
                rcidx += 1
                cluster_issues = [i for i in issues if i.id in unassigned]
                root_causes.append(RootCause(
                    cause_id=f"rc-{rcidx}",
                    title=f"Issue cluster: {cluster.label}",
                    description=f"{cluster.size} issues concentrated around {cluster.label}.",
                    confidence=0.0,
                    severity=cluster.severity,
                    evidence=[f"[{i.severity}] {i.title}: {i.message}" for i in cluster_issues[:5]],
                    related_issues=unassigned,
                    related_clusters=[cluster.cluster_id],
                    category=cluster.component_type,
                ))

    return root_causes


# ─── Step 5: Rank Root Causes ────────────────────────────────────────────────


def _rank_root_causes(root_causes: List[RootCause]) -> List[RootCause]:
    """Score and sort root causes by importance.

    Score formula:
        raw = severity_weight * 0.4
            + evidence_ratio  * 0.3
            + cluster_ratio   * 0.2
            + issue_ratio     * 0.1

    Confidence is the normalised raw score (0.0–1.0).
    """
    if not root_causes:
        return root_causes

    max_evidence = max(len(rc.evidence) for rc in root_causes) or 1
    max_clusters = max(len(rc.related_clusters) for rc in root_causes) or 1
    max_issues = max(len(rc.related_issues) for rc in root_causes) or 1

    for rc in root_causes:
        sev_w = _SEVERITY_WEIGHT.get(rc.severity, 0.2)
        evidence_ratio = len(rc.evidence) / max_evidence
        cluster_ratio = len(rc.related_clusters) / max_clusters
        issue_ratio = len(rc.related_issues) / max_issues

        raw = (
            sev_w * 0.4
            + evidence_ratio * 0.3
            + cluster_ratio * 0.2
            + issue_ratio * 0.1
        )
        rc.confidence = round(min(max(raw, 0.0), 1.0), 3)

    root_causes.sort(key=lambda rc: -rc.confidence)
    return root_causes


# ─── Step 6: Fix Suggestions ─────────────────────────────────────────────────


def _generate_fix_suggestions(
    root_causes: List[RootCause],
    issues: List[DebugIssue],
    graph,
) -> List[RootCause]:
    """Attach safe fix suggestions to each root cause."""
    for rc in root_causes:
        suggestions: List[str] = []

        if rc.category == "database":
            suggestions.append("Check DATABASE_URL environment variable is set and correct.")
            suggestions.append("Verify the database server is running and accepting connections.")
            suggestions.append("Run 'aksara diagnostics' to get detailed DB connectivity info.")

        elif rc.category == "migration":
            suggestions.append("Run 'aksara migrate' to apply pending migrations.")
            suggestions.append("Check for migration conflicts with 'aksara migrate --check'.")
            suggestions.append("Review migration history for inconsistencies.")

        elif rc.category == "ai_provider":
            suggestions.append("Configure at least one AI provider in AI Hub settings.")
            suggestions.append("Check API key environment variables (e.g. OPENAI_API_KEY).")
            suggestions.append("Run 'aksara ai hub providers' to verify provider status.")

        elif rc.category == "route":
            suggestions.append("Check route handler for unhandled exceptions.")
            suggestions.append("Verify model dependencies are available.")
            suggestions.append("Review recent events for error patterns on this route.")

        elif rc.category == "security":
            suggestions.append("Review security settings in aksara.conf.")
            suggestions.append("Ensure DEBUG mode is disabled in production.")
            suggestions.append("Check CORS and allowed origins configuration.")

        else:
            suggestions.append("Review the related issues for common patterns.")
            suggestions.append("Run 'aksara diagnostics' for a comprehensive health check.")

        rc.fix_suggestions = suggestions

    return root_causes


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _is_db_issue(issue: DebugIssue) -> bool:
    text = f"{issue.title} {issue.message}".lower()
    return any(kw in text for kw in ("database", "db_", "pool", "connection", "sql", "postgres"))


def _is_migration_issue(issue: DebugIssue) -> bool:
    text = f"{issue.title} {issue.message}".lower()
    return any(kw in text for kw in ("migration", "migrate", "schema drift", "pending"))


def _is_ai_issue(issue: DebugIssue) -> bool:
    text = f"{issue.title} {issue.message}".lower()
    return any(kw in text for kw in ("ai_provider", "provider_missing", "provider_unreachable", "api_key", "openai", "anthropic"))


def _is_security_issue(issue: DebugIssue) -> bool:
    text = f"{issue.title} {issue.message}".lower()
    return any(kw in text for kw in ("security", "cors", "csrf", "auth", "permission", "secret"))


def _worst_severity(severities: List[str]) -> str:
    order = {"error": 3, "warning": 2, "info": 1}
    if not severities:
        return "info"
    return max(severities, key=lambda s: order.get(s, 0))


def _elapsed(t0: float) -> float:
    return round((time.monotonic() - t0) * 1000, 1)


def _build_summary(
    issues: List[DebugIssue],
    clusters: List[IssueCluster],
    root_causes: List[RootCause],
    query: Optional[str],
) -> str:
    """Build a human-readable summary."""
    parts: List[str] = []

    if query:
        parts.append(f"Debug analysis for: {query}")
    else:
        parts.append("Full project debug analysis")

    parts.append(f"Found {len(issues)} issues in {len(clusters)} clusters.")

    if root_causes:
        parts.append(f"Detected {len(root_causes)} potential root causes.")
        top = root_causes[0]
        parts.append(f"Top cause: {top.title} (confidence: {top.confidence:.0%})")
    else:
        parts.append("No specific root causes detected.")

    error_count = sum(1 for i in issues if i.severity == "error")
    warn_count = sum(1 for i in issues if i.severity == "warning")
    if error_count:
        parts.append(f"{error_count} error(s), {warn_count} warning(s).")

    return " ".join(parts)
