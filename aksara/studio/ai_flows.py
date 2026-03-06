"""
Aksara Studio AI Flows  (v0.5.29 builders, v0.5.30 execution)

Deterministic prompt-pack builders for in-context AI actions.
Each builder gathers project context, constructs a system + user prompt
pair, and returns a ``StudioAiFlowResponse``.  No network calls are made
to external AI vendors — the output is a *prompt pack* the user can
run in any LLM client.

v0.5.30 adds ``execute_*_flow()`` functions that optionally run the
prompt pack through a connector via ``aksara.ai.runtime``.

Flow kinds:
    - model   — explain / suggest constraints / refactor suggestions
    - route   — review endpoint / harden permissions / example requests
    - query   — explain plan / suggest indexes / rewrite suggestions
    - migration — explain impact / safe rollout plan
    - diagnostic — explain & prioritize
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from aksara.studio.models import StudioAiFlowResponse

# ─── Action Registry ────────────────────────────────────────────────────────

AI_FLOW_ACTIONS: Dict[str, Dict[str, Any]] = {
    # Model actions
    "explain_model": {
        "kind": "model",
        "title": "Explain Model",
        "description": "Explain all fields, relationships, PII/sensitivity hints, and usage patterns.",
        "risk": "low",
        "what_it_does": "Reads the model schema and generates a human-readable overview.",
        "what_it_cannot_do": "Cannot see live row counts or actual data values.",
        "recommended_next": ["suggest_constraints", "refactor_suggestions"],
    },
    "suggest_constraints": {
        "kind": "model",
        "title": "Suggest Constraints",
        "description": "Recommend unique, index, check, and nullable constraints.",
        "risk": "medium",
        "what_it_does": "Analyses fields and relationships to recommend missing DB constraints.",
        "what_it_cannot_do": "Cannot execute DDL or measure real-world query performance.",
        "recommended_next": ["explain_model"],
    },
    "refactor_suggestions": {
        "kind": "model",
        "title": "Refactor Suggestions",
        "description": "Naming, normalization, and consistency improvements.",
        "risk": "medium",
        "what_it_does": "Reviews naming conventions, field types, and table structure for improvements.",
        "what_it_cannot_do": "Cannot auto-apply refactors or generate migrations.",
        "recommended_next": ["suggest_constraints"],
    },
    # Route actions
    "review_endpoint": {
        "kind": "route",
        "title": "Review Endpoint",
        "description": "Auth/permissions, input validation, response shape review.",
        "risk": "low",
        "what_it_does": "Examines endpoint metadata for security, validation, and response gaps.",
        "what_it_cannot_do": "Cannot execute requests or verify runtime behavior.",
        "recommended_next": ["harden_permissions", "generate_examples"],
    },
    "harden_permissions": {
        "kind": "route",
        "title": "Harden Permissions",
        "description": "Identify admin-only risks and suggest safe defaults.",
        "risk": "medium",
        "what_it_does": "Flags endpoints with weak or missing permission checks.",
        "what_it_cannot_do": "Cannot modify route definitions or auth backends.",
        "recommended_next": ["review_endpoint"],
    },
    "generate_examples": {
        "kind": "route",
        "title": "Generate Example Requests",
        "description": "Produce curl + JSON payload examples for the endpoint.",
        "risk": "low",
        "what_it_does": "Generates sample HTTP requests with realistic payloads.",
        "what_it_cannot_do": "Cannot guarantee payload validity against live schema changes.",
        "recommended_next": ["review_endpoint"],
    },
    # Query actions
    "explain_plan": {
        "kind": "query",
        "title": "Explain Query Plan",
        "description": "Analyse EXPLAIN output for performance insights.",
        "risk": "low",
        "what_it_does": "Parses the query plan and highlights sequential scans, cost hot spots, and join issues.",
        "what_it_cannot_do": "Cannot modify queries or create indexes.",
        "recommended_next": ["suggest_indexes", "rewrite_suggestions"],
    },
    "suggest_indexes": {
        "kind": "query",
        "title": "Suggest Indexes",
        "description": "Safe, conservative index recommendations.",
        "risk": "medium",
        "what_it_does": "Recommends CREATE INDEX statements based on query patterns.",
        "what_it_cannot_do": "Cannot measure index build time or disk overhead.",
        "recommended_next": ["explain_plan"],
    },
    "rewrite_suggestions": {
        "kind": "query",
        "title": "Rewrite Suggestions",
        "description": "Selectivity improvements, N+1 detection.",
        "risk": "medium",
        "what_it_does": "Suggests WHERE-clause improvements and prefetch strategies.",
        "what_it_cannot_do": "Cannot benchmark alternative queries.",
        "recommended_next": ["explain_plan", "suggest_indexes"],
    },
    # Migration actions
    "explain_migration": {
        "kind": "migration",
        "title": "Explain Migration Impact",
        "description": "Locking risk, downtime risk, data-loss potential.",
        "risk": "low",
        "what_it_does": "Analyses migration SQL for lock types, table sizes, and risk factors.",
        "what_it_cannot_do": "Cannot predict actual downtime without real DB metrics.",
        "recommended_next": ["safe_rollout_plan"],
    },
    "safe_rollout_plan": {
        "kind": "migration",
        "title": "Safe Rollout Plan",
        "description": "Expand/contract strategy, deployment steps.",
        "risk": "medium",
        "what_it_does": "Produces an ordered deploy plan with expand and contract phases.",
        "what_it_cannot_do": "Cannot auto-split migrations or manage deploy orchestration.",
        "recommended_next": ["explain_migration"],
    },
    # Diagnostic actions
    "diagnostic_prioritize": {
        "kind": "diagnostic",
        "title": "Explain & Prioritize",
        "description": "Short fix strategy using diagnostic issue actions.",
        "risk": "low",
        "what_it_does": "Ranks issues by severity and suggests an ordered fix plan.",
        "what_it_cannot_do": "Cannot apply fixes or access runtime state.",
        "recommended_next": [],
    },
}


def list_flow_actions() -> List[Dict[str, Any]]:
    """Return all registered flow action descriptors."""
    result = []
    for key, meta in AI_FLOW_ACTIONS.items():
        result.append({"action_key": key, **meta})
    return result


def get_flow_action(action_key: str) -> Optional[Dict[str, Any]]:
    """Return a single flow action descriptor or None."""
    meta = AI_FLOW_ACTIONS.get(action_key)
    if meta is None:
        return None
    return {"action_key": action_key, **meta}


# ─── Hub helpers ─────────────────────────────────────────────────────────────

def _get_hub_settings():
    """Lazy-load AiHubSettings."""
    from aksara.ai.hub_settings import load_aihub_settings
    return load_aihub_settings()


def _resolve_provider_model(hub, hub_overrides: Optional[Dict[str, str]] = None):
    """Pick provider + model from hub defaults (with optional overrides)."""
    provider = hub_overrides.get("provider") if hub_overrides else None
    model = hub_overrides.get("model") if hub_overrides else None

    if not provider:
        provider = hub.defaults.chat_provider or hub.active_provider or ""
    if not model:
        model = hub.defaults.chat_model or ""
    return str(provider or ""), str(model or "")


def _hub_not_configured_response(action_key: str) -> StudioAiFlowResponse:
    """Standard error response when AI Hub isn't configured."""
    return StudioAiFlowResponse(
        ok=False,
        action_key=action_key,
        risk="low",
        provider="",
        model="",
        system_prompt="",
        user_prompt="",
        result_markdown="",
        error_code="AI_HUB_NOT_CONFIGURED",
        error="AI Hub is not configured. Open AI Hub onboarding in Studio to set up a provider.",
        suggested_next=["Open AI Hub → Onboarding tab"],
    )


