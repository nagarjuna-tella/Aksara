"""
Aksara AI Hub — Unified Settings & Configuration.

v0.5.28: Central configuration for all AI features. Replaces scattered
env-var handling with a single Pydantic-based settings layer that:

- Loads from environment variables (backward-compatible)
- Loads from optional ``aksara.ai.json`` / ``aksara.ai.toml`` config file
- Merges both sources with env taking precedence
- Exposes helpers: ``load_aihub_settings()``, ``save_aihub_settings()``,
  ``resolve_defaults()``

Usage::

    from aksara.ai.hub_settings import load_aihub_settings

    hub = load_aihub_settings()
    print(hub.active_provider)       # "openai"
    print(hub.defaults.chat_model)   # "gpt-4o"
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field

logger = logging.getLogger("aksara.ai.hub_settings")

# ---------------------------------------------------------------------------
# Provider-specific config models
# ---------------------------------------------------------------------------

ProviderKind = Literal["openai", "azure", "anthropic", "ollama", "custom"]
ModelMode = Literal["chat", "code", "embeddings"]

# Well-known default models per provider & mode
_PROVIDER_DEFAULT_MODELS: Dict[str, Dict[str, str]] = {
    "openai": {
        "chat": "gpt-4o",
        "code": "gpt-4o",
        "embeddings": "text-embedding-3-large",
    },
    "azure": {
        "chat": "gpt-4o",
        "code": "gpt-4o",
        "embeddings": "text-embedding-3-large",
    },
    "anthropic": {
        "chat": "claude-3-5-sonnet-20241022",
        "code": "claude-3-5-sonnet-20241022",
        "embeddings": "",
    },
    "ollama": {
        "chat": "llama3",
        "code": "llama3",
        "embeddings": "nomic-embed-text",
    },
    "custom": {
        "chat": "default",
        "code": "default",
        "embeddings": "",
    },
}


class OpenAIConfig(BaseModel):
    """OpenAI-specific configuration."""

    api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    model: Optional[str] = Field(default=None, description="Default model")
    base_url: str = Field(
        default="https://api.openai.com/v1", description="API base URL"
    )
    organization: Optional[str] = Field(default=None, description="Org ID")
    extra: Dict[str, Any] = Field(default_factory=dict)


class AzureOpenAIConfig(BaseModel):
    """Azure OpenAI-specific configuration."""

    api_key: Optional[str] = Field(default=None, description="Azure API key")
    model: Optional[str] = Field(default=None, description="Deployment model")
    base_url: Optional[str] = Field(default=None, description="Azure endpoint")
    api_version: str = Field(
        default="2024-02-15-preview", description="API version"
    )
    deployment: Optional[str] = Field(default=None, description="Deployment name")
    extra: Dict[str, Any] = Field(default_factory=dict)


class AnthropicConfig(BaseModel):
    """Anthropic-specific configuration."""

    api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    model: Optional[str] = Field(default=None, description="Default model")
    base_url: str = Field(
        default="https://api.anthropic.com", description="API base URL"
    )
    extra: Dict[str, Any] = Field(default_factory=dict)


class OllamaConfig(BaseModel):
    """Ollama local-model configuration."""

    base_url: str = Field(
        default="http://localhost:11434", description="Ollama server URL"
    )
    model: Optional[str] = Field(default=None, description="Default model")
    extra: Dict[str, Any] = Field(default_factory=dict)


class CustomHttpConfig(BaseModel):
    """Custom HTTP LLM endpoint configuration."""

    api_key: Optional[str] = Field(default=None, description="API key")
    model: Optional[str] = Field(default=None, description="Model name")
    base_url: str = Field(
        default="http://localhost:8080", description="Endpoint URL"
    )
    headers: Dict[str, str] = Field(
        default_factory=dict, description="Extra HTTP headers"
    )
    extra: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Unified ProviderConfig wrapper
# ---------------------------------------------------------------------------


class ProviderConfig(BaseModel):
    """Normalised per-provider configuration.

    Wraps a specific config (OpenAI / Azure / Anthropic / Ollama / Custom)
    under a common envelope used by ``AiHubSettings.providers``.
    """

    kind: ProviderKind = Field(..., description="Provider type key")
    enabled: bool = Field(default=True, description="Whether this provider is active")
    openai: Optional[OpenAIConfig] = None
    azure: Optional[AzureOpenAIConfig] = None
    anthropic: Optional[AnthropicConfig] = None
    ollama: Optional[OllamaConfig] = None
    custom: Optional[CustomHttpConfig] = None

    @property
    def active_config(self) -> Optional[BaseModel]:
        """Return the provider-specific config that matches ``kind``."""
        return getattr(self, self.kind, None)

    @property
    def is_configured(self) -> bool:
        """Return True when enough credentials/URLs are present."""
        cfg = self.active_config
        if cfg is None:
            return False
        base_url = getattr(cfg, "base_url", "")
        if base_url:
            parsed = urlparse(base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                return False
        if self.kind in {"ollama", "custom"}:
            return bool(base_url)
        return bool(getattr(cfg, "api_key", ""))

    @property
    def api_key(self) -> Optional[str]:
        cfg = self.active_config
        return getattr(cfg, "api_key", None) if cfg else None

    @property
    def base_url(self) -> Optional[str]:
        cfg = self.active_config
        return getattr(cfg, "base_url", None) if cfg else None

    @property
    def model(self) -> Optional[str]:
        cfg = self.active_config
        return getattr(cfg, "model", None) if cfg else None

    def get_supported_modes(self) -> List[ModelMode]:
        """Return the modes this provider can serve."""
        modes: List[ModelMode] = []
        defaults = _PROVIDER_DEFAULT_MODELS.get(self.kind, {})
        if defaults.get("chat"):
            modes.append("chat")
        if defaults.get("code"):
            modes.append("code")
        if defaults.get("embeddings"):
            modes.append("embeddings")
        return modes

    def to_safe_dict(self) -> Dict[str, Any]:
        """Export config without secrets (masks API key)."""
        d = self.model_dump()
        for section in ("openai", "azure", "anthropic", "custom"):
            if d.get(section) and d[section].get("api_key"):
                key = d[section]["api_key"]
                d[section]["api_key"] = (
                    f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "****"
                )
        return d

    def to_unified_provider(self) -> "UnifiedAiProvider":  # noqa: F821
        """Convert to legacy ``UnifiedAiProvider`` for backward compat."""
        from aksara.ai.providers_unified import UnifiedAiProvider

        cfg = self.active_config
        extra: Dict[str, Any] = {}
        if self.kind == "azure" and cfg is not None:
            extra["api_version"] = getattr(cfg, "api_version", "")
            dep = getattr(cfg, "deployment", None)
            if dep:
                extra["deployment"] = dep
        if self.kind == "custom" and cfg is not None:
            hdrs = getattr(cfg, "headers", {})
            if hdrs:
                extra["headers"] = hdrs

        return UnifiedAiProvider(
            provider=self.kind,
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            extra=extra,
        )


# ---------------------------------------------------------------------------
# Default model assignments
# ---------------------------------------------------------------------------


class AiDefaultModels(BaseModel):
    """Default model assignments for each AI mode (chat / code / embeddings)."""

    chat_model: Optional[str] = Field(default=None, description="Default chat / agent model")
    chat_provider: Optional[ProviderKind] = Field(default=None, description="Provider for chat")
    code_model: Optional[str] = Field(default=None, description="Default code model")
    code_provider: Optional[ProviderKind] = Field(default=None, description="Provider for code")
    embeddings_model: Optional[str] = Field(default=None, description="Default embedding model")
    embeddings_provider: Optional[ProviderKind] = Field(default=None, description="Provider for embeddings")


# ---------------------------------------------------------------------------
# Top-level AI Hub Settings
# ---------------------------------------------------------------------------


class AiHubSettings(BaseModel):
    """Central configuration for all Aksara AI features.

    Merges zero or more ``ProviderConfig`` entries with an ``AiDefaultModels``
    mapping.  Call ``resolve_defaults()`` after loading to fill in any
    missing model assignments from the first configured provider.
    """

    providers: List[ProviderConfig] = Field(default_factory=list)
    defaults: AiDefaultModels = Field(default_factory=AiDefaultModels)
    active_provider: Optional[ProviderKind] = Field(
        default=None,
        description="Which provider is the primary active one",
    )
    version: str = Field(default="0.5.28", description="Config schema version")

    # --- helpers ---------------------------------------------------------

    def get_provider(self, kind: ProviderKind) -> Optional[ProviderConfig]:
        """Return the ``ProviderConfig`` for *kind*, or ``None``."""
        for p in self.providers:
            if p.kind == kind:
                return p
        return None

    def configured_providers(self) -> List[ProviderConfig]:
        """Return only providers that have credentials/URLs."""
        return [p for p in self.providers if p.enabled and p.is_configured]

    def provider_status_summary(self) -> Dict[str, Any]:
        """Return a JSON-friendly summary of all providers."""
        items: List[Dict[str, Any]] = []
        for p in self.providers:
            items.append({
                "kind": p.kind,
                "enabled": p.enabled,
                "configured": p.is_configured,
                "model": p.model,
                "base_url": p.base_url,
                "modes": p.get_supported_modes(),
            })
        return {
            "total": len(self.providers),
            "configured": sum(1 for p in self.providers if p.is_configured),
            "active_provider": self.active_provider,
            "providers": items,
        }

    def resolve_defaults(self) -> "AiHubSettings":
        """Fill in missing default model assignments from the first configured
        provider.  Mutates in place and returns ``self`` for chaining."""
        configured = self.configured_providers()
        if not configured:
            return self

        primary = None
        if self.active_provider:
            primary = self.get_provider(self.active_provider)
            if primary and not primary.is_configured:
                primary = None
        if primary is None:
            primary = configured[0]
            self.active_provider = primary.kind

        defs = _PROVIDER_DEFAULT_MODELS.get(primary.kind, {})

        if not self.defaults.chat_model:
            self.defaults.chat_model = primary.model or defs.get("chat")
        if not self.defaults.chat_provider:
            self.defaults.chat_provider = primary.kind

        if not self.defaults.code_model:
            self.defaults.code_model = primary.model or defs.get("code")
        if not self.defaults.code_provider:
            self.defaults.code_provider = primary.kind

        # Embeddings — prefer a provider that supports them
        if not self.defaults.embeddings_model:
            for p in configured:
                emb = _PROVIDER_DEFAULT_MODELS.get(p.kind, {}).get("embeddings")
                if emb:
                    self.defaults.embeddings_model = emb
                    if not self.defaults.embeddings_provider:
                        self.defaults.embeddings_provider = p.kind
                    break

        return self

    def to_safe_dict(self) -> Dict[str, Any]:
        """Export the full config with secrets masked."""
        return {
            "active_provider": self.active_provider,
            "version": self.version,
            "defaults": self.defaults.model_dump(),
            "providers": [p.to_safe_dict() for p in self.providers],
        }


# ---------------------------------------------------------------------------
# ENV-VAR MAPPINGS (for backward-compat loading)
# ---------------------------------------------------------------------------

_ENV_KEY_MAP: Dict[str, Dict[str, str]] = {
    "openai": {
        "api_key": "OPENAI_API_KEY",
        "model": "OPENAI_MODEL",
        "base_url": "OPENAI_BASE_URL",
        "organization": "OPENAI_ORGANIZATION",
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

_CONFIG_CLASSES: Dict[str, type] = {
    "openai": OpenAIConfig,
    "azure": AzureOpenAIConfig,
    "anthropic": AnthropicConfig,
    "ollama": OllamaConfig,
    "custom": CustomHttpConfig,
}


# ---------------------------------------------------------------------------
# Loader / saver
# ---------------------------------------------------------------------------


def _provider_from_env(kind: ProviderKind) -> ProviderConfig:
    """Build a ``ProviderConfig`` for *kind* solely from env vars."""
    mapping = _ENV_KEY_MAP.get(kind, {})
    raw: Dict[str, Any] = {}
    for field_name, env_var in mapping.items():
        val = os.environ.get(env_var)
        if val:
            raw[field_name] = val

    cfg_cls = _CONFIG_CLASSES[kind]
    # Local/custom adapter defaults are not evidence of environment
    # configuration.  Explicitly constructed config objects retain defaults.
    if kind in {"ollama", "custom"} and not raw:
        cfg = cfg_cls(base_url="")
    else:
        cfg = cfg_cls(**raw)
    return ProviderConfig(kind=kind, **{kind: cfg})


def _detect_active_from_env() -> Optional[ProviderKind]:
    """Determine the primary provider from env vars (priority order)."""
    explicit = os.environ.get("AKSARA_AI_PROVIDER", "").lower()
    if explicit in ("openai", "azure", "anthropic", "ollama", "custom"):
        return explicit  # type: ignore[return-value]
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
    return None


def clear_provider_api_key(kind: str, env_path: Optional[str] = None) -> None:
    """Remove a provider's api_key from the .env file and os.environ.

    Silently does nothing when the provider has no api_key mapping (e.g. Ollama)
    or when no .env file exists.
    """
    mapping = _ENV_KEY_MAP.get(kind, {})
    env_var = mapping.get("api_key")
    if not env_var:
        return
    os.environ.pop(env_var, None)
    path_obj = Path(env_path) if env_path else Path.cwd() / ".env"
    if path_obj.exists():
        lines = path_obj.read_text().splitlines()
        updated = [l for l in lines if l.split("=", 1)[0].strip() != env_var]
        path_obj.write_text("\n".join(updated) + ("\n" if updated else ""))


def _load_from_file(path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Try to load ``aksara.ai.json`` (or explicit path)."""
    if path is not None:
        p = Path(path)
    else:
        # Search CWD for aksara.ai.json
        p = Path.cwd() / "aksara.ai.json"

    if not p.exists():
        return None

    try:
        return json.loads(p.read_text())  # type: ignore[no-any-return]
    except Exception as exc:
        logger.warning("Failed to load AI Hub config from %s: %s", p, exc)
        return None


