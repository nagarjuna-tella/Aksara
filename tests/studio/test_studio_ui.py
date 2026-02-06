"""
Tests for Aksara Studio UI (v0.5.3).

Tests:
- GET /studio/ui - Dashboard HTML
- GET /studio/assets/* - Static assets (CSS, JS, icons)
- Origin security for UI
- Studio disabled scenarios
- CLI commands: studio open, studio ui-path
"""

import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
from fastapi.testclient import TestClient
from fastapi import FastAPI

from aksara.studio.fastapi import router, STATIC_DIR, get_static_dir


# =============================================================================
# Test Setup
# =============================================================================

def create_test_app() -> FastAPI:
    """Create a test FastAPI app with Studio router."""
    app = FastAPI(title="Test App", version="1.0.0")
    app.include_router(router)
    return app


def create_mock_settings(
    enable_studio: bool = True,
    studio_ui_enabled: bool = True,
    debug: bool = True,
    studio_expose_in_production: bool = False,
    studio_allowed_origins: list = None,
):
    """Create mock settings for testing."""
    mock_settings = MagicMock()
    mock_settings.enable_studio = enable_studio
    mock_settings.studio_ui_enabled = studio_ui_enabled
    mock_settings.debug = debug
    mock_settings.studio_expose_in_production = studio_expose_in_production
    mock_settings.studio_allowed_origins = studio_allowed_origins or ["*"]
    return mock_settings


# =============================================================================
# Studio UI Endpoint Tests
# =============================================================================

class TestStudioUIEndpoint:
    """Tests for GET /studio/ui endpoint."""
    
    def test_studio_ui_loads(self):
        """UI endpoint returns HTML with expected markers."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/ui")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert '<div id="root">' in response.text
        assert "Aksara Studio" in response.text
    
    def test_studio_ui_version_header(self):
        """UI response includes version header."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/ui")
        
        assert response.status_code == 200
        assert "X-Aksara-Studio-Version" in response.headers
    
    def test_studio_ui_no_cache(self):
        """UI response has no-store cache control."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/ui")
        
        assert response.status_code == 200
        assert "no-store" in response.headers.get("cache-control", "")
    
    def test_studio_ui_has_required_elements(self):
        """UI HTML contains all required elements."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/ui")
        
        assert response.status_code == 200
        html = response.text
        
        # Required meta tags
        assert '<meta charset="utf-8">' in html
        assert '<meta name="viewport"' in html
        
        # Required structure
        assert '<aside id="sidebar">' in html
        assert '<main id="content">' in html
        
        # Required assets
        assert '/studio/assets/styles.css' in html
        assert '/studio/assets/app.js' in html


# =============================================================================
# Static Asset Tests
# =============================================================================

class TestStudioAssets:
    """Tests for GET /studio/assets/* endpoint."""
    
    def test_css_asset(self):
        """CSS file is served with correct content type."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/assets/styles.css")
        
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]
    
    def test_js_asset(self):
        """JS file is served with correct content type."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/assets/app.js")
        
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]
    
    def test_svg_asset(self):
        """SVG icon is served with correct content type."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/assets/icons/aksara-logo.svg")
        
        assert response.status_code == 200
        assert "image/svg+xml" in response.headers["content-type"]
    
    def test_missing_asset_404(self):
        """Missing asset returns 404."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/assets/nonexistent.xyz")
        
        assert response.status_code == 404
    
    def test_directory_traversal_blocked(self):
        """Directory traversal attempts are blocked."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/assets/../../../etc/passwd")
        
        assert response.status_code in (400, 403, 404)
    
    def test_asset_cache_control(self):
        """Assets have cache control headers."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/assets/styles.css")
        
        assert response.status_code == 200
        cache_control = response.headers.get("cache-control", "")
        assert "max-age" in cache_control


# =============================================================================
# Origin Security Tests
# =============================================================================

