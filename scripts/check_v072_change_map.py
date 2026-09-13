"""Verify every v0.7.2 production change maps to the audit-closure ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "a0422cf8fa004b41a2ccdaa9aa91c8036357159d"
ISSUES = {
    "CFG-001", "SDK-001", "STORAGE-001", "ACTION-001", "TASK-001",
    "AIPROVIDER001", "GAP001", "AIFLOW001", "AIFLOW002", "EX-001",
    "SCAFFOLD-001", "SOFTDELETE001", "FIXTURE001", "FIXTURE002",
    "FIXTURE003", "INSPECTOR001", "ADMINWIDGET001", "MIGRATION-001",
    "RELATION001", "BULK-001", "PAGINATION-001", "TESTING-001",
}


def entry(issue_ids: list[str], symbols: list[str], reason: str, impact: str, tests: list[str]) -> dict:
    return {
        "issue_ids": issue_ids,
        "functions_or_classes": symbols,
        "reason": reason,
        "compatibility_impact": impact,
        "tests": tests,
    }


MAP = {
    "aksara/_version.py": entry(sorted(ISSUES), ["__version__"], "Candidate identity after closing the complete 22-item ledger.", "Version metadata only.", ["tests/test_v048_packaging_sanity.py"]),
    "aksara/ai/hub_settings.py": entry(["AIPROVIDER001"], ["provider status serialization"], "Report explicit configuration independently from adapter defaults and reachability.", "Corrects experimental status reporting.", ["tests/ai/test_v072_provider_configuration.py"]),
    "aksara/ai/providers_unified.py": entry(["AIPROVIDER001"], ["ProviderConfig", "provider detection"], "Require explicit, valid provider configuration.", "Malformed URLs fail clearly; defaults no longer imply configured.", ["tests/ai/test_v072_provider_configuration.py"]),
    "aksara/ai/workflows.py": entry(["AIFLOW001", "AIFLOW002"], ["workflow imports", "_render_set_env_command"], "Break the import cycle and use the canonical environment-command renderer.", "Public import order now works; malformed duplicated export prefixes are normalized.", ["tests/ai/test_v072_workflow_boundaries.py"]),
    "aksara/api/pagination.py": entry(["PAGINATION-001"], ["pagination response models"], "Preserve paginator-specific metadata in runtime responses and OpenAPI.", "Adds previously dropped response metadata.", ["tests/api/test_v072_pagination_contract.py"]),
    "aksara/api/router.py": entry(["ACTION-001", "PAGINATION-001"], ["route generation", "custom action dispatch"], "Enforce declared permissions for custom actions and select paginator-specific response models.", "Unauthorized custom actions now fail closed; response schemas become accurate.", ["tests/api/test_actions.py", "tests/api/test_v072_pagination_contract.py"]),
    "aksara/api/viewsets.py": entry(["ACTION-001"], ["action", "ModelViewSet custom actions"], "Define deterministic ViewSet and action permission precedence.", "Calls that previously bypassed declared permissions are denied.", ["tests/api/test_actions.py"]),
    "aksara/cli/main.py": entry(["MIGRATION-001", "TASK-001", "SCAFFOLD-001", "AIFLOW002"], ["inspect_models", "tasks_reenqueue", "startproject", "doctor rendering"], "Expose collision errors, clear ownership fields on re-enqueue, guide valid scaffold installs, and render environment actions canonically.", "Ambiguity and authorization-sensitive state now fail clearly; documented scaffold workflow succeeds.", ["tests/test_v072_registry.py", "tests/test_v072_task_ownership.py", "tests/cli/test_dev_tools.py", "tests/ai/test_v072_workflow_boundaries.py"]),
    "aksara/cli/scaffold.py": entry(["SCAFFOLD-001"], ["project pyproject templates", "README templates"], "Generate explicit package selection and candidate guidance.", "Generated projects support editable and wheel installation.", ["tests/dx/test_scaffold_importable.py", "scripts/run_v072_scaffold_gate.py"]),
    "aksara/cli/templates/__init__.py": entry(["SCAFFOLD-001"], ["copy_template_project", "get_flat_project_pyproject_template"], "Give all domain templates intentional package metadata.", "Domain scaffolds become installable Python projects.", ["scripts/run_v072_scaffold_gate.py"]),
    "aksara/conf.py": entry(["CFG-001"], ["_parse_list"], "Replace platform path-separator parsing with a deterministic list grammar.", "Ambiguous input is rejected instead of silently split.", ["tests/test_v072_configuration.py"]),
    "aksara/contrib/admin/widgets/array.py": entry(["ADMINWIDGET001"], ["ArrayAdminWidget.render"], "Copy caller values before adding visual rows.", "Rendering no longer mutates application data.", ["tests/admin/test_v072_array_widget.py"]),
    "aksara/contrib/soft_delete.py": entry(["SOFTDELETE001"], ["with_deleted", "only_deleted"], "Transform the supplied queryset rather than replacing it.", "Existing predicates, tenant scope, ordering and limits are preserved.", ["tests/test_soft_delete.py", "tests/security/test_v072_soft_delete_rls.py"]),
    "aksara/core/migrations/0003_task_claim_ownership.py": entry(["TASK-001"], ["Migration"], "Add ordinary-task owner, token and lease columns and claim index.", "Additive internal schema migration for v0.7.1 task rows.", ["tests/migrations/test_v072_task_ownership.py"]),
    "aksara/diagnostics.py": entry(["AIFLOW002"], ["DiagnosticAction", "render_set_env_command"], "Store raw values and centralize shell-display rendering.", "Legacy already-formatted values remain readable; new output is syntactically coherent.", ["tests/ai/test_v072_workflow_boundaries.py"]),
    "aksara/fields.py": entry(["MIGRATION-001"], ["ForeignKey", "ManyToMany"], "Propagate ambiguous registry identity rather than silently guessing a table.", "Unambiguous legacy names work; collisions fail explicitly.", ["tests/test_v072_registry.py"]),
    "aksara/fixtures.py": entry(["FIXTURE001", "FIXTURE002", "FIXTURE003"], ["dump_database", "dump_model", "load_fixture"], "Use canonical registry values, restore missing explicit identities, and emit portable YAML scalars.", "Exported JSON/YAML fixtures round-trip; conflicts remain explicit.", ["tests/test_v072_fixtures.py"]),
    "aksara/gapanalysis.py": entry(["GAP001"], ["environment compatibility checks"], "Read the authoritative supported Python boundary.", "Python 3.10 is correctly rejected.", ["tests/test_gapanalysis.py", "tests/test_runtime_compatibility.py"]),
    "aksara/inspectors/__init__.py": entry(["INSPECTOR001"], ["explain_query", "explain_query_async"], "Export explicit live and fallback query inspection APIs.", "Results expose provenance and whether ANALYZE ran.", ["tests/inspectors/test_v072_query_provenance.py"]),
    "aksara/inspectors/queries.py": entry(["INSPECTOR001"], ["QueryPlan", "explain_query", "explain_query_async"], "Separate live execution from synthetic estimates and retain warnings.", "Synthetic output cannot be read as measured ANALYZE.", ["tests/inspectors/test_v072_query_provenance.py"]),
    "aksara/launch_check.py": entry(["GAP001", "SCAFFOLD-001"], ["launch compatibility checks"], "Use one Python support policy and validate generated packaging guidance.", "Unsupported future Python versions are explicit.", ["tests/test_v048_launch_check.py", "tests/test_runtime_compatibility.py"]),
    "aksara/manager.py": entry(["SOFTDELETE001", "RELATION001", "BULK-001"], ["QuerySet._clone", "QuerySet.first", "Manager.bulk_update"], "Preserve query semantics, eager-load terminal first results, and cast CASE values by field type.", "Correctness tightening with no signature change.", ["tests/test_soft_delete.py", "tests/test_relations.py", "tests/test_v072_bulk_update.py"]),
    "aksara/migrations/autodetector.py": entry(["MIGRATION-001"], ["MigrationAutodetector"], "Use canonical model identities and reject ambiguity.", "Migration generation can no longer silently omit a colliding model.", ["tests/test_v072_registry.py"]),
    "aksara/model/base.py": entry(["MIGRATION-001"], ["ModelMeta"], "Register qualified model identity while preserving unambiguous simple lookup.", "Same-name collisions become explicit.", ["tests/test_v072_registry.py"]),
    "aksara/registry.py": entry(["MIGRATION-001", "FIXTURE003"], ["ModelRegistry", "AmbiguousModelError"], "Make qualified module/class identity canonical and enumerate model classes.", "Unambiguous simple names remain compatible; ambiguous names fail deterministically.", ["tests/test_v072_registry.py", "tests/test_v072_fixtures.py"]),
    "aksara/runtime_compatibility.py": entry(["GAP001"], ["MIN_PYTHON", "MAX_PYTHON", "python_support"], "Centralize the supported Python 3.11 through 3.14 policy.", "Future unsupported interpreters are classified explicitly.", ["tests/test_runtime_compatibility.py"]),
    "aksara/sdk/typescript.py": entry(["SDK-001", "PAGINATION-001"], ["TypeScriptGenerator", "QueryValue", "pagination types"], "Generate strict-compatible query parameters and match paginator response metadata.", "Generated types become usable without any suppression.", ["tests/api/test_typescript_sdk.py", "scripts/run_v072_typescript_sdk_gate.py"]),
    "aksara/storage.py": entry(["STORAGE-001"], ["FileSystemStorage", "_resolve_path"], "Apply component-aware resolved containment to every filesystem operation.", "Traversal and outward symlinks are rejected.", ["tests/test_storage.py"]),
    "aksara/studio/fastapi.py": entry(["INSPECTOR001"], ["query inspection endpoint"], "Await the live database inspection path.", "Studio reports actual execution provenance.", ["tests/inspectors/test_v072_query_provenance.py"]),
    "aksara/studio/models.py": entry(["AIFLOW001"], ["workflow model definitions"], "Keep workflow data types independent of workflow builder imports.", "Public imports become order-independent.", ["tests/ai/test_v072_workflow_boundaries.py"]),
    "aksara/studio/utils.py": entry(["AIFLOW001"], ["lazy workflow forwarding"], "Avoid package initialization re-entering a partially imported workflow module.", "Existing public names and signatures remain available.", ["tests/ai/test_v072_workflow_boundaries.py", "scripts/check_v072_installed_boundaries.py"]),
    "aksara/tasks.py": entry(["TASK-001"], ["TaskRecord", "TaskWorker", "claim", "heartbeat", "completion"], "Fence ordinary task ownership with database-time leases and conditional terminal writes.", "Stale workers cannot update authoritative state; task/Operation separation remains.", ["tests/test_v072_task_ownership.py", "tests/test_v072_task_processes.py"]),
    "aksara/testing.py": entry(["TESTING-001"], ["test_database"], "Pin same-task database activity to the owned rollback transaction and tear down resources.", "Documented rollback isolation now holds within its stated boundary.", ["tests/test_v072_testing_database.py"]),
    "examples/multitenant/middleware.py": entry(["EX-001"], ["TenantMiddleware._is_exempt_path"], "Use exact exemptions and explicit subtree prefixes.", "Protected routes no longer inherit the root exemption.", ["tests/patterns/test_multitenant_example.py", "scripts/check_v072_installed_boundaries.py"]),
    "examples/support_desk/main.py": entry(sorted(ISSUES), ["app version"], "Identify the packaged reference app as the audit-closure candidate used to validate the ledger.", "Version metadata only.", ["scripts/run_support_desk_gate.py"]),
    "pyproject.toml": entry(["GAP001", "SCAFFOLD-001"], ["project.version", "project.requires-python"], "Publish the candidate identity and enforce the documented Python 3.11 through 3.14 range.", "Python 3.15 and later require an explicit future compatibility decision; runtime dependencies are unchanged.", ["tests/test_runtime_compatibility.py", "tests/test_v048_packaging_sanity.py"]),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    names = subprocess.check_output(
        ["git", "diff", "--name-only", BASE, "--", "aksara", "examples", "pyproject.toml"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    production = sorted(
        name for name in names
        if name.startswith("aksara/")
        or (name.startswith("examples/") and name.endswith(".py"))
        or name == "pyproject.toml"
    )
    assert production == sorted(MAP), {
        "missing": sorted(set(production) - set(MAP)),
        "unexpected": sorted(set(MAP) - set(production)),
    }
    for path, item in MAP.items():
        assert item["issue_ids"] and set(item["issue_ids"]) <= ISSUES, path
        assert item["tests"], path

    before = tomllib.loads(subprocess.check_output(
        ["git", "show", f"{BASE}:pyproject.toml"], cwd=ROOT, text=True
    ))
    after = tomllib.loads((ROOT / "pyproject.toml").read_text())
    dependency_keys = ("dependencies", "optional-dependencies")
    dependencies_unchanged = all(
        before["project"].get(key) == after["project"].get(key)
        for key in dependency_keys
    )
    assert dependencies_unchanged
    assert before["project"]["requires-python"] == ">=3.11"
    assert after["project"]["requires-python"] == ">=3.11,<3.15"

    output = {
        "schema_version": 1,
        "pass": True,
        "base": BASE,
        "candidate_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "changed_production_files": MAP,
        "changed_production_file_count": len(MAP),
        "runtime_logic_changed": True,
        "runtime_changes_limited_to_22_findings": True,
        "dependencies_changed": False,
        "requires_python_changed_for_gap001": True,
        "schema_migrations_changed": ["aksara/core/migrations/0003_task_claim_ownership.py"],
        "schema_change_issue": "TASK-001",
        "unmapped_production_files": [],
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(f"PASS: {len(MAP)} production/package files map to the 22-item ledger; dependencies unchanged")


if __name__ == "__main__":
    main()
