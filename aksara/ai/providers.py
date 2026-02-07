"""
Aksara AI Profiles & Provider Contracts

v0.5.11: Vendor-agnostic, pluggable description layer for AI providers & models.

This module provides:
- AiModelProfile: Description of an AI model's capabilities and limits
- AiProviderProfile: Configuration for an AI provider (no secrets stored)
- AiProfileSet: Collection of providers for an environment
- AiProviderRegistry: Central registry for managing AI profiles
- Built-in example profiles for documentation and demos

IMPORTANT: This is a metadata & configuration layer only.
- NO network calls to AI providers
- NO vendor SDK dependencies (openai, anthropic, etc.)
- NO actual completion/chat logic
- NO API keys or secrets stored in profiles

Usage:
    from aksara.ai.providers import (
        AiModelProfile,
        AiProviderProfile,
        AiProfileSet,
        AiProviderRegistry,
        get_ai_provider_registry,
        build_default_ai_profile_set,
    )
    
    # Register a provider profile
    registry = get_ai_provider_registry(app)
    registry.register_profile(my_provider)
    
    # Get available providers
    providers = registry.list_providers()
    
    # Get models for a specific provider
    models = registry.list_models(provider_name="my_provider")
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("aksara.ai.providers")


# =============================================================================
# Type Aliases
# =============================================================================

AiModelKind = Literal[
    "chat",
    "completion",
    "embedding",
    "tool-calling",
    "rerank",
    "vision",
    "audio",
    "code",
]
"""Classification of AI model capabilities."""

AiProviderKind = Literal[
    "openai",
    "azure_openai",
    "anthropic",
    "google",
    "cohere",
    "local",
    "other",
]
"""Classification of AI provider types."""


# =============================================================================
# Core Profile Models
# =============================================================================

class AiModelProfile(BaseModel):
    """
    Describes an AI model and its capabilities.
    
    This is a metadata-only description - no actual API calls are made.
    Used for discovery, configuration, and capability checking.
    
    Attributes:
        name: Short handle identifier (e.g., "gpt-4o", "claude-3-sonnet")
        display_name: Human-readable name for UI display
        model_id: Actual provider model identifier (may differ from name)
        kind: Primary capability classification
        max_input_tokens: Maximum input context length (None = unknown)
        max_output_tokens: Maximum output length (None = unknown)
        supports_tools: Whether model supports function/tool calling
        supports_streaming: Whether model supports streaming responses
        supports_vision: Whether model supports image inputs
        tags: Free-form tags for filtering (e.g., "fast", "cheap", "reasoning")
    
    Example:
        AiModelProfile(
            name="gpt-4o",
            display_name="GPT-4 Omni",
            model_id="gpt-4o-2024-05-13",
            kind="chat",
            max_input_tokens=128000,
            max_output_tokens=4096,
            supports_tools=True,
            supports_streaming=True,
            tags=["fast", "multimodal"],
        )
    """
    
    model_config = {"extra": "forbid"}
    
    name: str = Field(
        ...,
        description="Short handle identifier (e.g., 'gpt-4o', 'claude-3-sonnet')",
    )
    display_name: str = Field(
        ...,
        description="Human-readable name for UI display",
    )
    model_id: str = Field(
        ...,
        description="Actual provider model identifier (may differ from name)",
    )
    kind: AiModelKind = Field(
        default="chat",
        description="Primary capability classification",
    )
    max_input_tokens: Optional[int] = Field(
        default=None,
        description="Maximum input context length (None = unknown)",
    )
    max_output_tokens: Optional[int] = Field(
        default=None,
        description="Maximum output length (None = unknown)",
    )
    supports_tools: bool = Field(
        default=False,
        description="Whether model supports function/tool calling",
    )
    supports_streaming: bool = Field(
        default=True,
        description="Whether model supports streaming responses",
    )
    supports_vision: bool = Field(
        default=False,
        description="Whether model supports image inputs",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Free-form tags for filtering (e.g., 'fast', 'cheap', 'reasoning')",
    )


class AiProviderProfile(BaseModel):
    """
    Configuration for an AI provider (no secrets stored).
    
    Describes a provider instance that can be used for AI operations.
    Multiple profiles can exist for the same provider kind (e.g., 
    different Azure OpenAI deployments).
    
    IMPORTANT: Do NOT include API keys or other secrets here.
    Use AiProviderSecretHint to document required environment variables.
    
    Attributes:
        name: Unique identifier for this provider profile
        display_name: Human-readable name for UI display
        kind: Provider type classification
        base_url: Custom endpoint URL (for self-hosted/proxy/Azure)
        api_version: API version string (for versioned APIs like Azure)
        models: List of available model profiles
        default_model: Name of the default model to use
        timeout_seconds: Request timeout (None = use client default)
        max_retries: Maximum retry count (None = use client default)
        metadata: Additional provider-specific configuration hints
    
    Example:
        AiProviderProfile(
            name="openai_default",
            display_name="OpenAI (Default)",
            kind="openai",
            models=[gpt4o_profile, gpt4o_mini_profile],
            default_model="gpt-4o",
            timeout_seconds=30,
            max_retries=2,
        )
    """
    
    model_config = {"extra": "forbid"}
    
    name: str = Field(
        ...,
        description="Unique identifier for this provider profile",
    )
    display_name: str = Field(
        ...,
        description="Human-readable name for UI display",
    )
    kind: AiProviderKind = Field(
        ...,
        description="Provider type classification",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Custom endpoint URL (for self-hosted/proxy/Azure)",
    )
    api_version: Optional[str] = Field(
        default=None,
        description="API version string (for versioned APIs like Azure)",
    )
    models: List[AiModelProfile] = Field(
        default_factory=list,
        description="List of available model profiles",
    )
    default_model: Optional[str] = Field(
        default=None,
        description="Name of the default model to use",
    )
    timeout_seconds: Optional[int] = Field(
        default=None,
        description="Request timeout (None = use client default)",
    )
    max_retries: Optional[int] = Field(
        default=None,
        description="Maximum retry count (None = use client default)",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional provider-specific configuration hints",
    )
    
    def get_model(self, name: str) -> Optional[AiModelProfile]:
        """Get a model by name or model_id."""
        for model in self.models:
            if model.name == name or model.model_id == name:
                return model
        return None
    
    def get_default_model(self) -> Optional[AiModelProfile]:
        """Get the default model for this provider."""
        if self.default_model:
            return self.get_model(self.default_model)
        if self.models:
            return self.models[0]
        return None


class AiProfileSet(BaseModel):
    """
    Collection of AI provider profiles for an environment.
    
    Represents the complete AI configuration for an application,
    including all available providers and models.
    
    Attributes:
        providers: List of provider profiles
        default_provider: Name of the default provider
        environment: Environment name (dev, stage, prod)
        version: Configuration version (for cache invalidation)
    
    Example:
        AiProfileSet(
            providers=[openai_profile, anthropic_profile],
            default_provider="openai_default",
            environment="production",
            version="1.0.0",
        )
    """
    
    model_config = {"extra": "forbid"}
    
    providers: List[AiProviderProfile] = Field(
        default_factory=list,
        description="List of provider profiles",
    )
    default_provider: Optional[str] = Field(
        default=None,
        description="Name of the default provider",
    )
    environment: Optional[str] = Field(
        default=None,
        description="Environment name (dev, stage, prod)",
    )
    version: Optional[str] = Field(
        default=None,
        description="Configuration version (for cache invalidation)",
    )
    
    def get_provider(self, name: str) -> Optional[AiProviderProfile]:
        """Get a provider by name."""
        for provider in self.providers:
            if provider.name == name:
                return provider
        return None
    
    def get_default_provider(self) -> Optional[AiProviderProfile]:
        """Get the default provider."""
        if self.default_provider:
            return self.get_provider(self.default_provider)
        if self.providers:
            return self.providers[0]
        return None
    
    def total_models(self) -> int:
        """Count total models across all providers."""
        return sum(len(p.models) for p in self.providers)


# =============================================================================
# Secret Hint Models (Metadata Only - No Actual Secrets)
# =============================================================================

class AiProviderSecretHint(BaseModel):
    """
    Hint about required secrets for a provider (no actual values).
    
    Documents what environment variables or secrets are needed
    to connect to a provider. External tools can use this to
    prompt users for configuration.
    
    IMPORTANT: This never contains actual secret values.
    
    Attributes:
        provider_name: Name of the provider this hint applies to
        env_var: Environment variable name (e.g., "OPENAI_API_KEY")
        required: Whether this secret is required
        description: Human-readable description of the secret
    
    Example:
        AiProviderSecretHint(
            provider_name="openai_default",
            env_var="OPENAI_API_KEY",
            required=True,
            description="OpenAI API key from platform.openai.com",
        )
    """
    
    model_config = {"extra": "forbid"}
    
    provider_name: str = Field(
        ...,
        description="Name of the provider this hint applies to",
    )
    env_var: str = Field(
        ...,
        description="Environment variable name (e.g., 'OPENAI_API_KEY')",
    )
    required: bool = Field(
        default=True,
        description="Whether this secret is required",
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the secret",
    )


class AiProviderConfigInfo(BaseModel):
    """
    Complete AI configuration information for export.
    
    Combines the profile set with secret hints for external
    tools to understand what's configured and what's needed.
    
    Attributes:
        profile_set: The complete AI profile configuration
        secrets: List of secret hints (env var names, not values)
    """
    
    model_config = {"extra": "forbid"}
    
    profile_set: AiProfileSet = Field(
        ...,
        description="The complete AI profile configuration",
    )
    secrets: List[AiProviderSecretHint] = Field(
        default_factory=list,
        description="List of secret hints (env var names, not values)",
    )


# =============================================================================
# v0.5.12: Validation & Linting Models
# =============================================================================

AiProfileIssueSeverity = Literal["info", "warning", "error"]
"""Severity level for profile validation issues."""

AiProfileIssueKind = Literal[
    "duplicate_provider_name",
    "duplicate_model_name",
    "missing_default_provider",
    "missing_default_model",
    "unknown_provider_kind",
    "unknown_model_kind",
    "invalid_model_reference",
    "empty_profile_set",
    "empty_provider_models",
]
"""Classification of validation issue types."""

# Valid kinds for validation
_VALID_MODEL_KINDS = {"chat", "completion", "embedding", "tool-calling", "rerank", "vision", "audio", "code"}
_VALID_PROVIDER_KINDS = {"openai", "azure_openai", "anthropic", "google", "cohere", "local", "other"}


class AiProfileIssue(BaseModel):
    """
    A single validation issue found in an AI profile configuration.
    
    v0.5.12: Used by validate_profile_set() to report problems.
    
    Attributes:
        id: Stable identifier (e.g., "duplicate_provider_name:openai")
        kind: Classification of the issue type
        severity: How critical this issue is
        message: Human-readable description
        provider_name: Provider involved (if applicable)
        model_name: Model involved (if applicable)
        field: Specific field with issue (e.g., "default_provider")
    """
    
    model_config = {"extra": "forbid"}
    
    id: str = Field(
        ...,
        description="Stable identifier for this issue",
    )
    kind: AiProfileIssueKind = Field(
        ...,
        description="Classification of the issue type",
    )
    severity: AiProfileIssueSeverity = Field(
        ...,
        description="How critical this issue is",
    )
    message: str = Field(
        ...,
        description="Human-readable description of the issue",
    )
    provider_name: Optional[str] = Field(
        default=None,
        description="Provider involved (if applicable)",
    )
    model_name: Optional[str] = Field(
        default=None,
        description="Model involved (if applicable)",
    )
    field: Optional[str] = Field(
        default=None,
        description="Specific field with issue",
    )


class AiProfileHealth(BaseModel):
    """
    Health status of an AI profile configuration.
    
    v0.5.12: Result of validate_profile_set().
    
    Attributes:
        is_valid: True if no errors were found
        error_count: Number of error-level issues
        warning_count: Number of warning-level issues
        info_count: Number of info-level issues
        issues: List of all discovered issues
    """
    
    model_config = {"extra": "forbid"}
    
    is_valid: bool = Field(
        ...,
        description="True if no errors were found",
    )
    error_count: int = Field(
        default=0,
        description="Number of error-level issues",
    )
    warning_count: int = Field(
        default=0,
        description="Number of warning-level issues",
    )
    info_count: int = Field(
        default=0,
        description="Number of info-level issues",
    )
    issues: List[AiProfileIssue] = Field(
        default_factory=list,
        description="List of all discovered issues",
    )


# =============================================================================
# v0.5.12: Validation Functions
# =============================================================================

def classify_issue_severity(
    kind: AiProfileIssueKind, 
    *, 
    is_configured: bool = True
) -> AiProfileIssueSeverity:
    """
    Determine severity for an issue kind.
    
    v0.5.12: Centralizes severity logic for validation.
    
    Args:
        kind: The type of issue
        is_configured: Whether user has explicit config (vs defaults)
        
    Returns:
        Appropriate severity level
    """
    # Hard errors - always error level
    hard_errors = {
        "duplicate_provider_name",
        "duplicate_model_name",
        "unknown_provider_kind",
        "unknown_model_kind",
        "invalid_model_reference",
    }
    
    if kind in hard_errors:
        return "error"
    
    # Soft issues - depends on configuration state
    if kind == "empty_profile_set":
        return "error" if is_configured else "warning"
    
    if kind == "empty_provider_models":
        return "warning"
    
    if kind in ("missing_default_provider", "missing_default_model"):
        # If user explicitly configured something wrong, it's an error
        # If just using defaults, it's a warning
        return "warning"
    
    return "warning"


def validate_profile_set(profile_set: AiProfileSet) -> AiProfileHealth:
    """
    Validate an AiProfileSet for configuration issues.
    
    v0.5.12: Main validation entry point.
    
    Checks:
    - Profile set is non-empty
    - Provider names are unique
    - Provider kinds are valid
    - Model names within each provider are unique
    - Model kinds are valid
    - Default provider exists and has models
    - Default model exists within default provider
    
    Args:
        profile_set: The profile set to validate
        
    Returns:
        AiProfileHealth with validation results
    """
    issues: List[AiProfileIssue] = []
    
    # Track provider names for duplicate detection
    seen_provider_names: Dict[str, int] = {}
    
    # Check 1: Empty profile set
    if not profile_set.providers:
        issues.append(AiProfileIssue(
            id="empty_profile_set",
            kind="empty_profile_set",
            severity=classify_issue_severity("empty_profile_set"),
            message="Profile set has no providers configured",
            field="providers",
        ))
    
    # Iterate through providers
    for provider in profile_set.providers:
        # Check 2: Duplicate provider names
        if provider.name in seen_provider_names:
            issues.append(AiProfileIssue(
                id=f"duplicate_provider_name:{provider.name}",
                kind="duplicate_provider_name",
                severity=classify_issue_severity("duplicate_provider_name"),
                message=f"Provider name '{provider.name}' is defined multiple times",
                provider_name=provider.name,
                field="name",
            ))
        seen_provider_names[provider.name] = seen_provider_names.get(provider.name, 0) + 1
        
        # Check 3: Unknown provider kind
        if provider.kind not in _VALID_PROVIDER_KINDS:
            issues.append(AiProfileIssue(
                id=f"unknown_provider_kind:{provider.name}:{provider.kind}",
                kind="unknown_provider_kind",
                severity=classify_issue_severity("unknown_provider_kind"),
                message=f"Provider '{provider.name}' has unknown kind '{provider.kind}'",
                provider_name=provider.name,
                field="kind",
            ))
        
        # Check 4: Empty models list (warning)
        if not provider.models:
            issues.append(AiProfileIssue(
                id=f"empty_provider_models:{provider.name}",
                kind="empty_provider_models",
                severity=classify_issue_severity("empty_provider_models"),
                message=f"Provider '{provider.name}' has no models defined",
                provider_name=provider.name,
                field="models",
            ))
        
        # Track model names for duplicate detection within provider
        seen_model_names: Dict[str, int] = {}
        
        for model in provider.models:
            # Check 5: Duplicate model names within provider
            if model.name in seen_model_names:
                issues.append(AiProfileIssue(
                    id=f"duplicate_model_name:{provider.name}:{model.name}",
                    kind="duplicate_model_name",
                    severity=classify_issue_severity("duplicate_model_name"),
                    message=f"Model name '{model.name}' is defined multiple times in provider '{provider.name}'",
                    provider_name=provider.name,
                    model_name=model.name,
                    field="name",
                ))
            seen_model_names[model.name] = seen_model_names.get(model.name, 0) + 1
            
            # Check 6: Unknown model kind
            if model.kind not in _VALID_MODEL_KINDS:
                issues.append(AiProfileIssue(
                    id=f"unknown_model_kind:{provider.name}:{model.name}:{model.kind}",
                    kind="unknown_model_kind",
                    severity=classify_issue_severity("unknown_model_kind"),
                    message=f"Model '{model.name}' in provider '{provider.name}' has unknown kind '{model.kind}'",
                    provider_name=provider.name,
                    model_name=model.name,
                    field="kind",
                ))
        
        # Check 7: Provider's default_model doesn't exist
        if provider.default_model:
            model_names = {m.name for m in provider.models}
            if provider.default_model not in model_names:
                issues.append(AiProfileIssue(
                    id=f"invalid_model_reference:{provider.name}:{provider.default_model}",
                    kind="invalid_model_reference",
                    severity=classify_issue_severity("invalid_model_reference"),
                    message=f"Provider '{provider.name}' references non-existent default model '{provider.default_model}'",
                    provider_name=provider.name,
                    model_name=provider.default_model,
                    field="default_model",
                ))
    
    # Check 8: Default provider validation
    if profile_set.default_provider:
        provider_names = {p.name for p in profile_set.providers}
        if profile_set.default_provider not in provider_names:
            issues.append(AiProfileIssue(
                id=f"missing_default_provider:{profile_set.default_provider}",
                kind="missing_default_provider",
                severity="error",  # Explicit reference to non-existent provider is an error
                message=f"Default provider '{profile_set.default_provider}' does not exist",
                provider_name=profile_set.default_provider,
                field="default_provider",
            ))
        else:
            # Check if default provider has models
            default_provider = profile_set.get_provider(profile_set.default_provider)
            if default_provider and not default_provider.models:
                issues.append(AiProfileIssue(
                    id=f"missing_default_model:{profile_set.default_provider}",
                    kind="missing_default_model",
                    severity="error",
                    message=f"Default provider '{profile_set.default_provider}' has no models",
                    provider_name=profile_set.default_provider,
                    field="default_model",
                ))
    elif profile_set.providers:
        # No default provider set - soft warning
        issues.append(AiProfileIssue(
            id="missing_default_provider:none",
            kind="missing_default_provider",
            severity="warning",
            message="No default provider is set",
            field="default_provider",
        ))
    
    # Count issues by severity
    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")
    
    return AiProfileHealth(
        is_valid=error_count == 0,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        issues=issues,
    )


def validate_default_profile_set() -> AiProfileHealth:
    """
    Validate the default AI profile set from settings.
    
    v0.5.12: Convenience wrapper for validate_profile_set().
    
    Builds the default profile set using build_default_ai_profile_set()
    and validates it.
    
    Returns:
        AiProfileHealth with validation results
    """
    from aksara.conf import settings
    
    profile_set = build_default_ai_profile_set(settings)
    return validate_profile_set(profile_set)


# =============================================================================
# Built-in Example Profiles
# =============================================================================

def _build_example_openai_provider() -> AiProviderProfile:
    """
    Build an example OpenAI-like provider for documentation and demos.
    
    This is purely demonstrative - no actual network calls are made.
    """
    return AiProviderProfile(
        name="example_openai_like",
        display_name="Example OpenAI-like Provider (Demo)",
        kind="openai",
        models=[
            AiModelProfile(
                name="gpt-4o",
                display_name="GPT-4 Omni",
                model_id="gpt-4o-2024-05-13",
                kind="chat",
                max_input_tokens=128000,
                max_output_tokens=4096,
                supports_tools=True,
                supports_streaming=True,
                supports_vision=True,
                tags=["fast", "multimodal", "flagship"],
            ),
            AiModelProfile(
                name="gpt-4o-mini",
                display_name="GPT-4 Omni Mini",
                model_id="gpt-4o-mini-2024-07-18",
                kind="chat",
                max_input_tokens=128000,
                max_output_tokens=16384,
                supports_tools=True,
                supports_streaming=True,
                tags=["fast", "cheap", "efficient"],
            ),
            AiModelProfile(
                name="text-embedding-3-large",
                display_name="Text Embedding 3 Large",
                model_id="text-embedding-3-large",
                kind="embedding",
                max_input_tokens=8191,
                max_output_tokens=None,
                supports_tools=False,
                supports_streaming=False,
                tags=["embedding", "search"],
            ),
        ],
        default_model="gpt-4o",
        timeout_seconds=30,
        max_retries=2,
        metadata={
            "_example": True,
            "_description": "This is a demonstrative example provider for documentation purposes.",
        },
    )


def _build_example_anthropic_provider() -> AiProviderProfile:
    """
    Build an example Anthropic-like provider for documentation and demos.
    
    This is purely demonstrative - no actual network calls are made.
    """
    return AiProviderProfile(
        name="example_anthropic_like",
        display_name="Example Anthropic-like Provider (Demo)",
        kind="anthropic",
        models=[
            AiModelProfile(
                name="claude-3-5-sonnet",
                display_name="Claude 3.5 Sonnet",
                model_id="claude-3-5-sonnet-20241022",
                kind="chat",
                max_input_tokens=200000,
                max_output_tokens=8192,
                supports_tools=True,
                supports_streaming=True,
                supports_vision=True,
                tags=["flagship", "reasoning", "long-context"],
            ),
            AiModelProfile(
                name="claude-3-haiku",
                display_name="Claude 3 Haiku",
                model_id="claude-3-haiku-20240307",
                kind="chat",
                max_input_tokens=200000,
                max_output_tokens=4096,
                supports_tools=True,
                supports_streaming=True,
                tags=["fast", "cheap", "efficient"],
            ),
        ],
        default_model="claude-3-5-sonnet",
        timeout_seconds=60,
        max_retries=2,
        metadata={
            "_example": True,
            "_description": "This is a demonstrative example provider for documentation purposes.",
        },
    )


def _build_example_local_provider() -> AiProviderProfile:
    """
    Build an example local/self-hosted provider for documentation and demos.
    
    This is purely demonstrative - no actual network calls are made.
    """
    return AiProviderProfile(
        name="example_local",
        display_name="Example Local Provider (Demo)",
        kind="local",
        base_url="http://localhost:11434/v1",
        models=[
            AiModelProfile(
                name="llama-3-8b",
                display_name="Llama 3 8B",
                model_id="llama3:8b",
                kind="chat",
                max_input_tokens=8192,
                max_output_tokens=2048,
                supports_tools=False,
                supports_streaming=True,
                tags=["local", "open-source"],
            ),
        ],
        default_model="llama-3-8b",
        metadata={
            "_example": True,
            "_description": "This is a demonstrative example for local/Ollama-style providers.",
        },
    )


def _build_example_secret_hints() -> List[AiProviderSecretHint]:
    """Build example secret hints for documentation."""
    return [
        AiProviderSecretHint(
            provider_name="example_openai_like",
            env_var="OPENAI_API_KEY",
            required=True,
            description="OpenAI API key from platform.openai.com",
        ),
        AiProviderSecretHint(
            provider_name="example_anthropic_like",
            env_var="ANTHROPIC_API_KEY",
            required=True,
            description="Anthropic API key from console.anthropic.com",
        ),
        # Local providers typically don't need API keys
    ]


def build_example_profile_set() -> AiProfileSet:
    """
    Build the built-in example profile set for documentation and demos.
    
    These profiles are purely demonstrative - no actual network calls are made.
    They serve as examples for how to configure real providers.
    
    Returns:
        AiProfileSet with example providers
    """
    return AiProfileSet(
        providers=[
            _build_example_openai_provider(),
            _build_example_anthropic_provider(),
            _build_example_local_provider(),
        ],
        default_provider="example_openai_like",
        environment="demo",
        version="0.5.11-example",
    )


# =============================================================================
# AI Provider Registry
# =============================================================================

class AiProviderRegistry:
    """
    Central registry for AI provider profiles.
    
    Manages the collection of configured AI providers and provides
    access methods for discovery and selection.
    
    Should be attached to the Aksara app instance as `app.ai_provider_registry`.
    
    Usage:
        registry = AiProviderRegistry()
        registry.register_profile(my_provider)
        
        # Get all providers
        providers = registry.list_providers()
        
        # Get specific provider
        provider = registry.get_provider("openai_default")
        
        # Get models across providers
        models = registry.list_models(provider_name="openai_default")
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._providers: Dict[str, AiProviderProfile] = {}
        self._default_provider: Optional[str] = None
        self._environment: Optional[str] = None
        self._version: Optional[str] = None
    
    def register_profile(self, provider: AiProviderProfile) -> None:
        """
        Register a provider profile in the registry.
        
        If a provider with the same name exists, it will be overwritten
        with a warning logged.
        
        Args:
            provider: The AiProviderProfile to register
        """
        if provider.name in self._providers:
            logger.warning(
                f"Provider '{provider.name}' already registered, overwriting"
            )
        self._providers[provider.name] = provider
        logger.debug(f"Registered AI provider: {provider.name}")
    
    def get_provider(self, name: str) -> Optional[AiProviderProfile]:
        """
        Get a provider by name.
        
        Args:
            name: The provider name
            
        Returns:
            The AiProviderProfile if found, None otherwise
        """
        return self._providers.get(name)
    
    def list_providers(self) -> List[AiProviderProfile]:
        """
        Get all registered providers.
        
        Returns:
            List of all AiProviderProfile instances
        """
        return list(self._providers.values())
    
    def list_models(
        self, 
        provider_name: Optional[str] = None,
    ) -> List[AiModelProfile]:
        """
        Get models from all or a specific provider.
        
        Args:
            provider_name: If specified, only return models from this provider
            
        Returns:
            List of AiModelProfile instances
        """
        if provider_name:
            provider = self.get_provider(provider_name)
            if provider:
                return list(provider.models)
            return []
        
        # Return all models from all providers
        models = []
        for provider in self._providers.values():
            models.extend(provider.models)
        return models
    
    def get_default_provider(self) -> Optional[AiProviderProfile]:
        """
        Get the default provider.
        
        Returns the provider set as default, or the first registered
        provider if no default is set.
        
        Returns:
            The default AiProviderProfile or None if registry is empty
        """
        if self._default_provider:
            return self.get_provider(self._default_provider)
        
        # Return first provider if no default set
        providers = list(self._providers.values())
        return providers[0] if providers else None
    
    def set_default_provider(self, name: str) -> None:
        """
        Set the default provider.
        
        Args:
            name: Name of the provider to set as default
            
        Raises:
            ValueError: If provider not found
        """
        if name not in self._providers:
            raise ValueError(f"Provider '{name}' not found in registry")
        self._default_provider = name
    
    def get_profile_set(self) -> AiProfileSet:
        """
        Get the complete profile set from the registry.
        
        Returns:
            AiProfileSet containing all registered providers
        """
        return AiProfileSet(
            providers=self.list_providers(),
            default_provider=self._default_provider,
            environment=self._environment,
            version=self._version,
        )
    
    def set_metadata(
        self,
        environment: Optional[str] = None,
        version: Optional[str] = None,
    ) -> None:
        """
        Set profile set metadata.
        
        Args:
            environment: Environment name (dev, stage, prod)
            version: Configuration version string
        """
        if environment is not None:
            self._environment = environment
        if version is not None:
            self._version = version
    
    def clear(self) -> None:
        """Clear all registered providers (useful for testing)."""
        self._providers.clear()
        self._default_provider = None
    
    def __len__(self) -> int:
        """Return number of registered providers."""
        return len(self._providers)
    
    def __contains__(self, name: str) -> bool:
        """Check if a provider is registered."""
        return name in self._providers


