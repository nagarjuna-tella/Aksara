"""Semantic guards for public documentation and the generated project."""

from __future__ import annotations

import ast
import dataclasses
import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

from aksara import __version__
from aksara.cli.scaffold import create_project_scaffold, write_scaffold_files
from aksara.tasks import TaskRecord

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "docs"
PYTHON_FENCE = re.compile(
    r"^```(?:python|py)(?:[ \t][^\n]*)?\n(.*?)^```[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


def _public_markdown() -> list[Path]:
    paths = [ROOT / "README.md"]
    paths.extend(DOCS.rglob("*.md"))
    paths.extend((ROOT / "examples").glob("*/README.md"))
    return sorted(
        path
        for path in paths
        if path != DOCS / "changelog.md" and (DOCS / "notes") not in path.parents
    )


def _python_blocks():
    for path in _public_markdown():
        text = path.read_text(encoding="utf-8")
        for number, match in enumerate(PYTHON_FENCE.finditer(text), start=1):
            yield path, number, match.group(1)


def test_public_python_fences_are_syntactically_executable() -> None:
    failures: list[str] = []
    for path, number, source in _python_blocks():
        try:
            compile(
                source,
                f"{path.relative_to(ROOT)}#block-{number}",
                "exec",
                flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
            )
        except SyntaxError as exc:
            failures.append(
                f"{path.relative_to(ROOT)} block {number}: {exc.msg} "
                f"(line {exc.lineno})"
            )
    assert failures == []


def test_public_aksara_imports_resolve() -> None:
    failures: list[str] = []
    for path, number, source in _python_blocks():
        tree = ast.parse(source, mode="exec")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not alias.name.startswith("aksara"):
                        continue
                    try:
                        importlib.import_module(alias.name)
                    except Exception as exc:  # noqa: BLE001  # pragma: no cover - reported below
                        failures.append(
                            f"{path.relative_to(ROOT)} block {number}: "
                            f"import {alias.name}: {type(exc).__name__}: {exc}"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                if not node.module.startswith("aksara"):
                    continue
                try:
                    module = importlib.import_module(node.module)
                except Exception as exc:  # noqa: BLE001  # pragma: no cover - reported below
                    failures.append(
                        f"{path.relative_to(ROOT)} block {number}: "
                        f"from {node.module}: {type(exc).__name__}: {exc}"
                    )
                    continue
                for alias in node.names:
                    if alias.name == "*" or hasattr(module, alias.name):
                        continue
                    try:
                        importlib.import_module(f"{node.module}.{alias.name}")
                    except Exception:  # noqa: BLE001
                        failures.append(
                            f"{path.relative_to(ROOT)} block {number}: "
                            f"{node.module}.{alias.name} does not exist"
                        )
    assert failures == []


def test_nonexistent_ai_classes_are_not_presented_as_python_imports() -> None:
    stale = re.compile(r"\b(?:AgentRuntime|Planner|ContextEngine|PatchEngine|QueryEngine)\b")
    failures = [
        f"{path.relative_to(ROOT)} block {number}"
        for path, number, source in _python_blocks()
        if stale.search(source)
    ]
    assert failures == []


def test_legacy_aksara_dictionary_is_never_in_an_executable_fence() -> None:
    failures = [
        f"{path.relative_to(ROOT)} block {number}"
        for path, number, source in _python_blocks()
        if re.search(r"^AKSARA\s*=\s*\{", source, re.MULTILINE)
    ]
    assert failures == []


def test_canonical_docs_distinguish_protocol_from_catalog() -> None:
    for path in [
        ROOT / "README.md",
        DOCS / "quickstart.md",
        DOCS / "getting-started" / "first-project.md",
        DOCS / "getting-started" / "mcp.md",
    ]:
        text = path.read_text(encoding="utf-8")
        assert "/mcp/" in text
        assert "Streamable HTTP" in text
        assert "/ai/tools/mcp" in text
        assert "inspection catalog" in text.lower()


def test_task_identity_docs_match_persisted_record() -> None:
    persisted = {field.name for field in dataclasses.fields(TaskRecord)}
    assert "tenant_id" in persisted
    assert {"principal", "roles", "scopes"}.isdisjoint(persisted)

    for path in [
        DOCS / "advanced" / "background-tasks.md",
        DOCS / "roadmap" / "v0-6-stability-contract.md",
    ]:
        text = path.read_text(encoding="utf-8").lower()
        assert "tenant_id" in text
        assert "does not persist" in text or "do not serialize" in text
        assert "principal" in text


def test_generated_project_uses_one_global_settings_source(tmp_path: Path) -> None:
    files = create_project_scaffold("truth_project", tmp_path)
    write_scaffold_files(files)
    project = tmp_path / "truth_project"

    settings_source = (project / "settings.py").read_text(encoding="utf-8")
    env_source = (project / ".env").read_text(encoding="utf-8")
    readme = (project / "README.md").read_text(encoding="utf-8")
    assert "configure(installed_apps=INSTALLED_APPS)" in settings_source
    assert "AKSARA =" not in settings_source
    assert "AKSARA_MCP_ENABLED=false" in env_source
    assert "AKSARA_AI_ENABLED=false" in env_source
    assert "AKSARA_ENABLE_STUDIO=false" in env_source
    assert "/mcp/" in readme and "/ai/tools/mcp" in readme

    for path in project.rglob("*.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "AKSARA_DATABASE_URL": "postgresql://example.invalid/truth",
    }
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import aksara.conf; import settings; "
                "assert settings.settings is aksara.conf.settings; "
                "assert aksara.conf.settings.installed_apps[-1] == 'app'; "
                "assert not aksara.conf.settings.mcp_enabled; "
                "assert not aksara.conf.settings.ai_enabled; "
                "assert not aksara.conf.settings.enable_studio; "
                "import main; assert main.app.title == 'truth_project'"
            ),
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr


def test_version_authorities_and_scaffold_agree() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    scaffold = create_project_scaffold("version_probe", ROOT / ".never-written")
    assert f'version = "{__version__}"' in pyproject
    assert f"v{__version__}" in scaffold[ROOT / ".never-written/version_probe/main.py"]
    assert (
        f'"aksara-framework>={__version__}"'
        in scaffold[ROOT / ".never-written/version_probe/pyproject.toml"]
    )
