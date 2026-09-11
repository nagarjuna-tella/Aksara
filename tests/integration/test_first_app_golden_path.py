from __future__ import annotations

from aksara.routing import iter_routes

import importlib
import sys
from pathlib import Path

import pytest

from aksara.examples_validation import validate_examples
from aksara.launch_check import run_launch_check


ROOT = Path(__file__).resolve().parents[2]


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


@pytest.mark.parametrize("module", ["examples.basic_app", "examples.blog", "examples.crm", "examples.multitenant", "examples.ai_providers"])
def test_example_packages_can_be_discovered(module):
    assert importlib.import_module(module)


@pytest.mark.parametrize(
    "module",
    [
        "examples.basic_app.models",
        "examples.blog.models",
        "examples.crm.models",
        "examples.multitenant.models",
    ],
)
def test_model_examples_can_import_models(module):
    assert importlib.import_module(module)


def test_basic_app_imports_and_registers_routes():
    app_module = importlib.import_module("examples.basic_app.main")
    app = app_module.app
    paths = {route.path for route in iter_routes(app)}
    assert "/api/users/" in paths
    assert "/api/posts/" in paths
    assert "/studio/ui" in paths
    assert "/ai/tools/mcp" in paths


def test_basic_app_models_are_registered():
    importlib.import_module("examples.basic_app.main")
    from aksara.registry import get_models

    names = {model.__name__ for model in get_models()}
    assert {"User", "Post", "Article"}.issubset(names)


def test_first_app_launch_check_smoke():
    report = run_launch_check(ROOT / "examples" / "basic_app", check_database=False)
    assert report.version == "0.7.0"
    assert any(check.name == "studio_ui" and check.status == "ok" for check in report.checks)
    assert any(check.name == "mcp_catalog" and check.status == "ok" for check in report.checks)


def test_examples_validation_smoke():
    report = validate_examples(ROOT)
    assert report.ok is True
    assert {example.name for example in report.examples} == {
        "basic_app",
        "blog",
        "crm",
        "multitenant",
        "support_desk",
        "ai_providers",
    }
