"""
Validation for bundled Aksara golden-path examples.
"""

from __future__ import annotations

import importlib
import json
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aksara.launch_check import find_examples_root


EXAMPLE_SPECS: dict[str, dict[str, Any]] = {
    "basic_app": {
        "needs_models": True,
        "needs_migrations": True,
        "import_modules": ["models", "settings"],
    },
    "blog": {
        "needs_models": True,
        "needs_migrations": True,
        "import_modules": ["models", "settings", "views"],
    },
    "crm": {
        "needs_models": True,
        "needs_migrations": True,
        "import_modules": ["models", "settings", "views"],
    },
    "multitenant": {
        "needs_models": True,
        "needs_migrations": True,
        "import_modules": ["models", "settings", "views"],
    },
    "ai_providers": {
        "needs_models": False,
        "needs_migrations": False,
        "import_modules": ["settings", "adapters", "views"],
    },
}

TEXT_SUFFIXES = {".md", ".py", ".txt", ".toml", ".yml", ".yaml", ".env", ".ini", ".json"}
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9][A-Za-z0-9_-]{18,}"),
    re.compile(r"sk-ant-[A-Za-z0-9][A-Za-z0-9_-]{18,}"),
    re.compile(r"(?i)\b(?:OPENAI|ANTHROPIC|AZURE_OPENAI)_API_KEY\s*=\s*([^\s#'\"]+)"),
    re.compile(r"(?i)\bpassword\s*=\s*([^\s#'\"]{12,})"),
]
PLACEHOLDER_TOKENS = {
    "your-key-here",
    "your-api-key",
    "your-openai-key",
    "your-anthropic-key",
    "sk-...",
    "sk-your-key-here",
    "<your-key>",
    "<your-api-key>",
    "<api_key>",
    "<openai_api_key>",
    "<anthropic_api_key>",
    "<azure_openai_api_key>",
    "example-not-a-real-secret",
    "example",
    "placeholder",
}


@dataclass
class ExampleValidationCheck:
    example: str
    name: str
    status: str
    message: str
    hint: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "example": self.example,
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "hint": self.hint,
            "details": self.details,
        }


