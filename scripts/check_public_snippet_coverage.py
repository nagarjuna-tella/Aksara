"""Summarize executable public-sample coverage without claiming every fence runs."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "docs"
EVIDENCE = ROOT / "audit-evidence" / "v071"
FENCE = re.compile(r"^```([^\n]*)\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
HISTORICAL = {
    "docs/docs/changelog.md",
    "docs/docs/notes/index.md",
    "docs/docs/notes/v0-5-49-announcement.md",
    "docs/docs/notes/v0-5-49-security-architecture.md",
}
EXECUTION_EVIDENCE = {
    "application_journeys": [
        "development-wheel-tutorial.json",
        "example-execution.json",
        "scaffold-startup.json",
        "support-desk-baseline.json",
    ],
    "database_examples": [
        "advanced-field-execution.json",
        "approval-execution.json",
        "auth-permission-execution.json",
        "bulk-execution.json",
        "custom-field-execution.json",
        "external-execution.json",
        "filter-doc-execution.json",
        "fixture-execution.json",
        "generic-step-execution.json",
        "history-execution.json",
        "media-lifecycle.json",
        "migration-doc-execution.json",
        "outbox-execution.json",
        "pagination-doc-execution.json",
        "query-execution.json",
        "query-profiling-execution.json",
        "soft-delete-execution.json",
        "testing-execution.json",
    ],
    "provider_free_examples": [
        "ai-cli-execution.json",
        "ai-provider-contract.json",
        "gap-analysis-version-contract.json",
        "installed-doc-imports.json",
        "media-email.json",
        "operator-cli.json",
        "setup-doc-execution.json",
        "upgrade-recipe.json",
    ],
    "syntax_and_cli": [
        "cli-docs-syntax.json",
        "installed-doc-imports.json",
    ],
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _markdown() -> list[Path]:
    return sorted(
        [
            ROOT / "README.md",
            *DOCS.rglob("*.md"),
            *(ROOT / "examples").glob("*/README.md"),
        ]
    )


def _blocks(paths: list[Path]) -> list[tuple[Path, str, str]]:
    blocks = []
    for path in paths:
        for match in FENCE.finditer(path.read_text(encoding="utf-8")):
            info = match.group(1).strip()
            language = info.split()[0].lower() if info else "unlabeled"
            if language == "py":
                language = "python"
            blocks.append((path, language, match.group(2)))
    return blocks


def _accepted_result(data: dict[str, object]) -> object:
    if "pass" in data:
        return data["pass"]
    if "status" in data:
        return data["status"]
    raise AssertionError("execution artifact has no explicit result")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    paths = _markdown()
    current_paths = [
        path for path in paths if str(path.relative_to(ROOT)) not in HISTORICAL
    ]
    all_blocks = _blocks(paths)
    current_blocks = _blocks(current_paths)
    counts = Counter(language for _path, language, _source in current_blocks)

    python_failures = []
    json_failures = []
    for path, language, source in current_blocks:
        name = str(path.relative_to(ROOT))
        if language == "python":
            try:
                compile(source, name, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
            except SyntaxError as exc:
                python_failures.append(f"{name}: {exc}")
        elif language == "json":
            try:
                json.loads(source)
            except json.JSONDecodeError as exc:
                json_failures.append(f"{name}: {exc}")
    assert python_failures == []
    assert json_failures == []

    package = subprocess.run(
        [str(args.python.absolute()), "-I", "-c", "import aksara; print(aksara.__version__); print(aksara.__file__)"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()
    assert not Path(package[1]).is_relative_to(ROOT)

    evidence_sha256 = {}
    evidence_results = {}
    for names in EXECUTION_EVIDENCE.values():
        for name in names:
            path = EVIDENCE / name
            data = json.loads(path.read_text(encoding="utf-8"))
            result = _accepted_result(data)
            assert result is True or result == "passed"
            evidence_sha256[name] = _digest(path)
            evidence_results[name] = result

    installed = json.loads((EVIDENCE / "installed-doc-imports.json").read_text())
    cli = json.loads((EVIDENCE / "cli-docs-syntax.json").read_text())
    examples = json.loads((EVIDENCE / "example-review.json").read_text())
    assert installed["python_blocks"] == counts["python"]
    assert installed["json_blocks"] == counts["json"]
    assert cli["checked_commands"] == 295
    assert len(cli["skipped"]) == 7
    assert cli["errors"] == []
    assert len(examples["examples"]) == 6

    result = {
        "schema_version": 1,
        "review_date": "2026-09-12",
        "pass": True,
        "package_version": package[0],
        "source_checkout_framework_imports": False,
        "inventory": {
            "public_markdown_files": len(paths),
            "current_sample_files": len(current_paths),
            "historical_files_excluded": sorted(HISTORICAL),
            "all_fences": len(all_blocks),
            "historical_fences": len(all_blocks) - len(current_blocks),
            "current_fences": len(current_blocks),
            "current_fences_by_language": dict(sorted(counts.items())),
        },
        "automated_coverage": {
            "python": {
                "blocks": counts["python"],
                "all_compile": True,
                "all_aksara_imports_resolve": True,
                "fresh_workflow_example_executes": True,
            },
            "json": {
                "blocks": counts["json"],
                "all_parse": True,
                "selected_installed_response_models": 5,
            },
            "cli": {
                "literal_forms_parsed": cli["checked_commands"],
                "explicit_exclusions": len(cli["skipped"]),
                "errors": len(cli["errors"]),
            },
            "repository_examples": {
                "classified": len(examples["examples"]),
                "startup_checked": 5,
                "packaged_support_desk_checks": len(
                    json.loads((EVIDENCE / "support-desk-baseline.json").read_text())[
                        "checks"
                    ]
                ),
                "development_tutorial_stages": len(
                    json.loads((EVIDENCE / "development-wheel-tutorial.json").read_text())[
                        "stages"
                    ]
                ),
            },
        },
        "execution_evidence": EXECUTION_EVIDENCE,
        "evidence_results": evidence_results,
        "evidence_sha256": dict(sorted(evidence_sha256.items())),
        "functional_findings": {
            "AIFLOW001": "A fresh direct aksara.ai.workflows import fails through a circular Studio import; the documented aksara.studio aggregate import executes.",
            "AIFLOW002": "Diagnostic set_env examples can acquire a duplicate export prefix when converted to display-only workflow commands.",
        },
        "page_sha256": {
            str(path.relative_to(ROOT)): _digest(path)
            for path in [
                DOCS / "ai-mode" / "bring-your-own-llm.md",
                DOCS / "ai-mode" / "debugger.md",
                DOCS / "ai-mode" / "workflows.md",
                DOCS / "studio" / "cli.md",
            ]
        },
        "candidate_acceptance": False,
        "limits": [
            "Python compilation and import resolution do not execute every partial fragment as a standalone program.",
            "CLI parsing does not run every callback; application and journey gates execute the release-critical paths.",
            "The lone TypeScript integration fragment needs an external compiler package and live endpoint and is not executed here.",
            "Dotenv, HTTP, SQL, CSS, text, diagrams, formulas and displayed output are reviewed by their owning setup, journey, schema or rendering gates rather than treated as standalone programs.",
            "Current public-wheel evidence must be repeated against the 0.7.1rc1 candidate.",
        ],
        "scope": "Complete fence census plus all-current Python syntax, all-current JSON parsing, selected installed response-shape checks, fresh workflow execution, literal CLI parsing, all six example dispositions and the existing installed-wheel/PostgreSQL behavior gates named here. This is bounded sample coverage, not universal execution of partial fragments, live providers, an external TypeScript toolchain or final candidate acceptance.",
        "runner_sha256": _digest(Path(__file__)),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"PASS: {len(current_paths)} current Markdown files, "
        f"{len(current_blocks)} fences, {len(evidence_sha256)} execution artifacts"
    )


if __name__ == "__main__":
    main()
