"""Regression contracts for workflow imports and diagnostic commands."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from aksara.ai.workflows import _render_set_env_command

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "statement",
    [
        "import aksara.ai.workflows",
        "from aksara.ai.workflows import build_agent_workflow, workflow_stats",
        "import aksara.studio",
        "import aksara.ai.workflows; import aksara.studio",
        "import aksara.studio; import aksara.ai.workflows; import aksara.ai.workflows",
    ],
)
def test_public_workflow_imports_are_order_independent_in_fresh_process(statement):
    code = f"import sys; sys.path.insert(0, {str(ROOT)!r}); {statement}"
    completed = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    ("target", "example", "expected"),
    [
        (
            "DATABASE_URL",
            "postgresql://user:pass@localhost:5432/dbname",
            "export DATABASE_URL=postgresql://user:pass@localhost:5432/dbname",
        ),
        ("OPENAI_API_KEY", "your-secret-here", "export OPENAI_API_KEY=your-secret-here"),
        ("LABEL", '"already quoted"', 'export LABEL="already quoted"'),
        ("LABEL", "two words", "export LABEL='two words'"),
        ("EMPTY", "", "export EMPTY=''"),
        ("DATABASE_URL", 'export DATABASE_URL="postgres://legacy"', 'export DATABASE_URL="postgres://legacy"'),
        ("TOKEN", "TOKEN=legacy-value", "export TOKEN=legacy-value"),
        (
            "SECRET_KEY",
            "$(python3 -c 'print(\"generated\")')",
            "export SECRET_KEY=$(python3 -c 'print(\"generated\")')",
        ),
        ("UNSET", None, "export UNSET=..."),
    ],
)
def test_set_env_actions_render_one_coherent_assignment(target, example, expected):
    assert _render_set_env_command(target, example) == expected
