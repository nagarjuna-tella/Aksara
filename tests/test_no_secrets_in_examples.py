from __future__ import annotations

from pathlib import Path

import pytest

from aksara.examples_validation import scan_path_for_secrets


ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("path", ["README.md", "docs/docs", "examples"])
def test_public_docs_and_examples_have_no_obvious_secrets(path):
    assert scan_path_for_secrets(ROOT / path) == []


@pytest.mark.parametrize(
    "placeholder",
    [
        "OPENAI_API_KEY=your-key-here",
        "ANTHROPIC_API_KEY=your-key-here",
        "AZURE_OPENAI_API_KEY=your-key-here",
        "OPENAI_API_KEY=sk-...",
        "password=placeholder",
    ],
)
def test_secret_scanner_allows_documented_placeholders(tmp_path, placeholder):
    (tmp_path / "doc.md").write_text(placeholder, encoding="utf-8")
    assert scan_path_for_secrets(tmp_path) == []


@pytest.mark.parametrize(
    "secret",
    [
        "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuv1234567890",
        "ANTHROPIC_API_KEY=sk-ant-abcdefghijklmnopqrstuv1234567890",
        "AZURE_OPENAI_API_KEY=abcdefghijklmnopqrstuv1234567890",
    ],
)
def test_secret_scanner_rejects_actual_looking_provider_keys(tmp_path, secret):
    (tmp_path / "doc.md").write_text(secret, encoding="utf-8")
    assert scan_path_for_secrets(tmp_path)