# ─── Context helpers ─────────────────────────────────────────────────────────

def _build_model_context(model_name: str) -> str:
    """Build schema-analysis context for a model."""
    try:
        from aksara.registry import ModelRegistry
        from aksara.inspectors.models import inspect_model

        model_cls = ModelRegistry.get(model_name)
        if model_cls is None:
            return f"Model '{model_name}' not found in the registry."
        summary = inspect_model(model_cls)
        lines = [
            f"## Model: {summary.name}",
            f"Table: {summary.table_name}",
            f"Fields: {summary.num_fields}  |  Relations: {summary.num_relationships}",
            f"PK: {summary.pk_field} ({summary.pk_type})",
            f"Timestamps: {'yes' if summary.has_timestamps else 'no'}",
            "",
        ]
        if summary.ai_description:
            lines.append(f"Description: {summary.ai_description}")
        # Fields
        lines.append("\n### Fields")
        for f in summary.fields:
            nullable = "NULL" if f.nullable else "NOT NULL"
            extra = []
            if f.unique:
                extra.append("UNIQUE")
            if f.primary_key:
                extra.append("PK")
            if f.ai_sensitive:
                extra.append("SENSITIVE")
            if f.has_default:
                extra.append(f"default={f.default_repr}")
            meta = f" [{', '.join(extra)}]" if extra else ""
            lines.append(f"- {f.name}: {f.field_type} ({f.python_type}) {nullable}{meta}")
        # Relationships
        if summary.relationships:
            lines.append("\n### Relationships")
            for r in summary.relationships:
                lines.append(f"- {r.field_name} → {r.target_model} ({r.kind}, on_delete={r.on_delete})")
        # Constraints
        if summary.constraints:
            lines.append("\n### Constraints")
            for c in summary.constraints:
                lines.append(f"- {c.kind}: {', '.join(c.columns)}")
        # Notes
        if summary.comments:
            lines.append("\n### Inspector Notes")
            for c in summary.comments:
                lines.append(f"- {c}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error inspecting model '{model_name}': {exc}"


def _build_route_context(path: str, method: str) -> str:
    """Build route-definition context for an endpoint."""
    try:
        from aksara.studio.utils import build_routes_info
        routes = build_routes_info()
        for r in routes:
            r_path = getattr(r, "path", "")
            r_method = getattr(r, "method", "GET")
            if r_path == path and r_method.upper() == method.upper():
                lines = [
                    f"## Endpoint: {r_method} {r_path}",
                    f"Name: {getattr(r, 'name', 'N/A')}",
                    f"Tags: {getattr(r, 'tags', [])}",
                    f"Auth required: {getattr(r, 'auth_required', 'unknown')}",
                    f"Permissions: {getattr(r, 'permissions', [])}",
                ]
                # Include schema hints if available
                ai_hint = getattr(r, "ai_hint", None)
                if ai_hint:
                    lines.append(f"\nAI Hint: {ai_hint}")
                params = getattr(r, "parameters", [])
                if params:
                    lines.append("\n### Parameters")
                    for p in params:
                        lines.append(f"- {p}")
                resp_model = getattr(r, "response_model", None)
                if resp_model:
                    lines.append(f"\nResponse model: {resp_model}")
                return "\n".join(lines)
        return f"Route {method} {path} not found in registered routes."
    except Exception as exc:
        return f"Error building route context: {exc}"


def _build_query_context(sql: str, include_explain: bool = False) -> str:
    """Build query context — optionally including EXPLAIN output."""
    lines = [
        "## Query",
        "```sql",
        sql.strip(),
        "```",
    ]
    if include_explain:
        lines.append("\nNote: EXPLAIN ANALYZE output not available in prompt-pack mode.")
        lines.append("Include real EXPLAIN output if you have it.")
    return "\n".join(lines)


def _build_migration_context(migration_id: Optional[str] = None, app: Optional[str] = None, name: Optional[str] = None) -> str:
    """Build migration metadata context."""
    lines = ["## Migration"]
    if migration_id:
        lines.append(f"ID: {migration_id}")
    if app:
        lines.append(f"App: {app}")
    if name:
        lines.append(f"Name: {name}")
    try:
        from aksara.studio.utils import build_migration_summary
        mig_summary = build_migration_summary()
        if hasattr(mig_summary, "apps") and mig_summary.apps:
            lines.append(f"\nTotal apps with migrations: {len(mig_summary.apps)}")
            total = sum(getattr(a, "total", 0) for a in mig_summary.apps)
            applied = sum(getattr(a, "applied", 0) for a in mig_summary.apps)
            lines.append(f"Migrations: {applied}/{total} applied")
    except Exception:
        pass
    return "\n".join(lines)


def _build_diagnostic_context(issue_id: Optional[str] = None, issue_payload: Optional[Dict[str, Any]] = None) -> str:
    """Build diagnostic issue context."""
    if issue_payload:
        lines = [
            "## Diagnostic Issue",
            f"Category: {issue_payload.get('category', 'N/A')}",
            f"Severity: {issue_payload.get('severity', 'N/A')}",
            f"Title: {issue_payload.get('title', 'N/A')}",
            f"Message: {issue_payload.get('message', 'N/A')}",
        ]
        hint = issue_payload.get("hint")
        if hint:
            lines.append(f"Hint: {hint}")
        actions = issue_payload.get("actions") or issue_payload.get("fix_commands") or []
        if actions:
            lines.append("\n### Available Fix Actions")
            for a in actions:
                if isinstance(a, dict):
                    lines.append(f"- {a.get('description', a.get('command', str(a)))}")
                else:
                    lines.append(f"- {a}")
        return "\n".join(lines)
    if issue_id:
        return f"## Diagnostic Issue\nID: {issue_id}\n(Fetch detail from diagnostics endpoint)"
    return "## Diagnostic Issue\nNo issue data provided."


# ─── Prompt templates ────────────────────────────────────────────────────────

_SYSTEM_PROMPTS: Dict[str, str] = {
    "explain_model": (
        "You are a senior database architect reviewing an Aksara (Python/Postgres) model.\n"
        "Explain the model clearly: purpose, fields, relationships, any PII/sensitivity risks,\n"
        "and typical usage patterns.  Be concise and structured."
    ),
    "suggest_constraints": (
        "You are a database tuning expert.  Given an Aksara model schema, suggest missing\n"
        "UNIQUE constraints, indexes, CHECK constraints, and nullable changes.\n"
        "Only suggest safe, conservative changes.  Explain WHY for each suggestion."
    ),
    "refactor_suggestions": (
        "You are a code-quality reviewer.  Given an Aksara model schema, suggest naming\n"
        "improvements, normalization opportunities, and consistency fixes.\n"
        "Do NOT suggest breaking changes unless clearly beneficial."
    ),
    "review_endpoint": (
        "You are an API security reviewer.  Given an endpoint definition, review:\n"
        "- Authentication and permission requirements\n"
        "- Input validation gaps\n"
        "- Response shape concerns\n"
        "Be specific and actionable."
    ),
    "harden_permissions": (
        "You are a security hardening specialist.  Given an endpoint definition, identify:\n"
        "- Admin-only operations exposed without proper guards\n"
        "- Missing rate limits or permission checks\n"
        "- Safe defaults that should be applied\n"
        "Suggest concrete permission class or decorator additions."
    ),
    "generate_examples": (
        "You are an API documentation expert.  Given an endpoint definition, generate:\n"
        "- 2-3 curl examples with realistic payloads\n"
        "- A JSON request body example\n"
        "- Expected response shape\n"
        "Use placeholder values that look realistic."
    ),
    "explain_plan": (
        "You are a PostgreSQL query optimizer.  Given a SQL query (and optionally its\n"
        "EXPLAIN output), analyze:\n"
        "- Sequential scan risks\n"
        "- Join order and type\n"
        "- Cost hot spots\n"
        "- Missing index opportunities\n"
        "Be concise; use bullet points."
    ),
    "suggest_indexes": (
        "You are a PostgreSQL DBA.  Given a SQL query, suggest CREATE INDEX statements.\n"
        "Rules:\n"
        "- Only suggest indexes that clearly help this query\n"
        "- Prefer partial indexes when appropriate\n"
        "- Warn about write-heavy tables\n"
        "- Include IF NOT EXISTS"
    ),
    "rewrite_suggestions": (
        "You are a PostgreSQL query expert.  Given a SQL query, suggest rewrites:\n"
        "- Better selectivity (narrow WHERE clauses)\n"
        "- N+1 detection and prefetch hints\n"
        "- CTE vs subquery trade-offs\n"
        "Show before/after SQL."
    ),
    "explain_migration": (
        "You are a deployment engineer.  Given migration metadata, analyze:\n"
        "- Lock risks (ACCESS EXCLUSIVE, ROW EXCLUSIVE, etc.)\n"
        "- Estimated downtime impact\n"
        "- Data-loss potential\n"
        "- Dependencies on other migrations\n"
        "Rate risk as low/medium/high."
    ),
    "safe_rollout_plan": (
        "You are a deployment strategist.  Given migration metadata, produce:\n"
        "- Expand phase: add new columns/tables (backward-compatible)\n"
        "- Migrate phase: backfill data\n"
        "- Contract phase: drop old columns/tables\n"
        "Include rollback steps."
    ),
    "diagnostic_prioritize": (
        "You are a DevOps triage specialist.  Given a set of diagnostic issues with\n"
        "severities and available fix actions, produce:\n"
        "- A priority-ordered fix list\n"
        "- One-line explanation per issue\n"
        "- Estimated effort (quick/medium/long)\n"
        "Focus on blocking issues first."
    ),
}


# ─── Flow Builders ───────────────────────────────────────────────────────────

def build_model_flow(
    model_name: str,
    action_key: str,
    hub_overrides: Optional[Dict[str, str]] = None,
) -> StudioAiFlowResponse:
    """Build an AI flow prompt pack for a model action."""
    action = get_flow_action(action_key)
    if action is None or action["kind"] != "model":
        return StudioAiFlowResponse(
            ok=False,
            action_key=action_key,
            risk="low",
            error_code="INVALID_ACTION",
            error=f"Unknown model action: {action_key}",
        )

    hub = _get_hub_settings()
    if not hub.configured_providers():
        return _hub_not_configured_response(action_key)

    provider, model = _resolve_provider_model(hub, hub_overrides)
    context = _build_model_context(model_name)
    system_prompt = _SYSTEM_PROMPTS.get(action_key, "You are a helpful assistant.")
    user_prompt = f"Analyse the following model and {action['description'].lower()}\n\n{context}"

    return StudioAiFlowResponse(
        ok=True,
        action_key=action_key,
        risk=action["risk"],
        provider=provider,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        result_markdown=f"**Prompt pack ready** — copy and send to your LLM.\n\nProvider: `{provider}` | Model: `{model}`",
        result_json={"model_name": model_name, "action": action_key},
        suggested_next=action.get("recommended_next", []),
        what_it_does=action.get("what_it_does", ""),
        what_it_cannot_do=action.get("what_it_cannot_do", ""),
    )


def build_route_flow(
    path: str,
    method: str,
    action_key: str,
    hub_overrides: Optional[Dict[str, str]] = None,
) -> StudioAiFlowResponse:
    """Build an AI flow prompt pack for a route action."""
    action = get_flow_action(action_key)
    if action is None or action["kind"] != "route":
        return StudioAiFlowResponse(
            ok=False,
            action_key=action_key,
            risk="low",
            error_code="INVALID_ACTION",
            error=f"Unknown route action: {action_key}",
        )

    hub = _get_hub_settings()
    if not hub.configured_providers():
        return _hub_not_configured_response(action_key)

    provider, model = _resolve_provider_model(hub, hub_overrides)
    context = _build_route_context(path, method)
    system_prompt = _SYSTEM_PROMPTS.get(action_key, "You are a helpful assistant.")
    user_prompt = f"Review the following endpoint and {action['description'].lower()}\n\n{context}"

    return StudioAiFlowResponse(
        ok=True,
        action_key=action_key,
        risk=action["risk"],
        provider=provider,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        result_markdown=f"**Prompt pack ready** — copy and send to your LLM.\n\nProvider: `{provider}` | Model: `{model}`",
        result_json={"path": path, "method": method, "action": action_key},
        suggested_next=action.get("recommended_next", []),
        what_it_does=action.get("what_it_does", ""),
        what_it_cannot_do=action.get("what_it_cannot_do", ""),
    )


def build_query_flow(
    sql: str,
    action_key: str,
    include_explain: bool = True,
    hub_overrides: Optional[Dict[str, str]] = None,
) -> StudioAiFlowResponse:
    """Build an AI flow prompt pack for a query action."""
    action = get_flow_action(action_key)
    if action is None or action["kind"] != "query":
        return StudioAiFlowResponse(
            ok=False,
            action_key=action_key,
            risk="low",
            error_code="INVALID_ACTION",
            error=f"Unknown query action: {action_key}",
        )

    hub = _get_hub_settings()
    if not hub.configured_providers():
        return _hub_not_configured_response(action_key)

    provider, model = _resolve_provider_model(hub, hub_overrides)
    context = _build_query_context(sql, include_explain)
    system_prompt = _SYSTEM_PROMPTS.get(action_key, "You are a helpful assistant.")
    user_prompt = f"Analyse the following SQL query and {action['description'].lower()}\n\n{context}"

    return StudioAiFlowResponse(
        ok=True,
        action_key=action_key,
        risk=action["risk"],
        provider=provider,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        result_markdown=f"**Prompt pack ready** — copy and send to your LLM.\n\nProvider: `{provider}` | Model: `{model}`",
        result_json={"sql": sql, "action": action_key},
        suggested_next=action.get("recommended_next", []),
        what_it_does=action.get("what_it_does", ""),
        what_it_cannot_do=action.get("what_it_cannot_do", ""),
    )


def build_migration_flow(
    action_key: str,
    migration_id: Optional[str] = None,
    app: Optional[str] = None,
    name: Optional[str] = None,
    hub_overrides: Optional[Dict[str, str]] = None,
) -> StudioAiFlowResponse:
    """Build an AI flow prompt pack for a migration action."""
    action = get_flow_action(action_key)
    if action is None or action["kind"] != "migration":
        return StudioAiFlowResponse(
            ok=False,
            action_key=action_key,
            risk="low",
            error_code="INVALID_ACTION",
            error=f"Unknown migration action: {action_key}",
        )

    hub = _get_hub_settings()
    if not hub.configured_providers():
        return _hub_not_configured_response(action_key)

    provider, model_name = _resolve_provider_model(hub, hub_overrides)
    context = _build_migration_context(migration_id, app, name)
    system_prompt = _SYSTEM_PROMPTS.get(action_key, "You are a helpful assistant.")
    user_prompt = f"Review the following migration and {action['description'].lower()}\n\n{context}"

    return StudioAiFlowResponse(
        ok=True,
        action_key=action_key,
        risk=action["risk"],
        provider=provider,
        model=model_name,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        result_markdown=f"**Prompt pack ready** — copy and send to your LLM.\n\nProvider: `{provider}` | Model: `{model_name}`",
        result_json={"migration_id": migration_id, "app": app, "name": name, "action": action_key},
        suggested_next=action.get("recommended_next", []),
        what_it_does=action.get("what_it_does", ""),
        what_it_cannot_do=action.get("what_it_cannot_do", ""),
    )


def build_diagnostic_flow(
    action_key: str,
    issue_id: Optional[str] = None,
    issue_payload: Optional[Dict[str, Any]] = None,
    hub_overrides: Optional[Dict[str, str]] = None,
) -> StudioAiFlowResponse:
    """Build an AI flow prompt pack for a diagnostic action."""
    action = get_flow_action(action_key)
    if action is None or action["kind"] != "diagnostic":
        return StudioAiFlowResponse(
            ok=False,
            action_key=action_key,
            risk="low",
            error_code="INVALID_ACTION",
            error=f"Unknown diagnostic action: {action_key}",
        )

    hub = _get_hub_settings()
    if not hub.configured_providers():
        return _hub_not_configured_response(action_key)

    provider, model_name = _resolve_provider_model(hub, hub_overrides)
    context = _build_diagnostic_context(issue_id, issue_payload)
    system_prompt = _SYSTEM_PROMPTS.get(action_key, "You are a helpful assistant.")
    user_prompt = f"Triage the following diagnostic issue and {action['description'].lower()}\n\n{context}"

    return StudioAiFlowResponse(
        ok=True,
        action_key=action_key,
        risk=action["risk"],
        provider=provider,
        model=model_name,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        result_markdown=f"**Prompt pack ready** — copy and send to your LLM.\n\nProvider: `{provider}` | Model: `{model_name}`",
        result_json={"issue_id": issue_id, "action": action_key},
        suggested_next=action.get("recommended_next", []),
        what_it_does=action.get("what_it_does", ""),
        what_it_cannot_do=action.get("what_it_cannot_do", ""),
    )


# ─── v0.5.30: Flow Execution ────────────────────────────────────────────────


async def execute_flow(
    flow_type: str,
    action_key: str,
    context: Dict[str, Any],
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Generic flow execution dispatcher.

    1. Build the prompt pack via the appropriate ``build_*_flow()``
    2. Execute via ``aksara.ai.runtime.run_prompt_pack()``
    3. Return merged result preserving the original prompt pack.
    """
    pack = _dispatch_builder(flow_type, action_key, context)

    if not pack.ok:
        return {
            "ok": False,
            "prompt_pack": pack.model_dump(),
            "execution": None,
            "error": pack.error,
            "error_code": pack.error_code,
        }

    from aksara.ai.runtime import run_prompt_pack

    pack_dict = pack.model_dump()
    execution = await run_prompt_pack(
        pack_dict,
        provider_override=provider_override,
        model_override=model_override,
    )

    return {
        "ok": execution.get("ok", False),
        "prompt_pack": pack_dict,
        "execution": execution,
    }


async def execute_model_flow(
    model_name: str, action_key: str,
    provider_override: Optional[str] = None, model_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Build and execute a model flow."""
    return await execute_flow("model", action_key, {"model_name": model_name},
                              provider_override=provider_override, model_override=model_override)


async def execute_route_flow(
    path: str, method: str, action_key: str,
    provider_override: Optional[str] = None, model_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Build and execute a route flow."""
    return await execute_flow("route", action_key, {"path": path, "method": method},
                              provider_override=provider_override, model_override=model_override)


async def execute_query_flow(
    sql: str, action_key: str,
    provider_override: Optional[str] = None, model_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Build and execute a query flow."""
    return await execute_flow("query", action_key, {"sql": sql},
                              provider_override=provider_override, model_override=model_override)


async def execute_migration_flow(
    action_key: str, app: Optional[str] = None, name: Optional[str] = None,
    provider_override: Optional[str] = None, model_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Build and execute a migration flow."""
    return await execute_flow("migration", action_key, {"app": app, "name": name},
                              provider_override=provider_override, model_override=model_override)


async def execute_diagnostic_flow(
    action_key: str, issue_id: Optional[str] = None,
    provider_override: Optional[str] = None, model_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Build and execute a diagnostic flow."""
    return await execute_flow("diagnostic", action_key, {"issue_id": issue_id},
                              provider_override=provider_override, model_override=model_override)


def _dispatch_builder(flow_type: str, action_key: str, context: Dict[str, Any]) -> StudioAiFlowResponse:
    """Route to the correct ``build_*_flow()``."""
    if flow_type == "model":
        return build_model_flow(model_name=context.get("model_name", ""), action_key=action_key)
    elif flow_type == "route":
        return build_route_flow(path=context.get("path", ""), method=context.get("method", "GET"), action_key=action_key)
    elif flow_type == "query":
        return build_query_flow(sql=context.get("sql", ""), action_key=action_key)
    elif flow_type == "migration":
        return build_migration_flow(action_key=action_key, app=context.get("app"), name=context.get("name"))
    elif flow_type == "diagnostic":
        return build_diagnostic_flow(action_key=action_key, issue_id=context.get("issue_id"), issue_payload=context.get("issue_payload"))
    else:
        return StudioAiFlowResponse(ok=False, action_key=action_key, risk="low",
                                    error_code="INVALID_FLOW_TYPE", error=f"Unknown flow type: {flow_type}")
