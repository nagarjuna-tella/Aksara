"""
AI Providers Example - Settings

v0.5.14: Shows how to configure AI providers via environment variables.

This demonstrates the recommended pattern for provider configuration:
- All secrets come from environment variables
- Default provider selection is configurable
- Settings integrate with Aksara's AiProfileSet

IMPORTANT: Never hardcode API keys or secrets in your code.
"""

import os
from typing import Optional

from aksara.conf import Settings as AksaraSettings


class Settings(AksaraSettings):
    """
    Example settings class with AI provider configuration.
    
    Copy this pattern to your own project and customize as needed.
    
    Environment Variables Expected:
        OPENAI_API_KEY          - OpenAI API key
        AZURE_OPENAI_ENDPOINT   - Azure OpenAI endpoint URL
        AZURE_OPENAI_API_KEY    - Azure OpenAI API key
        AZURE_OPENAI_DEPLOYMENT - Azure OpenAI deployment name
        ANTHROPIC_API_KEY       - Anthropic API key
        AI_DEFAULT_PROVIDER     - Default provider: "openai", "azure", "anthropic"
    """
    
    # ==========================================================================
    # Provider Selection
    # ==========================================================================
    
    # Which provider to use by default
    AI_DEFAULT_PROVIDER: str = os.getenv("AI_DEFAULT_PROVIDER", "openai")
    
    # ==========================================================================
    # OpenAI Configuration
    # ==========================================================================
    
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_ORG_ID: Optional[str] = os.getenv("OPENAI_ORG_ID")
    OPENAI_DEFAULT_MODEL: str = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")
    
    # ==========================================================================
    # Azure OpenAI Configuration
    # ==========================================================================
    
    AZURE_OPENAI_ENDPOINT: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_KEY: Optional[str] = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_DEPLOYMENT: Optional[str] = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
    
    # ==========================================================================
    # Anthropic Configuration
    # ==========================================================================
    
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_DEFAULT_MODEL: str = os.getenv("ANTHROPIC_DEFAULT_MODEL", "claude-3-5-sonnet-20241022")
    
    # ==========================================================================
    # General AI Settings
    # ==========================================================================
    
    AI_DEFAULT_MAX_TOKENS: int = int(os.getenv("AI_DEFAULT_MAX_TOKENS", "1024"))
    AI_DEFAULT_TEMPERATURE: float = float(os.getenv("AI_DEFAULT_TEMPERATURE", "0.7"))
    
    def is_provider_configured(self, provider: str) -> bool:
        """
        Check if a provider has its required credentials configured.
        
        Args:
            provider: Provider name ("openai", "azure", "anthropic")
            
        Returns:
            True if provider credentials are present
        """
        if provider == "openai":
            return bool(self.OPENAI_API_KEY)
        elif provider == "azure":
            return bool(
                self.AZURE_OPENAI_ENDPOINT
                and self.AZURE_OPENAI_API_KEY
                and self.AZURE_OPENAI_DEPLOYMENT
            )
        elif provider == "anthropic":
            return bool(self.ANTHROPIC_API_KEY)
        return False
    
    def get_configured_providers(self) -> list[str]:
        """
        Get list of providers that have credentials configured.
        
        Returns:
            List of configured provider names
        """
        providers = []
        for provider in ["openai", "azure", "anthropic"]:
            if self.is_provider_configured(provider):
                providers.append(provider)
        return providers
    
    def validate_ai_config(self) -> list[str]:
        """
        Validate AI configuration and return any issues.
        
        Returns:
            List of configuration issues (empty if all good)
        """
        issues = []
        
        # Check default provider is configured
        if not self.is_provider_configured(self.AI_DEFAULT_PROVIDER):
            issues.append(
                f"Default provider '{self.AI_DEFAULT_PROVIDER}' is not configured. "
                f"Set the required environment variables or change AI_DEFAULT_PROVIDER."
            )
        
        # Check at least one provider is available
        configured = self.get_configured_providers()
        if not configured:
            issues.append(
                "No AI providers are configured. Set at least one of: "
                "OPENAI_API_KEY, AZURE_OPENAI_*, or ANTHROPIC_API_KEY"
            )
        
        return issues


# Global settings instance for this example app
settings = Settings()
