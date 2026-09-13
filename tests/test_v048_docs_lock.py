from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "docs"


@pytest.mark.parametrize(
    "path",
    [
        "getting-started/installation.md",
        "getting-started/first-project.md",
        "getting-started/studio.md",
        "getting-started/ai-quickstart.md",
        "getting-started/mcp.md",
        "getting-started/examples.md",
        "roadmap.md",
        "changelog.md",
    ],
)
def test_getting_started_docs_exist(path):
    assert (DOCS / path).is_file()


@pytest.mark.parametrize(
    "fragment",
    [
        "What is Aksara?",
        "Why Aksara?",
        "10-Minute Quickstart",
        "Open Studio",
        "Use AI",
        "Use MCP",
        "Examples",
        "Core Features",
        "Roadmap",
        "Contributing",
        "/studio/ui",
        "http://127.0.0.1:8000/mcp/",
        "aksara doctor launch-check",
        "aksara examples validate",
    ],
)
def test_readme_mentions_launch_path(fragment):
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert fragment in text


@pytest.mark.parametrize(
    "fragment",
    [
        "# Roadmap",
        "Where Aksara is now",
        "v0.7 release",
        "Now — v0.7.2 audit closure",
        "v0.7.x maintenance",
        "Next — operating authorized application work",
        "durable authorized operations",
        "Later — supported modeling, integrations and stabilization",
        "Explore — integrations and demand",
        "Not planned",
        "Experimental / deferred",
        "v1.0 readiness",
        "directional, not a promise",
        "Release evidence overrides roadmap assumptions",
        "PostgreSQL",
        "exactly-once",
    ],
)
def test_roadmap_current_and_future_versions(fragment):
    text = (DOCS / "roadmap.md").read_text(encoding="utf-8")
    assert fragment in text


@pytest.mark.parametrize(
    "fragment",
    [
        "Added `aksara doctor launch-check`",
        "Added `aksara examples validate`",
        "Polished golden-path examples",
        "Improved first-user docs",
        "Added packaging sanity tests",
        "Updated roadmap",
        "Improved first-run Studio/AI guidance",
    ],
)
def test_changelog_mentions_v048_items(fragment):
    text = (DOCS / "changelog.md").read_text(encoding="utf-8")
    assert fragment in text


@pytest.mark.parametrize(
    "fragment",
    [
        "http://127.0.0.1:8000/docs",
        "http://127.0.0.1:8000/api/tickets/",
        "IsAuthenticated",
        "Principal.for_user",
        "aksara doctor launch-check",
        "aksara dbsetup",
        "aksara migrate",
        "aksara run main:app",
        "python -m unittest discover -s tests -v",
    ],
)
def test_first_project_doc_includes_first_run_flow(fragment):
    text = (DOCS / "getting-started" / "first-project.md").read_text(encoding="utf-8")
    assert fragment in text


@pytest.mark.parametrize(
    "fragment",
    [
        "aksara ai-hub status",
        "aksara ai-hub configure",
        "ollama serve",
        "ollama pull llama3",
        "Experimental in v0.7.0",
        "MCP generated-tool execution is a",
    ],
)
def test_ai_quickstart_local_first_path(fragment):
    text = (DOCS / "getting-started" / "ai-quickstart.md").read_text(encoding="utf-8")
    assert fragment in text


@pytest.mark.parametrize(
    "fragment",
    [
        "http://127.0.0.1:8000/mcp/",
        "MCP quickstart",
        "Resolve credentials on the server",
        "Streamable HTTP",
        "same application path",
        "ai_sensitive",
        "ai_agent_writable",
    ],
)
def test_mcp_doc_explains_catalog(fragment):
    text = (DOCS / "getting-started" / "mcp.md").read_text(encoding="utf-8")
    assert fragment in text


@pytest.mark.parametrize(
    "fragment",
    [
        "getting-started/first-project.md",
        "getting-started/studio.md",
        "getting-started/ai-quickstart.md",
        "getting-started/mcp.md",
        "getting-started/examples.md",
    ],
)
def test_mkdocs_nav_includes_new_getting_started_docs(fragment):
    text = (ROOT / "docs" / "mkdocs.yml").read_text(encoding="utf-8")
    assert fragment in text