# =============================================================================
# Helper Functions
# =============================================================================

def get_ai_provider_registry(
    app: Optional["FastAPI"] = None,
) -> AiProviderRegistry:
    """
    Get the AI provider registry for an app.
    
    If app is provided and has a registry attached, returns that.
    Otherwise creates a new registry.
    
    Args:
        app: Optional FastAPI app instance
        
    Returns:
        AiProviderRegistry instance
    """
    if app is not None:
        # Check for existing registry
        registry = getattr(app, 'ai_provider_registry', None)
        if registry is not None:
            return registry
        
        # Also check app.state
        registry = getattr(getattr(app, 'state', None), 'ai_provider_registry', None)
        if registry is not None:
            return registry
    
    # Create new registry
    return AiProviderRegistry()


def build_default_ai_profile_set(settings: Any) -> AiProfileSet:
    """
    Build an AiProfileSet from settings.
    
    Logic:
    1. If ai_profiles_enabled=False, return empty profile set
    2. If ai_providers is configured, parse and use those
    3. Otherwise, return built-in example profile set
    
    Args:
        settings: Aksara settings object
        
    Returns:
        AiProfileSet configured from settings
    """
    # Check if profiles are enabled
    ai_profiles_enabled = getattr(settings, 'ai_profiles_enabled', True)
    if not ai_profiles_enabled:
        return AiProfileSet(
            providers=[],
            default_provider=None,
            environment=None,
            version="disabled",
        )
    
    # Check for explicit provider configuration
    ai_providers = getattr(settings, 'ai_providers', None)
    
    if ai_providers:
        # Parse from settings
        providers = []
        for provider_dict in ai_providers:
            try:
                # Parse models first
                models = []
                for model_dict in provider_dict.get('models', []):
                    models.append(AiModelProfile(**model_dict))
                
                # Create provider with parsed models
                provider_data = {**provider_dict, 'models': models}
                providers.append(AiProviderProfile(**provider_data))
            except Exception as e:
                logger.warning(f"Failed to parse AI provider config: {e}")
        
        default_provider = getattr(settings, 'ai_default_provider', None)
        if not default_provider and providers:
            default_provider = providers[0].name
        
        return AiProfileSet(
            providers=providers,
            default_provider=default_provider,
            environment=_detect_environment(settings),
            version="0.5.11",
        )
    
    # Return built-in example profiles
    profile_set = build_example_profile_set()
    profile_set.environment = _detect_environment(settings)
    return profile_set


