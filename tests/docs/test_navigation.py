"""Reader routes must reach real pages without mixing onboarding and AI internals."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/docs"


def _navigation():
    # Parse only navigation; the full config contains a MkDocs Python YAML tag.
    source = (ROOT / "docs/mkdocs.yml").read_text()
    section = source.split("nav:\n", 1)[1].split("\nplugins:", 1)[0]
    return yaml.safe_load("nav:\n" + section)["nav"]


def _destinations(value):
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        value = value.values()
    return set().union(*(_destinations(child) for child in value))


def test_navigation_destinations_exist():
    for destination in _destinations(_navigation()):
        assert (DOCS / destination).is_file(), destination


def test_reader_journeys_are_separated_and_reachable():
    groups = {key: value for entry in _navigation() for key, value in entry.items()}
    start = _destinations(groups["Start"])
    assert {
        "getting-started/first-project.md",
        "tutorials/ticket-desk.md",
        "tutorials/ticket-desk-tenancy.md",
        "tutorials/ticket-desk-reports.md",
        "tutorials/ticket-desk-durable.md",
        "tutorials/ticket-desk-mcp.md",
    } <= start
    assert not any(path.startswith(("ai-mode/", "studio/")) for path in start)
    assert {"getting-started/mcp.md", "ai-mode/mcp.md"} <= _destinations(groups["MCP"])
    assert {
        "tutorials/deployment.md", "operations/upgrade-v07.md", "diagnostics.md"
    } <= _destinations(groups["Operate"])
    assert "studio/index.md" in _destinations(groups["Experimental"])
    assert "ai-mode/context-engine.md" in _destinations(groups["Contribute"])
