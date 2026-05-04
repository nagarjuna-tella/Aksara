"""
AI Providers Example - Application Wiring

v0.5.14: Complete example app showing AI provider integration.

This demonstrates:
1. Settings configuration from environment
2. App initialization with AI features
3. ViewSet registration with AI hints
4. Runtime client instantiation

Run with:
    aksara dev

Required environment variables:
    OPENAI_API_KEY=sk-...
    # or
    AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
    AZURE_OPENAI_API_KEY=...
    AZURE_OPENAI_DEPLOYMENT=your-deployment
    # or
    ANTHROPIC_API_KEY=sk-ant-...
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

# Aksara imports
from aksara import Aksara
from aksara.api import include_viewset

# Local imports
from .settings import settings
from .adapters import get_llm_client_from_settings, check_sdk_availability
from .views import DemoPostViewSet, get_ai_client_status

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ai_providers.main")


# =============================================================================
# Application Setup
# =============================================================================

@asynccontextmanager
async def lifespan(app: Aksara):
    """
    App lifespan manager.
    
    On startup:
    - Validate AI configuration
    - Log provider status
    
    On shutdown:
    - Clean up resources
    """
    # Startup
    logger.info("Starting AI Providers Example App")
    
    # Check SDK availability
    sdks = check_sdk_availability()
    logger.info(f"SDK availability: {sdks}")
    
    # Log configured providers
    configured = settings.get_configured_providers()
    logger.info(f"Configured providers: {configured}")
    
    # Validate configuration
    is_valid, issues = settings.validate_ai_config()
    if not is_valid:
        logger.warning(f"AI configuration issues: {issues}")
    else:
        logger.info("AI configuration validated successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AI Providers Example App")


# Create the Aksara app
app = Aksara(
    title="AI Providers Example",
    description="Demonstrates AI provider wiring patterns for Aksara",
    version="0.5.45",
    lifespan=lifespan,
    settings=settings,
)


# =============================================================================
# Register ViewSets
# =============================================================================

# Register the demo ViewSet with AI actions
include_viewset(app, DemoPostViewSet)


# =============================================================================
# Additional Routes
# =============================================================================

@app.get("/health")
def health_check():
    """Basic health check."""
    return {"status": "ok", "version": "0.5.14"}


@app.get("/ai/status")
def ai_status():
    """
    Get AI provider status.
    
    Returns:
    - default_provider: Currently selected provider
    - sdk_availability: Which SDKs are installed
    - configured_providers: Which providers have credentials
    - ready: Whether at least one provider is ready
    """
    return get_ai_client_status(settings)


@app.get("/ai/providers")
def list_providers():
    """
    List available AI providers with their status.
    """
    sdks = check_sdk_availability()
    
    providers = []
    
    # OpenAI
    openai_configured = settings.is_provider_configured("openai")
    providers.append({
        "name": "openai",
        "display_name": "OpenAI",
        "sdk_installed": sdks.get("openai", False),
        "configured": openai_configured,
        "ready": sdks.get("openai", False) and openai_configured,
        "default_model": settings.OPENAI_DEFAULT_MODEL,
    })
    
    # Azure OpenAI
    azure_configured = settings.is_provider_configured("azure")
    providers.append({
        "name": "azure",
        "display_name": "Azure OpenAI",
        "sdk_installed": sdks.get("openai", False),  # Uses openai SDK
        "configured": azure_configured,
        "ready": sdks.get("openai", False) and azure_configured,
        "deployment": settings.AZURE_OPENAI_DEPLOYMENT or "(not set)",
    })
    
    # Anthropic
    anthropic_configured = settings.is_provider_configured("anthropic")
    providers.append({
        "name": "anthropic",
        "display_name": "Anthropic Claude",
        "sdk_installed": sdks.get("anthropic", False),
        "configured": anthropic_configured,
        "ready": sdks.get("anthropic", False) and anthropic_configured,
        "default_model": settings.ANTHROPIC_DEFAULT_MODEL,
    })
    
    return {
        "providers": providers,
        "default": settings.AI_DEFAULT_PROVIDER,
    }


@app.post("/ai/test")
async def test_ai_connection(provider: str = None):
    """
    Test AI provider connection.
    
    Args:
        provider: Provider to test (openai, azure, anthropic).
                  Uses default if not specified.
    
    Returns:
        Test result with model response.
    """
    provider = provider or settings.AI_DEFAULT_PROVIDER
    
    try:
        client = get_llm_client_from_settings(settings, provider_override=provider)
        
        # Simple test prompt
        from aksara.ai.providers import AiModelProfile
        
        if provider == "azure":
            model_name = settings.AZURE_OPENAI_DEPLOYMENT or "gpt-4o-mini"
        elif provider == "anthropic":
            model_name = settings.ANTHROPIC_DEFAULT_MODEL
        else:
            model_name = settings.OPENAI_DEFAULT_MODEL
        
        profile = AiModelProfile(
            model_name=model_name,
            model_kind="chat",
            provider=provider,
        )
        
        response = await client.complete(
            "Say 'Hello from Aksara!' in exactly 5 words.",
            model=profile,
        )
        
        return {
            "success": True,
            "provider": provider,
            "model": model_name,
            "response": response.strip(),
        }
        
    except RuntimeError as e:
        return {
            "success": False,
            "provider": provider,
            "error": str(e),
            "suggestion": f"Install SDK: pip install {'openai' if provider in ['openai', 'azure'] else provider}",
        }
    except Exception as e:
        return {
            "success": False,
            "provider": provider,
            "error": str(e),
        }


# =============================================================================
# CLI Entry Point
# =============================================================================

def run():
    """
    Run the example app directly.
    
    Usage:
        python -m examples.ai_providers.main
    """
    import uvicorn
    
    logger.info("Starting AI Providers Example on http://127.0.0.1:8080")
    logger.info("API docs at http://127.0.0.1:8080/docs")
    logger.info("AI status at http://127.0.0.1:8080/ai/status")
    
    uvicorn.run(
        "examples.ai_providers.main:app",
        host="127.0.0.1",
        port=8080,
        reload=True,
    )


if __name__ == "__main__":
    run()
