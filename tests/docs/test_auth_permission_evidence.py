"""Bind authentication guidance to the executed installed-package examples."""

import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_auth_permission_evidence_is_current():
    evidence = json.loads((ROOT / "audit-evidence/v071/auth-permission-execution.json").read_text())
    assert evidence["pass"] and evidence["disposable_schema_removed"]
    assert evidence["source_checkout_framework_imports"] is False
    for path, digest in evidence["page_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence["runner_sha256"] == hashlib.sha256((ROOT / "scripts/check_public_auth.py").read_bytes()).hexdigest()
    assert {"different owner denied", "anonymous denied", "inactive owner denied",
            "incorrect credentials rejected", "revoked session rejected"} <= set(evidence["checks"])


def test_permission_example_uses_synchronous_hooks():
    page = (ROOT / "docs/docs/api/permissions.md").read_text()
    source = re.search(r'```python title="app/permissions.py"\n(.*?)```', page, re.DOTALL).group(1)
    tree = ast.parse(source)
    hooks = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
             and node.name in {"has_permission", "has_object_permission"}]
    assert len(hooks) == 2
    assert all(isinstance(node, ast.FunctionDef) for node in hooks)
