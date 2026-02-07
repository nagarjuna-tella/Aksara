"""
AI Providers Example Package

v0.5.14: Demonstrates how to wire Aksara's AI contracts to popular providers
(OpenAI, Azure OpenAI, Anthropic) without adding hard dependencies.

This package shows:
- Environment-based provider configuration
- Protocol-based adapter pattern with soft SDK imports
- Prompt building from AiRouteHint metadata
- End-to-end wiring examples

IMPORTANT: This is an EXAMPLE package. Copy these patterns into your own
project and install provider SDKs there - Aksara core does not depend on
any provider SDKs.

Usage:
    # 1. Copy adapters.py to your project
    # 2. Install provider SDK: pip install openai  (or anthropic, etc.)
    # 3. Set environment variables: OPENAI_API_KEY, etc.
    # 4. Use the adapter in your views/routes

Example:
    from your_project.ai_adapters import get_llm_client
    from aksara.ai import build_default_ai_profile_set
    
    profiles = build_default_ai_profile_set(settings)
    client = get_llm_client(profiles.default_provider, settings)
    response = await client.complete("Hello!", model=profiles.default_model)
"""

from .settings import Settings, settings
from .adapters import (
    LlmClient,
    BaseLlmClient,
    get_llm_client,
    get_llm_client_from_settings,
    check_sdk_availability,
    OpenAIClient,
    AzureOpenAIClient,
    AnthropicClient,
)
from .prompting import (
    build_prompt_for_route,
    build_chat_messages_for_route,
    format_structured_output_prompt,
    parse_json_response,
    extract_tags_from_response,
    get_tag_suggestion_prompt,
    get_content_summary_prompt,
)

# Lazy imports for views and app (to avoid import errors when
# aksara.api is not fully configured)
def __getattr__(name):
    """Lazy import for optional components."""
    if name in ("DemoPostViewSet", "get_ai_client_status"):
        from .views import DemoPostViewSet, get_ai_client_status
        return DemoPostViewSet if name == "DemoPostViewSet" else get_ai_client_status
    elif name in ("app", "run"):
        from .main import app, run
        return app if name == "app" else run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # Settings
    "Settings",
    "settings",
    # Adapters
    "LlmClient",
    "BaseLlmClient",
    "get_llm_client",
    "get_llm_client_from_settings",
    "check_sdk_availability",
    "OpenAIClient",
    "AzureOpenAIClient",
    "AnthropicClient",
    # Prompting
    "build_prompt_for_route",
    "build_chat_messages_for_route",
    "format_structured_output_prompt",
    "parse_json_response",
    "extract_tags_from_response",
    "get_tag_suggestion_prompt",
    "get_content_summary_prompt",
    # Views & App (lazy)
    "DemoPostViewSet",
    "get_ai_client_status",
    "app",
    "run",
]