class TestStudioUIOriginSecurity:
    """Tests for origin-based security on UI endpoints."""
    
    def test_ui_allowed_origin(self):
        """UI loads for allowed origin."""
        app = create_test_app()
        client = TestClient(app)
        
        settings = create_mock_settings(
            studio_allowed_origins=["http://localhost:3000"]
        )
        
        with patch("aksara.conf.settings", settings):
            response = client.get(
                "/studio/ui",
                headers={"Origin": "http://localhost:3000"}
            )
        
        assert response.status_code == 200
    
    def test_ui_blocked_origin(self):
        """UI blocked for disallowed origin."""
        app = create_test_app()
        client = TestClient(app)
        
        settings = create_mock_settings(
            studio_allowed_origins=["http://localhost:3000"]
        )
        
        with patch("aksara.conf.settings", settings):
            response = client.get(
                "/studio/ui",
                headers={"Origin": "https://evil.com"}
            )
        
        assert response.status_code == 403
    
    def test_ui_wildcard_origin(self):
        """UI allows all origins with wildcard."""
        app = create_test_app()
        client = TestClient(app)
        
        settings = create_mock_settings(
            studio_allowed_origins=["*"]
        )
        
        with patch("aksara.conf.settings", settings):
            response = client.get(
                "/studio/ui",
                headers={"Origin": "https://any-domain.com"}
            )
        
        assert response.status_code == 200


# =============================================================================
# Studio Disabled Tests
# =============================================================================

class TestStudioUIDisabled:
    """Tests for when Studio UI is disabled."""
    
    def test_studio_disabled(self):
        """UI returns 404 when Studio is disabled."""
        app = create_test_app()
        client = TestClient(app)
        
        settings = create_mock_settings(enable_studio=False)
        
        with patch("aksara.conf.settings", settings):
            response = client.get("/studio/ui")
        
        assert response.status_code == 404
    
    def test_studio_ui_disabled(self):
        """UI returns 404 when Studio UI specifically is disabled."""
        app = create_test_app()
        client = TestClient(app)
        
        settings = create_mock_settings(studio_ui_enabled=False)
        
        with patch("aksara.conf.settings", settings):
            response = client.get("/studio/ui")
        
        assert response.status_code == 404
    
    def test_production_mode_no_expose(self):
        """UI returns 403 in production without expose flag."""
        app = create_test_app()
        client = TestClient(app)
        
        settings = create_mock_settings(
            debug=False,
            studio_expose_in_production=False
        )
        
        with patch("aksara.conf.settings", settings):
            response = client.get("/studio/ui")
        
        assert response.status_code == 403
    
    def test_production_mode_with_expose(self):
        """UI loads in production with expose flag."""
        app = create_test_app()
        client = TestClient(app)
        
        settings = create_mock_settings(
            debug=False,
            studio_expose_in_production=True
        )
        
        with patch("aksara.conf.settings", settings):
            response = client.get("/studio/ui")
        
        assert response.status_code == 200


# =============================================================================
# Static Directory Tests
# =============================================================================

class TestStudioStaticDir:
    """Tests for static directory utilities."""
    
    def test_static_dir_exists(self):
        """Static directory exists."""
        assert STATIC_DIR.exists()
        assert STATIC_DIR.is_dir()
    
    def test_static_dir_has_index(self):
        """Static directory contains index.html."""
        index_path = STATIC_DIR / "index.html"
        assert index_path.exists()
    
    def test_static_dir_has_css(self):
        """Static directory contains styles.css."""
        css_path = STATIC_DIR / "styles.css"
        assert css_path.exists()
    
    def test_static_dir_has_js(self):
        """Static directory contains app.js."""
        js_path = STATIC_DIR / "app.js"
        assert js_path.exists()
    
    def test_static_dir_has_icons(self):
        """Static directory contains icons."""
        icons_dir = STATIC_DIR / "icons"
        assert icons_dir.exists()
        assert (icons_dir / "aksara-logo.svg").exists()
    
    def test_get_static_dir_function(self):
        """get_static_dir returns correct path."""
        result = get_static_dir()
        assert result == STATIC_DIR
        assert "aksara/studio/static" in str(result)


# =============================================================================
# CLI Tests
# =============================================================================

