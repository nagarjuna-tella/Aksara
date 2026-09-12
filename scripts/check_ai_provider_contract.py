"""Verify documented experimental provider configuration from an installed wheel."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    "docs/docs/ai-mode/config.md",
    "docs/docs/ai-mode/custom-http.md",
    "docs/docs/ai-mode/hub.md",
    "docs/docs/ai-mode/index.md",
    "docs/docs/ai-mode/ollama.md",
    "docs/docs/ai-mode/providers.md",
]
SOURCES = [
    "aksara/ai/llm_clients/custom_adapter.py",
    "aksara/ai/providers_unified.py",
    "aksara/cli/main.py",
]
PROBE = r'''
import json
import os
from unittest.mock import patch

import aksara
from click.testing import CliRunner
from aksara.ai.llm_clients.custom_adapter import CustomHttpAdapter
from aksara.ai.providers_unified import UnifiedAiProvider, _detect_provider_from_env
from aksara.cli.main import cli


def clean_provider_environment():
    names = {
        "AKSARA_AI_PROVIDER",
        "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL",
        "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_BASE_URL",
        "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_API_VERSION",
        "OLLAMA_BASE_URL", "OLLAMA_MODEL", "OLLAMA_HOST",
        "CUSTOM_LLM_API_KEY", "CUSTOM_LLM_BASE_URL", "CUSTOM_LLM_MODEL",
        "AKSARA_CUSTOM_LLM_KEY", "AKSARA_CUSTOM_LLM_URL",
        "AKSARA_CUSTOM_LLM_MODEL",
    }
    return {name: os.environ.pop(name, None) for name in names}


saved = clean_provider_environment()
try:
    clean_detect = CliRunner().invoke(cli, ["ai-provider", "detect"])
    assert clean_detect.exit_code == 0, clean_detect.output
    assert "Found 1 provider(s)" in clean_detect.output
    assert "ollama" in clean_detect.output

    with patch("aksara.ai.providers_unified.detect_all_providers", return_value=[]):
        help_result = CliRunner().invoke(cli, ["ai-provider", "detect"])
    assert help_result.exit_code == 0, help_result.output
    assert "OLLAMA_BASE_URL" in help_result.output
    assert "CUSTOM_LLM_BASE_URL" in help_result.output
    assert "OLLAMA_HOST" not in help_result.output
    assert "AKSARA_CUSTOM_LLM_URL" not in help_result.output

    os.environ.update({
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        "OLLAMA_MODEL": "docs-probe-model",
    })
    ollama = UnifiedAiProvider.from_env("ollama")
    assert ollama.base_url == "http://127.0.0.1:11434"
    assert ollama.model == "docs-probe-model"
    os.environ.pop("OLLAMA_BASE_URL")
    os.environ.pop("OLLAMA_MODEL")

    os.environ.update({
        "CUSTOM_LLM_BASE_URL": "https://llm.example.com",
        "CUSTOM_LLM_API_KEY": "docs-probe-key",
        "CUSTOM_LLM_MODEL": "docs-probe-model",
    })
    custom = UnifiedAiProvider.from_env("custom")
    assert custom.base_url == "https://llm.example.com"
    assert custom.model == "docs-probe-model"
    assert custom.api_key == "docs-probe-key"
    os.environ.pop("CUSTOM_LLM_API_KEY")
    keyless = UnifiedAiProvider.from_env("custom")
    assert _detect_provider_from_env() == "custom"
    assert keyless.is_configured() is False

    adapter = CustomHttpAdapter(keyless)
    assert adapter.generate_path == "/v1/completions"
    assert adapter.models_path == "/v1/models"
    assert adapter.prompt_field == "prompt"
    assert adapter.response_field == "text"

    print(json.dumps({
        "package_version": aksara.__version__,
        "package_path": aksara.__file__,
        "checks": {
            "documented_ollama_environment_loaded": True,
            "documented_custom_environment_loaded": True,
            "detect_help_uses_loaded_environment_names": True,
            "clean_environment_reports_default_ollama": True,
            "keyless_custom_detected_but_not_configured": True,
            "custom_adapter_defaults_match_docs": True,
        },
    }))
finally:
    for name in list(os.environ):
        if name in saved:
            os.environ.pop(name, None)
    os.environ.update({name: value for name, value in saved.items() if value is not None})
'''


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"DATABASE_URL", "PYTHONPATH"}
        and not key.startswith(("AKSARA_", "OPENAI_", "ANTHROPIC_", "AZURE_", "OLLAMA_", "CUSTOM_LLM_"))
    }
    with tempfile.TemporaryDirectory(prefix="aksara-ai-provider-docs-") as directory:
        run = subprocess.run(
            [str(args.python.absolute()), "-I", "-c", PROBE],
            cwd=directory,
            env=environment,
            text=True,
            capture_output=True,
            timeout=60,
            check=True,
        )
    evidence = json.loads(run.stdout)
    package_path = Path(evidence.pop("package_path")).resolve()
    assert not package_path.is_relative_to(ROOT)
    evidence.update(
        {
            "schema_version": 1,
            "pass": True,
            "source_checkout_framework_imports": False,
            "scope": (
                "Installed-wheel environment loading, provider-help labels and CustomHttpAdapter "
                "defaults with sockets unused. Records two experimental configured-state defects; "
                "does not test provider reachability, model output or production suitability."
            ),
            "page_sha256": {name: digest(ROOT / name) for name in PAGES},
            "source_sha256": {name: digest(ROOT / name) for name in SOURCES},
            "runner_sha256": digest(Path(__file__)),
        }
    )
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed provider-contract checks")


if __name__ == "__main__":
    main()