@dataclass
class ExampleValidationResult:
    name: str
    path: str | None
    checks: list[ExampleValidationCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass
class ExamplesValidationReport:
    ok: bool
    status: str
    examples_root: str | None
    examples: list[ExampleValidationResult]
    summary: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "examples_root": self.examples_root,
            "summary": self.summary,
            "examples": [example.to_dict() for example in self.examples],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @property
    def exit_code(self) -> int:
        if self.status == "ready":
            return 0
        if self.status == "partial":
            return 1
        return 2


def validate_examples(project_root: str | Path | None = None) -> ExamplesValidationReport:
    root = Path(project_root or Path.cwd()).resolve()
    examples_root = find_examples_root(root)
    results: list[ExampleValidationResult] = []

    for example_name, spec in EXAMPLE_SPECS.items():
        example_path = examples_root / example_name if examples_root else None
        result = ExampleValidationResult(
            name=example_name,
            path=str(example_path) if example_path else None,
        )
        results.append(result)

        def add(name: str, status: str, message: str, hint: str | None = None, **details: Any) -> None:
            result.checks.append(
                ExampleValidationCheck(
                    example=example_name,
                    name=name,
                    status=status,
                    message=message,
                    hint=hint,
                    details={key: value for key, value in details.items() if value is not None},
                )
            )

        if example_path is None or not example_path.exists():
            add(
                "exists",
                "error",
                f"{example_name} example missing",
                "Reinstall aksara-framework or restore examples/",
            )
            continue

        add("exists", "ok", "example directory found")
        _check_readme(example_path, add)
        _check_project_config(example_path, add)
        _check_models(example_path, bool(spec["needs_models"]), add)
        _check_migrations(example_path, bool(spec["needs_migrations"]), add)
        _check_imports(example_path, list(spec["import_modules"]), add)
        _check_secrets(example_path, add)

    summary = _summarize(results)
    if summary["errors"]:
        status = "blocked"
    elif summary["warnings"]:
        status = "partial"
    else:
        status = "ready"
    return ExamplesValidationReport(
        ok=status == "ready",
        status=status,
        examples_root=str(examples_root) if examples_root else None,
        examples=results,
        summary=summary,
    )


def scan_path_for_secrets(path: str | Path) -> list[dict[str, Any]]:
    root = Path(path)
    findings: list[dict[str, Any]] = []
    files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
    for file_path in files:
        if "__pycache__" in file_path.parts or file_path.suffix == ".pyc":
            continue
        if file_path.suffix and file_path.suffix not in TEXT_SUFFIXES:
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for pattern in SECRET_PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue
                value = match.group(1) if match.groups() else match.group(0)
                if _is_placeholder_secret(value):
                    continue
                findings.append(
                    {
                        "path": str(file_path),
                        "line": line_no,
                        "pattern": pattern.pattern,
                    }
                )
    return findings


def _check_readme(example_path: Path, add) -> None:
    readme = example_path / "README.md"
    if not readme.exists():
        add("readme", "error", "README missing", "Add README.md")
        return

    text = readme.read_text(encoding="utf-8")
    add("readme", "ok", "README found")

    required_fragments = {
        "run": "aksara dev",
        "migrate": "aksara migrate",
        "studio": "/studio/ui",
        "mcp": "/ai/tools/mcp",
        "seed": "seed",
        "ai_console": "AI Console",
    }
    for check_name, fragment in required_fragments.items():
        if fragment.lower() in text.lower():
            add(f"readme_{check_name}", "ok", f"README documents {check_name.replace('_', ' ')}")
        else:
            add(
                f"readme_{check_name}",
                "warning",
                f"README does not document {check_name.replace('_', ' ')}",
                f"Add a {check_name.replace('_', ' ')} section",
            )


def _check_project_config(example_path: Path, add) -> None:
    config_files = ["settings.py", "main.py", "pyproject.toml"]
    found = [name for name in config_files if (example_path / name).exists()]
    if found:
        add("project_config", "ok", "project/app config found", files=found)
    else:
        add("project_config", "error", "project/app config missing", "Add settings.py and main.py")


def _check_models(example_path: Path, required: bool, add) -> None:
    models = example_path / "models.py"
    if models.exists():
        add("models", "ok", "models found")
    elif required:
        add("models", "error", "models.py missing", "Add models.py for this example")
    else:
        add("models", "skipped", "models not required for this provider wiring example")


def _check_migrations(example_path: Path, required: bool, add) -> None:
    migrations = example_path / "migrations"
    if not required:
        add("migrations", "skipped", "migrations not required for this example")
        return
    if not migrations.exists():
        add("migrations", "error", "migration path missing", "Add migrations/")
        return
    add("migrations", "ok", "migration path found")


def _check_imports(example_path: Path, module_stems: list[str], add) -> None:
    package_name = _package_name(example_path)
    base_path = _import_base_path(example_path)
    failures: list[str] = []
    with _temporary_sys_path(base_path):
        for stem in module_stems:
            module_name = f"{package_name}.{stem}" if package_name else stem
            try:
                importlib.import_module(module_name)
            except Exception as exc:
                failures.append(f"{module_name}: {exc!r}")
    if failures:
        add("imports", "error", "project import failed", "Fix import errors", failures=failures)
    else:
        add("imports", "ok", "project imports")


def _check_secrets(example_path: Path, add) -> None:
    findings = scan_path_for_secrets(example_path)
    if findings:
        add(
            "secrets",
            "error",
            "possible committed secret found",
            "Replace real secrets with placeholders",
            findings=findings,
        )
    else:
        add("secrets", "ok", "no obvious secrets committed")


def _is_placeholder_secret(value: str) -> bool:
    normalized = value.strip().strip("'\"").lower()
    if normalized in PLACEHOLDER_TOKENS:
        return True
    if "your" in normalized or "placeholder" in normalized or "example" in normalized:
        return True
    if normalized.endswith("...") or normalized in {"...", "sk-"}:
        return True
    if any(char in normalized for char in "(){}[]"):
        return True
    if normalized.startswith(("hash_", "fields.", "field.", "os.getenv")):
        return True
    return False


def _summarize(results: list[ExampleValidationResult]) -> dict[str, int]:
    summary = {"ok": 0, "warnings": 0, "errors": 0, "skipped": 0}
    for result in results:
        for check in result.checks:
            if check.status == "ok":
                summary["ok"] += 1
            elif check.status == "warning":
                summary["warnings"] += 1
            elif check.status == "error":
                summary["errors"] += 1
            elif check.status == "skipped":
                summary["skipped"] += 1
    return summary


def _package_name(example_path: Path) -> str | None:
    parts: list[str] = []
    cursor = example_path
    while (cursor / "__init__.py").exists():
        parts.insert(0, cursor.name)
        cursor = cursor.parent
    return ".".join(parts) if parts else None


def _import_base_path(example_path: Path) -> Path:
    cursor = example_path
    while (cursor / "__init__.py").exists():
        cursor = cursor.parent
    return cursor


@contextmanager
def _temporary_sys_path(path: Path):
    value = str(path)
    added = value not in sys.path
    if added:
        sys.path.insert(0, value)
    try:
        yield
    finally:
        if added:
            try:
                sys.path.remove(value)
            except ValueError:
                pass