class TestStudioUICLI:
    """Tests for Studio UI CLI commands."""
    
    def test_cli_ui_path(self):
        """aksara studio ui-path shows path."""
        from click.testing import CliRunner
        from aksara.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ["studio", "ui-path"])
        
        assert result.exit_code == 0
        assert "aksara/studio/static" in result.output
    
    def test_cli_open_mocked(self):
        """aksara studio open calls webbrowser.open."""
        from click.testing import CliRunner
        from aksara.cli.main import cli
        
        runner = CliRunner()
        
        with patch("webbrowser.open") as mock_open:
            result = runner.invoke(cli, ["studio", "open"])
        
        assert result.exit_code == 0
        mock_open.assert_called_once()
        call_url = mock_open.call_args[0][0]
        assert "/studio/ui" in call_url
    
    def test_cli_open_custom_port(self):
        """aksara studio open respects --port option."""
        from click.testing import CliRunner
        from aksara.cli.main import cli
        
        runner = CliRunner()
        
        with patch("webbrowser.open") as mock_open:
            result = runner.invoke(cli, ["studio", "open", "--port", "8080"])
        
        assert result.exit_code == 0
        call_url = mock_open.call_args[0][0]
        assert ":8080" in call_url
    
    def test_cli_open_https(self):
        """aksara studio open respects --https option."""
        from click.testing import CliRunner
        from aksara.cli.main import cli
        
        runner = CliRunner()
        
        with patch("webbrowser.open") as mock_open:
            result = runner.invoke(cli, ["studio", "open", "--https"])
        
        assert result.exit_code == 0
        call_url = mock_open.call_args[0][0]
        assert call_url.startswith("https://")
    
    def test_cli_url_shows_ui(self):
        """aksara studio url includes UI URL."""
        from click.testing import CliRunner
        from aksara.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ["studio", "url"])
        
        assert result.exit_code == 0
        assert "/studio/ui" in result.output


# =============================================================================
# HTML Content Validation
# =============================================================================

class TestStudioUIContent:
    """Tests for UI HTML content integrity."""
    
    def test_html_has_templates(self):
        """HTML contains all required templates."""
        index_path = STATIC_DIR / "index.html"
        html = index_path.read_text()
        
        templates = [
            'template-overview',
            'template-models',
            'template-routes',
            'template-migrations',
            'template-diagnostics',
            'template-api',
        ]
        
        for template_id in templates:
            assert f'id="{template_id}"' in html, f"Missing template: {template_id}"
    
    def test_html_has_nav_items(self):
        """HTML contains navigation items."""
        index_path = STATIC_DIR / "index.html"
        html = index_path.read_text()
        
        nav_sections = ['overview', 'models', 'routes', 'migrations', 'diagnostics', 'api']
        
        for section in nav_sections:
            assert f'data-section="{section}"' in html, f"Missing nav item: {section}"
    
    def test_html_has_theme_toggle(self):
        """HTML contains theme toggle button."""
        index_path = STATIC_DIR / "index.html"
        html = index_path.read_text()
        
        assert 'id="theme-toggle"' in html


# =============================================================================
# CSS Content Validation
# =============================================================================

class TestStudioUIStyles:
    """Tests for UI CSS content."""
    
    def test_css_has_themes(self):
        """CSS contains light and dark theme variables."""
        css_path = STATIC_DIR / "styles.css"
        css = css_path.read_text()
        
        assert 'data-theme="light"' in css
        assert 'data-theme="dark"' in css
    
    def test_css_has_status_classes(self):
        """CSS contains status badge classes."""
        css_path = STATIC_DIR / "styles.css"
        css = css_path.read_text()
        
        assert '.status.ok' in css
        assert '.status.warning' in css
        assert '.status.error' in css


# =============================================================================
# JS Content Validation
# =============================================================================

class TestStudioUIScript:
    """Tests for UI JavaScript content."""
    
    def test_js_has_render_functions(self):
        """JS contains all render functions."""
        js_path = STATIC_DIR / "app.js"
        js = js_path.read_text()
        
        render_functions = [
            'renderOverview',
            'renderModels',
            'renderRoutes',
            'renderMigrations',
            'renderDiagnostics',
        ]
        
        for func in render_functions:
            assert f'function {func}' in js, f"Missing function: {func}"
    
    def test_js_has_json_get(self):
        """JS contains jsonGet helper."""
        js_path = STATIC_DIR / "app.js"
        js = js_path.read_text()
        
        assert 'async function jsonGet' in js
    
    def test_js_has_theme_management(self):
        """JS contains theme management functions."""
        js_path = STATIC_DIR / "app.js"
        js = js_path.read_text()
        
        assert 'function initTheme' in js
        assert 'function toggleTheme' in js