def build_secret_hints_from_settings(settings: Any) -> List[AiProviderSecretHint]:
    """
    Build secret hints from settings.
    
    Args:
        settings: Aksara settings object
        
    Returns:
        List of AiProviderSecretHint instances
    """
    # Check for explicit secret hints
    ai_secret_hints = getattr(settings, 'ai_secret_hints', None)
    
    if ai_secret_hints:
        hints = []
        for hint_dict in ai_secret_hints:
            try:
                hints.append(AiProviderSecretHint(**hint_dict))
            except Exception as e:
                logger.warning(f"Failed to parse AI secret hint: {e}")
        return hints
    
    # Return built-in example hints
    return _build_example_secret_hints()


def _detect_environment(settings: Any) -> str:
    """Detect environment from settings."""
    if getattr(settings, 'debug', False):
        return "development"
    return "production"


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Type aliases
    "AiModelKind",
    "AiProviderKind",
    # Core models
    "AiModelProfile",
    "AiProviderProfile",
    "AiProfileSet",
    # Secret hints
    "AiProviderSecretHint",
    "AiProviderConfigInfo",
    # v0.5.12: Validation models
    "AiProfileIssueSeverity",
    "AiProfileIssueKind",
    "AiProfileIssue",
    "AiProfileHealth",
    # Registry
    "AiProviderRegistry",
    # Helper functions
    "get_ai_provider_registry",
    "build_default_ai_profile_set",
    "build_secret_hints_from_settings",
    "build_example_profile_set",
    # v0.5.12: Validation functions
    "classify_issue_severity",
    "validate_profile_set",
    "validate_default_profile_set",
]