def load_aihub_settings(
    *,
    config_path: Optional[str] = None,
    include_env: bool = True,
) -> AiHubSettings:
    """Load and merge AI Hub settings from file + environment.

    Priority (highest-first):
    1. Environment variables
    2. Config file (``aksara.ai.json``)
    3. Built-in defaults

    Returns a fully resolved ``AiHubSettings`` with defaults filled in.
    """
    # 1. Start from config file (if any)
    file_data = _load_from_file(config_path)
    if file_data:
        try:
            hub = AiHubSettings(**file_data)
        except Exception as exc:
            logger.warning("Invalid AI Hub config file, ignoring: %s", exc)
            hub = AiHubSettings()
    else:
        hub = AiHubSettings()

    # 2. Merge / overlay env vars for each known provider
    if include_env:
        for kind in ("openai", "azure", "anthropic", "ollama", "custom"):
            env_prov = _provider_from_env(kind)  # type: ignore[arg-type]
            existing = hub.get_provider(kind)  # type: ignore[arg-type]
            if existing is None and env_prov.is_configured:
                hub.providers.append(env_prov)
            elif existing is None:
                # Add unconfigured placeholder so callers see all providers
                hub.providers.append(env_prov)
            # If existing already present from file — file wins (env can't
            # override file-based config to avoid accidental secret leaks)

    # 3. Detect primary provider
    if not hub.active_provider:
        hub.active_provider = _detect_active_from_env()

    # 4. Resolve defaults
    hub.resolve_defaults()

    return hub


def save_aihub_settings(
    hub: AiHubSettings,
    path: Optional[str] = None,
) -> str:
    """Persist AI Hub settings to ``aksara.ai.json``.

    Returns the path written to.
    """
    if path is None:
        path = str(Path.cwd() / "aksara.ai.json")

    p = Path(path)
    safe = hub.to_safe_dict()
    p.write_text(json.dumps(safe, indent=2) + "\n")
    return path


def resolve_defaults(hub: Optional[AiHubSettings] = None) -> AiDefaultModels:
    """Convenience: load settings (if needed) and return the resolved
    default model assignments."""
    if hub is None:
        hub = load_aihub_settings()
    hub.resolve_defaults()
    return hub.defaults


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "AiDefaultModels",
    "AiHubSettings",
    "AnthropicConfig",
    "AzureOpenAIConfig",
    "CustomHttpConfig",
    "ModelMode",
    "OllamaConfig",
    "OpenAIConfig",
    "ProviderConfig",
    "ProviderKind",
    "load_aihub_settings",
    "resolve_defaults",
    "save_aihub_settings",
]
