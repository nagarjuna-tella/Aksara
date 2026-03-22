"""
AI Investigation Engine — Core Data Models  (v0.5.39)

Persistent investigation sessions that transform AI from
"Prompt → Response" into "Goal → Plan → Execute → Inspect → Continue".

An investigation session holds a goal, a plan of discrete steps,
accumulated findings, and status tracking.  The session survives
across multiple console interactions so users can refine, re-run,
and drill into results.

Usage::

    from aksara.ai.investigation import (
        InvestigationStep,
        InvestigationPlan,
        InvestigationSession,
    )

    step = InvestigationStep(name="project_graph")
    plan = InvestigationPlan(goal="Why is the app slow?", steps=[step])
    session = InvestigationSession(goal=plan.goal, plan=plan)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal

# ─── Type Aliases ────────────────────────────────────────────────────────────

StepStatus = Literal["pending", "running", "done", "failed", "skipped"]
SessionStatus = Literal["created", "planning", "running", "paused", "completed", "failed"]

# ─── Investigation Step ──────────────────────────────────────────────────────


@dataclass
class InvestigationStep:
    """A single discrete step inside an investigation plan.

    Attributes:
        id: Unique step identifier (auto-generated UUID).
        name: Canonical step name (e.g. ``"project_graph"``, ``"performance_analysis"``).
        label: Human-readable label shown in the UI.
        status: Current execution state.
        result: Arbitrary result dict populated after execution.
        error: Error message if the step failed.
        started_at: Timestamp when execution began.
        completed_at: Timestamp when execution finished.
    """

    name: str
    label: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: StepStatus = "pending"
    result: Dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None

    def __post_init__(self) -> None:
        if not self.label:
            self.label = self.name.replace("_", " ").title()

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "label": self.label,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


# ─── Investigation Plan ─────────────────────────────────────────────────────


@dataclass
class InvestigationPlan:
    """Ordered list of steps derived from a user goal.

    Attributes:
        goal: The user's natural-language investigation goal.
        steps: Ordered steps to execute.
        strategy: Short label for the plan strategy (e.g. ``"performance"``, ``"generic"``).
    """

    goal: str
    steps: List[InvestigationStep] = field(default_factory=list)
    strategy: str = "generic"

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        return {
            "goal": self.goal,
            "strategy": self.strategy,
            "steps": [s.to_dict() for s in self.steps],
        }


# ─── Investigation Session ──────────────────────────────────────────────────


@dataclass
class InvestigationSession:
    """Persistent investigation session that survives across interactions.

    Attributes:
        id: Unique session identifier (auto-generated UUID).
        goal: The user's investigation goal.
        plan: The execution plan (may be ``None`` before planning).
        findings: Accumulated key findings from completed steps.
        status: Overall session status.
        created_at: ISO-8601 creation timestamp.
        updated_at: ISO-8601 last-update timestamp.
    """

    goal: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    plan: InvestigationPlan | None = None
    findings: List[str] = field(default_factory=list)
    status: SessionStatus = "created"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ── helpers ───────────────────────────────────────────────────────────

    def touch(self) -> None:
        """Update the ``updated_at`` timestamp to *now*."""
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def add_finding(self, finding: str) -> None:
        """Append a key finding and bump the timestamp."""
        self.findings.append(finding)
        self.touch()

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "goal": self.goal,
            "plan": self.plan.to_dict() if self.plan else None,
            "findings": self.findings,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_summary_dict(self) -> Dict[str, Any]:
        """Compact summary for list views."""
        step_count = len(self.plan.steps) if self.plan else 0
        done_count = (
            sum(1 for s in self.plan.steps if s.status == "done")
            if self.plan
            else 0
        )
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status,
            "strategy": self.plan.strategy if self.plan else None,
            "steps_total": step_count,
            "steps_done": done_count,
            "findings_count": len(self.findings),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
