from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from aksara.cli.main import cli
from aksara.examples_validation import EXAMPLE_SPECS, scan_path_for_secrets, validate_examples


ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


def _clear_example_import_state() -> None:
    for module_name in list(sys.modules):
        if module_name == "examples" or module_name.startswith("examples."):
            sys.modules.pop(module_name, None)


@pytest.fixture(autouse=True)
def _isolate_example_registries():
    from aksara.api.schemas import clear_schema_cache
    from aksara.registry import ModelRegistry
    from aksara.relations import RelationRegistry

    ModelRegistry.clear()
    RelationRegistry.clear()
    clear_schema_cache()
    _clear_example_import_state()
    yield
    ModelRegistry.clear()
    RelationRegistry.clear()
    clear_schema_cache()
    _clear_example_import_state()


@pytest.mark.parametrize("example", ["basic_app", "blog", "crm", "multitenant", "ai_providers"])
def test_required_examples_exist(example):
    assert (EXAMPLES / example).is_dir()


@pytest.mark.parametrize("example", EXAMPLE_SPECS.keys())
def test_each_example_has_readme(example):
    assert (EXAMPLES / example / "README.md").is_file()


@pytest.mark.parametrize("example", EXAMPLE_SPECS.keys())
@pytest.mark.parametrize(
    "fragment",
    [
        "aksara doctor launch-check",
        "aksara migrate",
        "aksara dev",
        "/studio/ui",
        "/ai/tools/mcp",
        "AI Console",
        "Seed",
    ],
)
def test_example_readmes_cover_golden_path(example, fragment):
    text = (EXAMPLES / example / "README.md").read_text(encoding="utf-8")
    assert fragment.lower() in text.lower()


@pytest.mark.parametrize("example", ["basic_app", "blog", "crm", "multitenant"])
def test_model_examples_have_models_and_migrations(example):
    path = EXAMPLES / example
    assert (path / "models.py").is_file()
    assert (path / "migrations").is_dir()


@pytest.mark.parametrize("example", EXAMPLE_SPECS.keys())
def test_examples_have_project_config(example):
    path = EXAMPLES / example
    assert (path / "settings.py").is_file()
    assert (path / "main.py").is_file()


def test_validate_examples_ready():
    report = validate_examples(ROOT)
    assert report.ok is True
    assert report.status == "ready"
    assert report.summary["errors"] == 0
    assert report.summary["warnings"] == 0


def test_validate_examples_json_shape():
    report = validate_examples(ROOT)
    data = json.loads(report.to_json())
    assert data["ok"] is True
    assert data["examples_root"].endswith("examples")
    assert len(data["examples"]) == len(EXAMPLE_SPECS)


def test_validate_examples_cli_pretty():
    result = CliRunner().invoke(cli, ["examples", "validate"])
    assert result.exit_code == 0
    assert "Aksara Examples Validation" in result.output
    assert "basic_app" in result.output
    assert "Result: READY" in result.output


def test_validate_examples_cli_json_is_pure():
    result = CliRunner().invoke(cli, ["examples", "validate", "--format", "json"])
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    data = json.loads(result.output)
    assert data["status"] == "ready"


@pytest.mark.parametrize(
    "placeholder",
    [
        "OPENAI_API_KEY=<OPENAI_API_KEY>",
        "ANTHROPIC_API_KEY=your-api-key",
        "AZURE_OPENAI_API_KEY=<AZURE_OPENAI_API_KEY>",
    ],
)
def test_secret_scan_allows_placeholders(tmp_path, placeholder):
    file_path = tmp_path / "README.md"
    file_path.write_text(placeholder, encoding="utf-8")
    assert scan_path_for_secrets(tmp_path) == []


@pytest.mark.parametrize(
    ("env_name", "value"),
    [
        ("OPENAI_API_KEY", "sk-" + "abcdefghijklmnopqrstuvwxyz123456"),
        ("ANTHROPIC_API_KEY", "sk-ant-" + "abcdefghijklmnopqrstuvwxyz123456"),
        ("AZURE_OPENAI_API_KEY", "abcdefghijklmnopqrstuvwxyz123456"),
        ("password", "super-secret-password-value"),
    ],
)
def test_secret_scan_detects_actual_looking_values(tmp_path, env_name, value):
    file_path = tmp_path / "leak.md"
    file_path.write_text(f"{env_name}={value}", encoding="utf-8")
    findings = scan_path_for_secrets(tmp_path)
    assert findings
    assert findings[0]["path"].endswith("leak.md")


@pytest.mark.parametrize("example", EXAMPLE_SPECS.keys())
def test_no_obvious_secrets_in_examples(example):
    assert scan_path_for_secrets(EXAMPLES / example) == []


@pytest.mark.parametrize("example", EXAMPLE_SPECS.keys())
def test_validation_report_contains_import_check(example):
    report = validate_examples(ROOT)
    result = next(item for item in report.examples if item.name == example)
    assert any(check.name == "imports" for check in result.checks)


@pytest.mark.parametrize("example", EXAMPLE_SPECS.keys())
def test_validation_report_contains_secret_check(example):
    report = validate_examples(ROOT)
    result = next(item for item in report.examples if item.name == example)
    assert any(check.name == "secrets" and check.status == "ok" for check in result.checks)
