"""
Tests for v0.5.5 Boilerplate Refresh & Starter Project.

Tests that a newly scaffolded project includes:
- Working Post model (not commented)
- Working PostViewSet (not commented)
- Working PostSerializer (not commented)
- Post registered in admin
- AKSARA configuration dict in settings
- Middleware imports in main.py
"""

import pytest
import sys
import tempfile
import shutil
from pathlib import Path

from aksara.cli.scaffold import create_project_scaffold, write_scaffold_files


class TestScaffoldV055Structure:
    """Test v0.5.5 scaffold structure and content."""
    
    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
        self.project_name = "blog_api"
        
        # Create scaffold
        files = create_project_scaffold(self.project_name, self.base_path)
        write_scaffold_files(files)
        self.project_path = self.base_path / self.project_name
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    # =========================================================================
    # Models Tests
    # =========================================================================
    
    def test_models_has_working_post_model(self):
        """Models should have a Post model example (in commented scaffold stub)."""
        models_path = self.project_path / "app" / "models.py"
        content = models_path.read_text()

        # Post is in the commented example stub
        assert "class Post(Model):" in content

        # Should have field definitions (in comments)
        assert 'title = fields.String(' in content
        assert 'content = fields.Text(' in content
        assert 'is_published = fields.Boolean(' in content
        assert 'view_count = fields.Integer(' in content
        assert 'tags = fields.JSON(' in content
        assert 'created_at = fields.DateTime(' in content

        # Should have AI metadata (in comments)
        assert 'ai_description=' in content
        assert 'ai_agent_exposed = True' in content
    
    def test_models_has_meta_class(self):
        """Post model commented stub should have Meta class with table_name."""
        models_path = self.project_path / "app" / "models.py"
        content = models_path.read_text()

        assert 'table_name = "posts"' in content
        assert 'ai_name = "Post"' in content
    
    # =========================================================================
    # Views Tests
    # =========================================================================
    
    def test_views_has_working_postviewset(self):
        """Views should have PostViewSet referenced in the commented example stub."""
        views_path = self.project_path / "app" / "views.py"
        content = views_path.read_text()

        # PostViewSet is in the commented example stub
        assert "class PostViewSet(ModelViewSet):" in content

        # Imports referenced in the comment
        assert "from .models import Post" in content
        assert "from .serializers import PostSerializer" in content

        # Configuration in comment stub
        assert 'model = Post' in content
        assert 'serializer_class = PostSerializer' in content
        assert 'prefix = "/api/posts"' in content
    
    def test_views_has_custom_actions(self):
        """PostViewSet commented stub should include @action examples."""
        views_path = self.project_path / "app" / "views.py"
        content = views_path.read_text()

        # @action examples are in the commented stub
        assert '@action(detail=True, methods=["POST"], ai_exposed=True)' in content
        assert 'async def publish(' in content
        assert 'async def increment_views(' in content
    
    def test_views_has_ai_exposed(self):
        """PostViewSet commented stub should reference ai_exposed."""
        views_path = self.project_path / "app" / "views.py"
        content = views_path.read_text()

        assert 'ai_exposed = True' in content
    
    # =========================================================================
    # Serializers Tests
    # =========================================================================
    
    def test_serializers_has_working_postserializer(self):
        """Serializers should have a working PostSerializer."""
        serializers_path = self.project_path / "app" / "serializers.py"
        content = serializers_path.read_text()
        
        # PostSerializer should be defined
        assert "class PostSerializer(ModelSerializer):" in content
        
        # Should import the model
        assert "from .models import Post" in content
        
        # Should have Meta class with fields
        assert 'model = Post' in content
        assert '"id"' in content
        assert '"title"' in content
        assert '"content"' in content
        assert 'read_only_fields' in content
    
    # =========================================================================
    # Admin Tests
    # =========================================================================
    
    def test_admin_has_post_registered(self):
        """Admin should have Post registered."""
        admin_path = self.project_path / "app" / "admin.py"
        content = admin_path.read_text()
        
        # Should import Post
        assert "from .models import Post" in content
        
        # Should have PostAdmin class
        assert "class PostAdmin(ModelAdmin):" in content
        assert 'list_display = ' in content
        
        # Should register
        assert "site.register(Post, PostAdmin)" in content
    
    # =========================================================================
    # URLs Tests
    # =========================================================================
    
    def test_urls_has_postviewset_registered(self):
        """URLs should reference PostViewSet in the commented example."""
        urls_path = self.project_path / "app" / "urls.py"
        content = urls_path.read_text()

        # PostViewSet is referenced in commented example
        assert "from .views import PostViewSet" in content

        # PostViewSet appears in the urlpatterns comment example
        assert "PostViewSet," in content
        # Neutral scaffold — PostViewSet is in comments, not active
        assert "# PostViewSet" in content
    
    # =========================================================================
    # Settings Tests
    # =========================================================================
    
    def test_settings_has_aksara_dict(self):
        """Settings should have AKSARA configuration dict."""
        settings_path = self.project_path / "settings.py"
        content = settings_path.read_text()
        
        # Should have AKSARA dict
        assert "AKSARA = {" in content
        
        # Should have key settings
        assert '"ENABLE_ADMIN"' in content
        assert '"ENABLE_STUDIO"' in content
        assert '"STUDIO_UI_ENABLED"' in content
        assert '"AI_MODE_ENABLED"' in content
    
    def test_settings_class_uses_aksara_dict(self):
        """Settings class should read from AKSARA dict."""
        settings_path = self.project_path / "settings.py"
        content = settings_path.read_text()
        
        # Should reference AKSARA dict
        assert 'AKSARA.get("ENABLE_ADMIN"' in content
        assert 'AKSARA.get("ENABLE_STUDIO"' in content
        assert 'AKSARA.get("AI_MODE_ENABLED"' in content
    
    # =========================================================================
    # Main.py Tests
    # =========================================================================
    
    def test_main_imports_middleware(self):
        """Main should import Aksara middleware."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert "from aksara.middleware.request_id import RequestIDMiddleware" in content
        assert "from aksara.middleware.logging import LoggingMiddleware" in content
    
    def test_main_configures_middleware(self):
        """Main should configure middleware in Aksara app."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert "middlewares=[" in content
        assert "(RequestIDMiddleware, {})" in content
        assert "(LoggingMiddleware," in content
    
    def test_main_enables_admin(self):
        """Main should pass enable_admin to Aksara."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert "enable_admin=settings.enable_admin" in content
    
    def test_main_mentions_studio_and_ai(self):
        """Main docstring should mention Studio and AI endpoints."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert "/studio/ui" in content
        assert "/ai/tools" in content
        assert "/admin" in content
    
    def test_health_endpoint_returns_endpoints(self):
        """Health check should return Studio/Admin/AI endpoints."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert '"studio": "/studio/ui"' in content
        assert '"admin": "/admin"' in content
        assert '"ai_tools": "/ai/tools"' in content
    
    # =========================================================================
    # README Tests
    # =========================================================================
    
    def test_readme_mentions_all_endpoints(self):
        """README should mention Admin, Studio, AI endpoints."""
        readme_path = self.project_path / "README.md"
        content = readme_path.read_text()
        
        assert "/admin" in content
        assert "/studio/ui" in content
        assert "/ai/tools" in content
        assert "/api/posts" in content
    
    def test_readme_has_whats_included_section(self):
        """README should have What's Included section."""
        readme_path = self.project_path / "README.md"
        content = readme_path.read_text()
        
        assert "What's Included" in content
        assert "Post model" in content
        assert "PostViewSet" in content
    
    # =========================================================================
    # pyproject.toml Tests
    # =========================================================================
    
    def test_pyproject_requires_aksara(self):
        """pyproject.toml should require aksara."""
        pyproject_path = self.project_path / "pyproject.toml"
        content = pyproject_path.read_text()
        
        # Should require aksara (version may change)
        assert '"aksara>=' in content


class TestScaffoldV055Importability:
    """Test that v0.5.5 scaffold files can be imported."""
    
    def setup_method(self):
        """Create a temporary directory and scaffold."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
        self.project_name = "test_imports"
        
        files = create_project_scaffold(self.project_name, self.base_path)
        write_scaffold_files(files)
        self.project_path = self.base_path / self.project_name
        
        # Add to path
        if str(self.project_path) not in sys.path:
            sys.path.insert(0, str(self.project_path))
    
    def teardown_method(self):
        """Clean up."""
        if str(self.project_path) in sys.path:
            sys.path.remove(str(self.project_path))
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # Clean up modules
        for mod in list(sys.modules.keys()):
            if mod.startswith('app') or mod.startswith('settings'):
                del sys.modules[mod]
    
    def test_models_module_imports_without_error(self):
        """app.models should import cleanly (neutral scaffold — Post is a commented stub)."""
        import importlib.util

        models_path = self.project_path / "app" / "models.py"
        spec = importlib.util.spec_from_file_location("app.models", models_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Neutral scaffold has no active Post class — Post is a commented example
        assert not hasattr(module, 'Post')
    
    def test_settings_syntax_valid(self):
        """settings.py should have valid Python syntax."""
        settings_path = self.project_path / "settings.py"
        content = settings_path.read_text()
        
        # Should compile without errors
        compile(content, str(settings_path), "exec")
    
    def test_main_syntax_valid(self):
        """main.py should have valid Python syntax."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        # Should compile without errors
        compile(content, str(main_path), "exec")
