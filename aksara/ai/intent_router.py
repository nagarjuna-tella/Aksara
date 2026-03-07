"""
Aksara AI Intent Router  (v0.5.36)

Rule-based intent detection for the Interactive AI Console.
Maps natural-language commands to AI Flow actions without calling an LLM.

The router uses keyword / pattern heuristics and never makes network
calls.  If the input is ambiguous it returns ``intent="unknown"`` with
``confidence=0.0`` so the console engine can respond gracefully.

Supported intents (one per AI_FLOW_ACTIONS entry):
    model   — explain_model, suggest_constraints, refactor_suggestions
    route   — review_endpoint, harden_permissions, generate_examples
    query   — explain_plan, suggest_indexes, rewrite_suggestions
    migration — explain_migration, safe_rollout_plan
    diagnostic — diagnostic_prioritize
    debug   — debug_analyze
    architecture_review — architecture_review
    performance_analysis — performance_analyze
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ─── IntentMatch ─────────────────────────────────────────────────────────────

@dataclass
class IntentMatch:
    """Result of intent detection."""

    intent: str = "unknown"
    flow_type: str = ""
    action_key: str = ""
    confidence: float = 0.0
    extracted_context: Dict[str, Any] = field(default_factory=dict)


# ─── Pattern Rules ───────────────────────────────────────────────────────────
# Each rule is (compiled_regex, flow_type, action_key, base_confidence).
# Rules are evaluated in order; first match with highest confidence wins.

_RULES: List[Tuple[re.Pattern, str, str, float]] = []


def _r(pattern: str, flow_type: str, action_key: str, confidence: float = 0.85) -> None:
    """Register a pattern rule."""
    _RULES.append((re.compile(pattern, re.IGNORECASE), flow_type, action_key, confidence))


# ── Model intents ────────────────────────────────────────────────────────────
_r(r"\bexplain\b.*\bmodel\b", "model", "explain_model", 0.90)
_r(r"\bmodel\b.*\bexplain\b", "model", "explain_model", 0.88)
_r(r"\bdescribe\b.*\bmodel\b", "model", "explain_model", 0.85)
_r(r"\btell\s+me\s+about\b.*\bmodel\b", "model", "explain_model", 0.82)
_r(r"\bwhat\s+is\b.*\bmodel\b", "model", "explain_model", 0.80)
_r(r"\bsuggest\b.*\bconstraint", "model", "suggest_constraints", 0.90)
_r(r"\bconstraint.*\bfor\b", "model", "suggest_constraints", 0.85)
_r(r"\bmissing\b.*\bconstraint", "model", "suggest_constraints", 0.82)
_r(r"\brefactor\b.*\bmodel\b", "model", "refactor_suggestions", 0.90)
_r(r"\bmodel\b.*\brefactor\b", "model", "refactor_suggestions", 0.88)
_r(r"\bimprove\b.*\bmodel\b", "model", "refactor_suggestions", 0.82)
_r(r"\bclean\s*up\b.*\bmodel\b", "model", "refactor_suggestions", 0.80)

# ── Route intents ────────────────────────────────────────────────────────────
_r(r"\breview\b.*\bendpoint\b", "route", "review_endpoint", 0.90)
_r(r"\breview\b.*\broute\b", "route", "review_endpoint", 0.88)
_r(r"\breview\b.*\b(GET|POST|PUT|PATCH|DELETE)\b", "route", "review_endpoint", 0.90)
_r(r"\bcheck\b.*\bendpoint\b", "route", "review_endpoint", 0.82)
_r(r"\bcheck\b.*\broute\b", "route", "review_endpoint", 0.80)
_r(r"\bharden\b.*\bpermission", "route", "harden_permissions", 0.90)
_r(r"\bpermission.*\bharden\b", "route", "harden_permissions", 0.88)
_r(r"\bsecure\b.*\bendpoint\b", "route", "harden_permissions", 0.82)
_r(r"\bsecurity\b.*\broute\b", "route", "harden_permissions", 0.80)
_r(r"\bgenerate\b.*\bexample", "route", "generate_examples", 0.90)
_r(r"\bexample\b.*\brequest", "route", "generate_examples", 0.88)
_r(r"\bcurl\b.*\bendpoint\b", "route", "generate_examples", 0.85)
_r(r"\bsample\b.*\brequest", "route", "generate_examples", 0.82)

# ── Query intents ────────────────────────────────────────────────────────────
_r(r"\bexplain\b.*\bquery\b", "query", "explain_plan", 0.90)
_r(r"\bexplain\b.*\bplan\b", "query", "explain_plan", 0.90)
_r(r"\bquery\b.*\bperformance\b", "query", "explain_plan", 0.82)
_r(r"\banalyse\b.*\bquery\b", "query", "explain_plan", 0.82)
_r(r"\banalyze\b.*\bquery\b", "query", "explain_plan", 0.82)
_r(r"\bsuggest\b.*\bindex", "query", "suggest_indexes", 0.90)
_r(r"\bindex\b.*\brecommend", "query", "suggest_indexes", 0.85)
_r(r"\bmissing\b.*\bindex", "query", "suggest_indexes", 0.82)
_r(r"\brewrite\b.*\bquery\b", "query", "rewrite_suggestions", 0.90)
_r(r"\boptimize\b.*\bquery\b", "query", "rewrite_suggestions", 0.85)
_r(r"\boptimise\b.*\bquery\b", "query", "rewrite_suggestions", 0.85)
_r(r"\bn\+1\b", "query", "rewrite_suggestions", 0.88)

# ── Migration intents ────────────────────────────────────────────────────────
_r(r"\bexplain\b.*\bmigration\b", "migration", "explain_migration", 0.90)
_r(r"\bmigration\b.*\bimpact\b", "migration", "explain_migration", 0.88)
_r(r"\bmigration\b.*\brisk\b", "migration", "explain_migration", 0.85)
_r(r"\brollout\b.*\bplan\b", "migration", "safe_rollout_plan", 0.90)
_r(r"\bsafe\b.*\bmigration\b", "migration", "safe_rollout_plan", 0.85)
_r(r"\bdeploy\b.*\bmigration\b", "migration", "safe_rollout_plan", 0.82)

# ── Diagnostic intents ───────────────────────────────────────────────────────
_r(r"\bdiagnostic\b.*\bprioritize\b", "diagnostic", "diagnostic_prioritize", 0.90)
_r(r"\bdiagnostic\b.*\bprioritise\b", "diagnostic", "diagnostic_prioritize", 0.90)
_r(r"\bprioritize\b.*\bissue", "diagnostic", "diagnostic_prioritize", 0.85)
_r(r"\bprioritise\b.*\bissue", "diagnostic", "diagnostic_prioritize", 0.85)
_r(r"\btriage\b.*\bdiagnostic", "diagnostic", "diagnostic_prioritize", 0.85)
_r(r"\bdiagnostic\b.*\bexplain\b", "diagnostic", "diagnostic_prioritize", 0.82)
_r(r"\bfix\b.*\bdiagnostic", "diagnostic", "diagnostic_prioritize", 0.80)

# ── Debug intents (v0.5.33) ──────────────────────────────────────────────────
_r(r"\bdebug\b", "debug", "debug_analyze", 0.88)
_r(r"\broot\s*cause\b", "debug", "debug_analyze", 0.90)
_r(r"\bwhy\b.*\bfail", "debug", "debug_analyze", 0.87)
_r(r"\bwhy\b.*\bbroken\b", "debug", "debug_analyze", 0.87)
_r(r"\bwhy\b.*\berror\b", "debug", "debug_analyze", 0.85)
_r(r"\bwhat\b.*\bbroke\b", "debug", "debug_analyze", 0.88)
_r(r"\bwhat\b.*\bwrong\b", "debug", "debug_analyze", 0.82)
_r(r"\banalyze\b.*\bissue", "debug", "debug_analyze", 0.85)
_r(r"\banalyse\b.*\bissue", "debug", "debug_analyze", 0.85)
_r(r"\bfind\b.*\bbug", "debug", "debug_analyze", 0.83)
_r(r"\bdiagnose\b", "debug", "debug_analyze", 0.87)
_r(r"\btroubleshoot\b", "debug", "debug_analyze", 0.86)
# ── Architecture review intents (v0.5.34) ───────────────────────────────────────────
_r(r"\barchitecture\b.*\breview\b", "architecture_review", "architecture_review", 0.92)
_r(r"\breview\b.*\barchitecture\b", "architecture_review", "architecture_review", 0.92)
_r(r"\barchitectur", "architecture_review", "architecture_review", 0.88)
_r(r"\bhow\s+healthy\b", "architecture_review", "architecture_review", 0.87)
_r(r"\bhealth\s*(score|check)\b", "architecture_review", "architecture_review", 0.88)
_r(r"\banti.?pattern", "architecture_review", "architecture_review", 0.86)
_r(r"\bcoupling\b", "architecture_review", "architecture_review", 0.85)
_r(r"\bcode\s*quality\b", "architecture_review", "architecture_review", 0.83)
_r(r"\bdesign\s*(review|issue|risk)\b", "architecture_review", "architecture_review", 0.84)
_r(r"\brefactor", "architecture_review", "architecture_review", 0.82)
_r(r"\barchitecture\s*analysis\b", "architecture_review", "architecture_review", 0.90)
# ── Performance analysis intents (v0.5.35) ───────────────────────────────────
_r(r"(?<!\bquery\s)\bperformance\s+analyz", "performance_analysis", "performance_analyze", 0.92)
_r(r"(?<!\bquery\s)\bperformance\s+analys", "performance_analysis", "performance_analyze", 0.92)
_r(r"\banalyze\s+performance\b", "performance_analysis", "performance_analyze", 0.91)
_r(r"\banalyse\s+performance\b", "performance_analysis", "performance_analyze", 0.91)
_r(r"\bwhy\b.*\bslow\b", "performance_analysis", "performance_analyze", 0.88)
_r(r"\bapp\b.*\bslow\b", "performance_analysis", "performance_analyze", 0.87)
_r(r"\bfind\b.*\bslow\b.*\bquer", "performance_analysis", "performance_analyze", 0.88)
_r(r"\bslow\b.*\bendpoint", "performance_analysis", "performance_analyze", 0.88)
_r(r"\bperformance\b.*\breview\b", "performance_analysis", "performance_analyze", 0.89)
_r(r"\bn\s*plus\s*one\b", "performance_analysis", "performance_analyze", 0.85)
_r(r"\bquery\s*explosion\b", "performance_analysis", "performance_analyze", 0.90)
# ── Generic explain (low confidence fallback) ────────────────────────────────
_r(r"\bexplain\b", "model", "explain_model", 0.50)
_r(r"\breview\b", "route", "review_endpoint", 0.45)
_r(r"\bsuggest\b", "model", "suggest_constraints", 0.40)


# ─── Context Extraction ─────────────────────────────────────────────────────

# Model name: "explain the User model" → User
_MODEL_NAME_RE = re.compile(
    r"(?:the\s+)?(\b[A-Z][A-Za-z0-9_]*)\b\s*(?:model|table)?",
)

# Route: "review GET /api/users" → GET, /api/users
_ROUTE_RE = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b\s+([/\w\-{}\.:]+)",
    re.IGNORECASE,
)

# SQL: anything in backticks or after "query:" / "sql:"
_SQL_RE = re.compile(
    r"(?:query|sql)\s*:\s*(.+)|`([^`]+)`",
    re.IGNORECASE,
)

# Migration ref: "migration 0003" or "migration auth/0003"
_MIGRATION_RE = re.compile(
    r"\bmigration\s+(?:(\w+)[/\\])?(\w+)",
    re.IGNORECASE,
)

# Diagnostic issue: "issue #12" or "issue DX-001"
_ISSUE_RE = re.compile(
    r"\bissue\s+#?(\S+)",
    re.IGNORECASE,
)

# Common English words that look like model names
_SKIP_MODEL_WORDS = {
    "The", "This", "That", "What", "How", "Can", "Could",
    "Should", "Would", "My", "Your", "Our", "All", "Any",
    "Some", "Each", "Every", "About", "For", "With",
    "Explain", "Describe", "Tell", "Review", "Check",
    "Suggest", "Refactor", "Improve", "Generate", "Harden",
}


def _extract_context(message: str, flow_type: str) -> Dict[str, Any]:
    """Pull structured fields out of the user message."""
    ctx: Dict[str, Any] = {}

    if flow_type == "model":
        m = _ROUTE_RE.search(message)  # skip if it looks like a route
        if not m:
            m = _MODEL_NAME_RE.search(message)
            if m:
                name = m.group(1)
                if name not in _SKIP_MODEL_WORDS:
                    ctx["model_name"] = name

    elif flow_type == "route":
        m = _ROUTE_RE.search(message)
        if m:
            ctx["method"] = m.group(1).upper()
            ctx["path"] = m.group(2)

    elif flow_type == "query":
        m = _SQL_RE.search(message)
        if m:
            ctx["sql"] = (m.group(1) or m.group(2) or "").strip()

    elif flow_type == "migration":
        m = _MIGRATION_RE.search(message)
        if m:
            ctx["app"] = m.group(1) or None
            ctx["name"] = m.group(2) or None

    elif flow_type == "diagnostic":
        m = _ISSUE_RE.search(message)
        if m:
            ctx["issue_id"] = m.group(1)

    elif flow_type == "debug":
        # Extract route context if present for debug queries
        m = _ROUTE_RE.search(message)
        if m:
            ctx["method"] = m.group(1).upper()
            ctx["path"] = m.group(2)
        # Extract model name if present
        else:
            m = _MODEL_NAME_RE.search(message)
            if m and m.group(1) not in _SKIP_MODEL_WORDS:
                ctx["model_name"] = m.group(1)

    elif flow_type == "architecture_review":
        # Optionally extract a focus target
        m = _ROUTE_RE.search(message)
        if m:
            ctx["method"] = m.group(1).upper()
            ctx["path"] = m.group(2)

    elif flow_type == "performance_analysis":
        # Extract route context for performance queries
        m = _ROUTE_RE.search(message)
        if m:
            ctx["method"] = m.group(1).upper()
            ctx["path"] = m.group(2)

    return ctx


# ─── Public API ──────────────────────────────────────────────────────────────

def detect_intent(message: str) -> IntentMatch:
    """Detect the user's intent from a natural-language message.

    Returns the best ``IntentMatch`` found.  If nothing matches,
    returns ``IntentMatch(intent="unknown", confidence=0.0)``.

    Parameters
    ----------
    message : str
        The user's console input.

    Returns
    -------
    IntentMatch
    """
    if not message or not message.strip():
        return IntentMatch()

    text = message.strip()

    best: Optional[IntentMatch] = None

    for pattern, flow_type, action_key, base_confidence in _RULES:
        m = pattern.search(text)
        if m:
            confidence = base_confidence
            # Boost confidence if more of the message matches
            match_ratio = len(m.group(0)) / len(text)
            confidence = min(confidence + match_ratio * 0.1, 1.0)

            if best is None or confidence > best.confidence:
                best = IntentMatch(
                    intent=action_key,
                    flow_type=flow_type,
                    action_key=action_key,
                    confidence=round(confidence, 3),
                    extracted_context=_extract_context(text, flow_type),
                )

    return best or IntentMatch()


def list_intents() -> List[Dict[str, str]]:
    """Return a de-duplicated list of all supported intents for suggestion UIs.

    Returns
    -------
    list[dict]
        Each dict has ``action_key``, ``flow_type``, and ``description``.
    """
    from aksara.studio.ai_flows import AI_FLOW_ACTIONS  # avoid circular at module level

    seen: set = set()
    result: List[Dict[str, str]] = []

    for action_key, meta in AI_FLOW_ACTIONS.items():
        if action_key in seen:
            continue
        seen.add(action_key)
        result.append({
            "action_key": action_key,
            "flow_type": meta["kind"],
            "title": meta.get("title", action_key),
            "description": meta.get("description", ""),
        })

    return result


# ─── Suggestion helpers ──────────────────────────────────────────────────────

# Pre-built suggestion phrases for the console command palette
EXAMPLE_COMMANDS: List[str] = [
    "Explain the User model",
    "Suggest constraints for Order",
    "Refactor the Product model",
    "Review GET /api/users",
    "Harden permissions on POST /api/orders",
    "Generate example requests for GET /api/products",
    "Explain the query plan",
    "Suggest indexes",
    "Rewrite query for performance",
    "Explain migration impact",
    "Safe rollout plan for migration",
    "Prioritize diagnostic issues",
]


def suggest_commands(prefix: str) -> List[str]:
    """Return example commands that match a prefix for autocomplete.

    Parameters
    ----------
    prefix : str
        What the user has typed so far (case-insensitive).

    Returns
    -------
    list[str]
        Matching suggestions, max 6.
    """
    if not prefix:
        return EXAMPLE_COMMANDS[:6]

    lower = prefix.lower()
    matches = [cmd for cmd in EXAMPLE_COMMANDS if lower in cmd.lower()]
    return matches[:6]
