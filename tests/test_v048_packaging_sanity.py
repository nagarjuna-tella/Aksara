from __future__ import annotations

import tomllib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", ["README.md", "LICENSE", "pyproject.toml"])
def test_public_metadata_files_exist(path):
    assert (ROOT / path).is_file()


@pytest.mark.parametrize(
    "path",
    [
        "aksara/studio/static/index.html",
        "aksara/studio/static/app.js",
        "aksara/studio/static/styles.css",
        "aksara/studio/static/icons/aksara-logo.svg",
    ],
)
def test_studio_static_assets_exist(path):
    assert (ROOT / path).is_file()


@pytest.mark.parametrize(
    "path",
    [
        "examples/basic_app/README.md",
        "examples/blog/README.md",
        "examples/crm/README.md",
        "examples/multitenant/README.md",
        "examples/ai_providers/README.md",
    ],
)
def test_examples_in_source_tree(path):
    assert (ROOT / path).is_file()


def test_wheel_packages_aksara_package():
    pyproject = _pyproject()
    assert pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["aksara"]


def test_wheel_force_includes_examples():
    force_include = _pyproject()["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert force_include["examples"] == "aksara/_examples"


@pytest.mark.parametrize("path", ["/aksara", "/aksara/studio/static/**/*", "/examples", "/docs/docs", "/README.md", "/LICENSE"])
def test_sdist_includes_public_assets(path):
    include = _pyproject()["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    assert path in include


def test_project_version_matches_runtime():
    from aksara._version import __version__
    assert _pyproject()["project"]["version"] == __version__


def test_console_script_points_to_cli():
    assert _pyproject()["project"]["scripts"]["aksara"] == "aksara.cli:main"


@pytest.mark.parametrize(
    "dependency",
    ["fastapi", "asyncpg", "click", "uvicorn", "python-dotenv", "pyyaml"],
)
def test_runtime_dependencies_include_launch_path_needs(dependency):
    deps = "\n".join(_pyproject()["project"]["dependencies"])
    assert dependency in deps


@pytest.mark.parametrize("path", ["aksara/cli/scaffold.py", "aksara/cli/templates/__init__.py"])
def test_project_template_helpers_exist(path):
    assert (ROOT / path).is_file()


@pytest.mark.parametrize(
    "fragment",
    [
        "get_examples_path",
        "aksara/_examples",
        "examples/blog",
        "examples/crm",
        "examples/multitenant",
    ],
)
def test_template_module_documents_bundled_examples(fragment):
    text = (ROOT / "aksara" / "cli" / "templates" / "__init__.py").read_text(encoding="utf-8")
    assert fragment in text


@pytest.mark.parametrize("fragment", ["v0.7.0", "aksara-framework>=0.7.0"])
def test_scaffold_template_version_is_current(fragment):
    text = (ROOT / "aksara" / "cli" / "scaffold.py").read_text(encoding="utf-8")
    assert fragment in text
