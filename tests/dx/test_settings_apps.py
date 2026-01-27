"""
Tests for settings.apps multi-app configuration.
"""

import pytest
import aksara.conf
from aksara.conf import Settings, configure, reset_settings


def get_settings():
    """Get current settings (reimport to get fresh reference)."""
    return aksara.conf.settings


class TestSettingsApps:
    """Tests for the apps configuration in settings."""
    
    def test_default_apps_value(self):
        """Settings should have a default apps list."""
        s = Settings()
        assert s.apps == ["app"]
    
    def test_custom_apps_value(self):
        """Settings should accept custom apps list."""
        s = Settings(apps=["blog", "users", "orders"])
        assert s.apps == ["blog", "users", "orders"]
    
    def test_single_app_value(self):
        """Settings should accept a single app."""
        s = Settings(apps=["myapp"])
        assert s.apps == ["myapp"]
    
    def test_empty_apps_list(self):
        """Settings should accept an empty apps list."""
        s = Settings(apps=[])
        assert s.apps == []


class TestConfigureWithApps:
    """Tests for configure() function with apps parameter."""
    
    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()
    
    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()
    
    def test_configure_with_apps(self):
        """configure() should set apps in global settings."""
        configure(
            apps=["blog", "users"],
            database_url="postgresql://test:test@localhost/test"
        )
        # Access via module to get fresh reference
        assert aksara.conf.settings.apps == ["blog", "users"]
        assert aksara.conf.settings.database_url == "postgresql://test:test@localhost/test"
    
    def test_configure_default_apps(self):
        """configure() without apps should use current value."""
        reset_settings()  # Ensure clean state
        configure(
            database_url="postgresql://test:test@localhost/testdb"
        )
        # Default is ["app"]
        assert aksara.conf.settings.apps == ["app"]
    
    def test_configure_with_settings_object(self):
        """configure() should accept a Settings object with apps."""
        custom_settings = Settings(
            apps=["api", "admin", "auth"],
            database_url="postgresql://test:test@localhost/custom"
        )
        configure(custom_settings)
        assert aksara.conf.settings.apps == ["api", "admin", "auth"]
