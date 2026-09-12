"""Keep experimental provider guidance tied to installed-wheel evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ai_provider_contract_evidence_is_current():
    evidence_path = ROOT / "audit-evidence/v071/ai-provider-contract.json"
    evidence = json.loads(evidence_path.read_text())
    assert evidence["pass"] is True
    assert evidence["source_checkout_framework_imports"] is False
    assert all(evidence["checks"].values())
    for field in ("page_sha256", "source_sha256"):
        for name, digest in evidence[field].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert evidence["runner_sha256"] == hashlib.sha256(
        (ROOT / "scripts/check_ai_provider_contract.py").read_bytes()
    ).hexdigest()


def test_ai_provider_pages_use_loaded_environment_names_and_adapter_defaults():
    ollama = (ROOT / "docs/docs/ai-mode/ollama.md").read_text()
    custom = (ROOT / "docs/docs/ai-mode/custom-http.md").read_text()
    providers = (ROOT / "docs/docs/ai-mode/providers.md").read_text()
    cli = (ROOT / "aksara/cli/main.py").read_text()

    assert "OLLAMA_BASE_URL" in ollama
    assert "OLLAMA_HOST" not in ollama
    assert "CUSTOM_LLM_BASE_URL" in custom
    assert "CUSTOM_LLM_API_KEY" in custom
    assert "AKSARA_CUSTOM_LLM_" not in custom
    assert "`/v1/completions`" in custom
    assert "| `response_field` | `text` |" in custom
    assert "default local Ollama profile" in providers
    assert "keyless custom endpoint" in providers
    assert 'click.echo("    OLLAMA_BASE_URL' in cli
    assert 'click.echo("    CUSTOM_LLM_BASE_URL' in cli
