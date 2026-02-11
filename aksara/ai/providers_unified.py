"""
Aksara Unified AI Provider System

v0.5.25: Single configuration object for all AI features.

Replaces ad-hoc AI env var handling with a unified provider abstraction
that supports OpenAI, Azure, Anthropic, Ollama, and Custom HTTP providers.

Loads configuration from:
- Environment variables
- .env files
- provider.json (optional)

Usage:
    from aksara.ai.providers_unified import UnifiedAiProvider, detect_providers

    # From environment
    provider = UnifiedAiProvider.from_env()
    if provider.is_configured():
        client = provider.get_llm_client()
        result = client.generate("Hello!")
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Literal, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from aksara.ai.llm_clients.base import BaseLlmClient

logger = logging.getLogger("aksara.ai.providers_unified")

# Provider type literals
ProviderType = Literal["openai", "azure", "anthropic", "ollama", "custom"]

# Known env var mappings per provider
_ENV_MAPPINGS: Dict[str, Dict[str, str]] = {
    "openai": {
        "api_key": "OPENAI_API_KEY",
        "model": "OPENAI_MODEL",
        "base_url": "OPENAI_BASE_URL",
    },
    "azure": {
        "api_key": "AZURE_OPENAI_API_KEY",
        "model": "AZURE_OPENAI_MODEL",
        "base_url": "AZURE_OPENAI_ENDPOINT",
        "api_version": "AZURE_OPENAI_API_VERSION",
        "deployment": "AZURE_OPENAI_DEPLOYMENT",
    },
    "anthropic": {
        "api_key": "ANTHROPIC_API_KEY",
        "model": "ANTHROPIC_MODEL",
        "base_url": "ANTHROPIC_BASE_URL",
    },
    "ollama": {
        "base_url": "OLLAMA_BASE_URL",
        "model": "OLLAMA_MODEL",
    },
    "custom": {
        "api_key": "CUSTOM_LLM_API_KEY",
        "model": "CUSTOM_LLM_MODEL",
        "base_url": "CUSTOM_LLM_BASE_URL",
    },
}

# Default model for each provider
_DEFAULT_MODELS: Dict[str, str] = {
    "openai": "gpt-4o",
    "azure": "gpt-4o",
    "anthropic": "claude-3-5-sonnet-20241022",
    "ollama": "llama3",
    "custom": "default",
}

# Default base URLs
_DEFAULT_BASE_URLS: Dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "azure": "",  # Must be configured
    "anthropic": "https://api.anthropic.com",
    "ollama": "http://localhost:11434",
    "custom": "http://localhost:8080",
}


class UnifiedAiProvider(BaseModel):
    """
    Single configuration object for all AI features.

    Supports OpenAI, Azure OpenAI, Anthropic, Ollama, and Custom HTTP providers.
    Can be loaded from environment variables, .env files, or provider.json.

    Attributes:
        provider: The AI provider type
        base_url: Provider endpoint URL
        api_key: API key for authentication (not needed for Ollama)
        model: Model identifier to use
        extra: Additional provider-specific configuration
    """

    model_config = {"extra": "forbid"}

    provider: ProviderType = Field(
        ...,
        description="AI provider type: openai, azure, anthropic, ollama, custom",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Provider endpoint URL",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for authentication",
    )
    model: Optional[str] = Field(
        default=None,
        description="Model identifier to use",
    )
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional provider-specific configuration",
    )

    @classmethod
    def from_env(
        cls,
        provider: Optional[ProviderType] = None,
    ) -> "UnifiedAiProvider":
        """
        Build a UnifiedAiProvider from environment variables.

        Auto-detects provider if not specified by checking which
        env vars are set (prioritizes: openai > anthropic > azure > ollama > custom).

        Args:
            provider: Explicit provider type. Auto-detected if None.

        Returns:
            Configured UnifiedAiProvider instance.
        """
        if provider is None:
            provider = _detect_provider_from_env()

        mappings = _ENV_MAPPINGS.get(provider, {})
        api_key = os.environ.get(mappings.get("api_key", ""), None)
        model = os.environ.get(mappings.get("model", ""), None) or _DEFAULT_MODELS.get(provider)
        base_url = os.environ.get(mappings.get("base_url", ""), None) or _DEFAULT_BASE_URLS.get(provider)

        extra: Dict[str, Any] = {}
        if provider == "azure":
            api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
            extra["api_version"] = api_version
            if deployment:
                extra["deployment"] = deployment

        return cls(
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            model=model,
            extra=extra,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnifiedAiProvider":
        """Build from a dictionary (e.g. loaded from provider.json)."""
        return cls(**data)

    @classmethod
    def from_json_file(cls, path: Optional[str] = None) -> Optional["UnifiedAiProvider"]:
        """
        Load from provider.json file.

        Args:
            path: Path to provider.json. Defaults to CWD/provider.json.

        Returns:
            UnifiedAiProvider if file exists and is valid, None otherwise.
        """
        if path is None:
            path = str(Path.cwd() / "provider.json")

        p = Path(path)
        if not p.exists():
            return None

        try:
            data = json.loads(p.read_text())
            return cls.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load provider.json: {e}")
            return None

    def is_configured(self) -> bool:
        """
        Check whether this provider has enough configuration to work.

        Returns:
            True if the provider can potentially make API calls.
        """
        # Ollama doesn't need an API key
        if self.provider == "ollama":
            return bool(self.base_url)

        # Cloud providers need API key
        if self.provider in ("openai", "anthropic", "azure", "custom"):
            return bool(self.api_key)

        return False

    def ping(self) -> Dict[str, Any]:
        """
        Test connectivity to the provider.

        Returns a dict with:
            - ok: bool
            - provider: str
            - model: str
            - message: str
            - models: list (if supported)
        """
        result: Dict[str, Any] = {
            "ok": False,
            "provider": self.provider,
            "model": self.model or "",
            "message": "",
            "models": [],
        }

        if not self.is_configured():
            result["message"] = f"Provider '{self.provider}' is not configured"
            return result

        try:
            client = self.get_llm_client()
            available = client.is_available()
            result["ok"] = available
            result["message"] = "Connected" if available else "Unreachable"
        except Exception as e:
            result["message"] = f"Error: {str(e)}"

        return result

    def get_llm_client(self) -> "BaseLlmClient":
        """
        Return the correct LLM adapter for this provider.

        Returns:
            A BaseLlmClient implementation for the configured provider.

        Raises:
            ValueError: If provider is unknown.
        """
        from aksara.ai.llm_clients import get_client_for_provider
        return get_client_for_provider(self)

    def to_safe_dict(self) -> Dict[str, Any]:
        """
        Export config without secrets (masks API key).

        Returns:
            Dict suitable for logging/display.
        """
        d = self.model_dump()
        if d.get("api_key"):
            key = d["api_key"]
            d["api_key"] = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "****"
        return d

    def save_to_env_file(self, path: Optional[str] = None) -> str:
        """
        Save provider configuration to a .env file.

        Args:
            path: Path to .env file. Defaults to CWD/.env.

        Returns:
            The path written to.
        """
        if path is None:
            path = str(Path.cwd() / ".env")

        mappings = _ENV_MAPPINGS.get(self.provider, {})
        lines: List[str] = []

        if self.api_key and "api_key" in mappings:
            lines.append(f'{mappings["api_key"]}={self.api_key}')
        if self.model and "model" in mappings:
            lines.append(f'{mappings["model"]}={self.model}')
        if self.base_url and "base_url" in mappings:
            lines.append(f'{mappings["base_url"]}={self.base_url}')

        for k, v in self.extra.items():
            env_key = f"{self.provider.upper()}_{k.upper()}"
            lines.append(f"{env_key}={v}")

        # Append or update existing .env
        env_path = Path(path)
        existing = ""
        if env_path.exists():
            existing = env_path.read_text()

        # Simple append strategy (won't duplicate if already present)
        new_vars = {}
        for line in lines:
            key, _, val = line.partition("=")
            new_vars[key.strip()] = val.strip()

        # Parse existing
        existing_lines = existing.splitlines() if existing else []
        existing_keys = set()
        updated_lines = []
        for eline in existing_lines:
            stripped = eline.strip()
            if "=" in stripped and not stripped.startswith("#"):
                ekey = stripped.split("=", 1)[0].strip()
                if ekey in new_vars:
                    updated_lines.append(f"{ekey}={new_vars[ekey]}")
                    existing_keys.add(ekey)
                else:
                    updated_lines.append(eline)
            else:
                updated_lines.append(eline)

        # Add new vars not already in file
        for key, val in new_vars.items():
            if key not in existing_keys:
                updated_lines.append(f"{key}={val}")

        env_path.write_text("\n".join(updated_lines) + "\n")
        return path

    def save_to_json(self, path: Optional[str] = None) -> str:
        """
        Save provider configuration to provider.json.

        Args:
            path: Path to provider.json. Defaults to CWD/provider.json.

        Returns:
            The path written to.
        """
        if path is None:
            path = str(Path.cwd() / "provider.json")

        p = Path(path)
        p.write_text(json.dumps(self.model_dump(), indent=2) + "\n")
        return path


def _detect_provider_from_env() -> ProviderType:
    """
    Auto-detect provider from environment variables.

    Priority: AKSARA_AI_PROVIDER env var > openai > anthropic > azure > ollama > custom
    """
    # Explicit override
    explicit = os.environ.get("AKSARA_AI_PROVIDER", "").lower()
    if explicit in ("openai", "azure", "anthropic", "ollama", "custom"):
        return explicit  # type: ignore

    # Check for API keys
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("AZURE_OPENAI_API_KEY"):
        return "azure"
    if os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_MODEL"):
        return "ollama"
    if os.environ.get("CUSTOM_LLM_BASE_URL") or os.environ.get("CUSTOM_LLM_API_KEY"):
        return "custom"

    # Default to openai (unconfigured)
    return "openai"


def detect_all_providers() -> List["UnifiedAiProvider"]:
    """
    Detect all providers that have any configuration present.

    Returns:
        List of UnifiedAiProvider instances (one per known provider type).
    """
    results: List["UnifiedAiProvider"] = []

    for ptype in ("openai", "azure", "anthropic", "ollama", "custom"):
        try:
            p = UnifiedAiProvider.from_env(provider=ptype)  # type: ignore
            results.append(p)
        except Exception:
            # Return a bare unconfigured provider so callers can see it
            results.append(UnifiedAiProvider(provider=ptype))  # type: ignore

    return results


def get_active_provider() -> UnifiedAiProvider:
    """
    Get the currently active unified provider.

    Tries provider.json first, then environment variables.

    Returns:
        The active UnifiedAiProvider.
    """
    # Try JSON config first
    from_json = UnifiedAiProvider.from_json_file()
    if from_json is not None and from_json.is_configured():
        return from_json

    # Fall back to env
    return UnifiedAiProvider.from_env()


__all__ = [
    "ProviderType",
    "UnifiedAiProvider",
    "detect_all_providers",
    "get_active_provider",
]
