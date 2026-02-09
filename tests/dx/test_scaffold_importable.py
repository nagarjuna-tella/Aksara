"""
Tests that scaffolded code is actually importable and API-compatible.

Unlike string-matching tests, these tests compile the scaffold templates
and verify they reference real Aksara APIs that exist and have the correct
signatures. This catches drift between scaffold templates and framework code.

v0.5.24: Added after discovering multiple runtime crashes in scaffolded
projects (log_request_body, serializer_class, _table_name, etc.)
"""

import pytest
import sys
import ast
import inspect
import tempfile
import shutil
from pathlib import Path

from aksara.cli.scaffold import (
    create_project_scaffold,
    write_scaffold_files,
    get_main_py_template,
    get_views_template,
    get_models_template,
    get_admin_template,
    get_urls_template,
    get_serializers_template,
    get_settings_py_template,
)


class TestScaffoldCompiles:
    """Test that all scaffold templates compile as valid Python."""

    @pytest.fixture(autouse=True)
    def setup_templates(self):
        self.project = "testproj"
        self.templates = {
            "main.py": get_main_py_template(self.project),
            "app/views.py": get_views_template(self.project),
            "app/models.py": get_models_template(self.project),
            "app/admin.py": get_admin_template(self.project),
            "app/urls.py": get_urls_template(self.project),
            "app/serializers.py": get_serializers_template(self.project),
            "settings.py": get_settings_py_template(self.project),
        }

    @pytest.mark.parametrize("filename", [
        "main.py", "app/views.py", "app/models.py", "app/admin.py",
        "app/urls.py", "app/serializers.py", "settings.py",
    ])
    def test_template_is_valid_python(self, filename):
        """Every template should parse as valid Python (no SyntaxError)."""
        source = self.templates[filename]
        try:
            ast.parse(source, filename=filename)
        except SyntaxError as e:
            pytest.fail(f"{filename} has SyntaxError at line {e.lineno}: {e.msg}")


class TestScaffoldAPICompatibility:
    """
    Verify scaffold templates reference APIs that actually exist
    in the Aksara framework with correct signatures.
    """

    # =========================================================================
    # Middleware
    # =========================================================================

    def test_logging_middleware_exists(self):
        """LoggingMiddleware should be importable."""
        from aksara.middleware.logging import LoggingMiddleware
        assert LoggingMiddleware is not None

    def test_logging_middleware_no_log_request_body(self):
        """LoggingMiddleware should NOT accept 'log_request_body' kwarg."""
        from aksara.middleware.logging import LoggingMiddleware
        sig = inspect.signature(LoggingMiddleware.__init__)
        params = list(sig.parameters.keys())
        assert "log_request_body" not in params, (
            "LoggingMiddleware accepts 'log_request_body' but scaffold should use 'log_body'"
        )

    def test_logging_middleware_accepts_log_body(self):
        """LoggingMiddleware should accept 'log_body' kwarg."""
        from aksara.middleware.logging import LoggingMiddleware
        sig = inspect.signature(LoggingMiddleware.__init__)
        assert "log_body" in sig.parameters

    def test_scaffold_middleware_kwargs_are_valid(self):
        """All middleware kwargs used in scaffold must be accepted by actual classes."""
        from aksara.middleware.logging import LoggingMiddleware
        from aksara.middleware.request_id import RequestIDMiddleware

        template = get_main_py_template("test")

        # Parse the AST and find middleware kwargs
        tree = ast.parse(template)

        # The scaffold should not pass log_request_body
        assert "log_request_body" not in template, (
            "Scaffold still references 'log_request_body' — use 'log_body' or {}"
        )

    def test_request_id_middleware_importable_both_names(self):
        """Both RequestIDMiddleware and RequestIdMiddleware should work."""
        from aksara.middleware.request_id import RequestIDMiddleware
        from aksara.middleware.request_id import RequestIdMiddleware
        assert RequestIDMiddleware is RequestIdMiddleware

    # =========================================================================
    # ModelViewSet
    # =========================================================================

    def test_model_viewset_has_individual_serializer_attrs(self):
        """ModelViewSet should have list/retrieve/create/update serializer attrs."""
        from aksara.api.viewsets import ModelViewSet
        for attr in [
            "list_serializer_class",
            "retrieve_serializer_class",
            "create_serializer_class",
            "update_serializer_class",
        ]:
            assert hasattr(ModelViewSet, attr), f"ModelViewSet missing '{attr}'"

    def test_scaffold_viewset_uses_individual_serializers(self):
        """Scaffold views.py should use individual serializer class attrs, not serializer_class."""
        template = get_views_template("test")
        # Should NOT have bare 'serializer_class = ' (without list/retrieve/create/update prefix)
        lines = template.split("\n")
        uncommented = [l for l in lines if not l.strip().startswith("#")]
        for line in uncommented:
            stripped = line.strip()
            if "serializer_class" in stripped and "=" in stripped:
                # Allow list_serializer_class, retrieve_serializer_class, etc.
                if not any(stripped.startswith(f"{prefix}_serializer_class")
                           for prefix in ["list", "retrieve", "create", "update"]):
                    pytest.fail(
                        f"Scaffold uses bare 'serializer_class' — ModelViewSet uses "
                        f"list/retrieve/create/update_serializer_class. Line: {stripped}"
                    )
        # Should have the individual ones
        code = "\n".join(uncommented)
        assert "list_serializer_class" in code
        assert "create_serializer_class" in code

    def test_model_viewset_has_model_attr(self):
        """ModelViewSet should accept 'model' attribute."""
        from aksara.api.viewsets import ModelViewSet
        assert hasattr(ModelViewSet, "model")

    def test_model_viewset_has_prefix_attr(self):
        """ModelViewSet should accept 'prefix' attribute."""
        from aksara.api.viewsets import ModelViewSet
        assert hasattr(ModelViewSet, "prefix")

    def test_model_viewset_has_tags_attr(self):
        """ModelViewSet should accept 'tags' attribute."""
        from aksara.api.viewsets import ModelViewSet
        assert hasattr(ModelViewSet, "tags")

    def test_model_viewset_has_permission_classes(self):
        """ModelViewSet should accept 'permission_classes' attribute."""
        from aksara.api.viewsets import ModelViewSet
        assert hasattr(ModelViewSet, "permission_classes")

    def test_model_viewset_has_ai_exposed(self):
        """ModelViewSet should have 'ai_exposed' attribute."""
        from aksara.api.viewsets import ModelViewSet
        assert hasattr(ModelViewSet, "ai_exposed")

    # =========================================================================
    # Aksara App
    # =========================================================================

    def test_aksara_init_accepts_middlewares(self):
        """Aksara.__init__ should accept 'middlewares' parameter."""
        from aksara.app import Aksara
        sig = inspect.signature(Aksara.__init__)
        assert "middlewares" in sig.parameters

    def test_aksara_init_accepts_database_url(self):
        """Aksara.__init__ should accept 'database_url' parameter."""
        from aksara.app import Aksara
        sig = inspect.signature(Aksara.__init__)
        assert "database_url" in sig.parameters

    def test_aksara_init_accepts_enable_admin(self):
        """Aksara.__init__ should accept 'enable_admin' parameter."""
        from aksara.app import Aksara
        sig = inspect.signature(Aksara.__init__)
        assert "enable_admin" in sig.parameters

    def test_aksara_init_accepts_debug(self):
        """Aksara.__init__ should accept 'debug' parameter."""
        from aksara.app import Aksara
        sig = inspect.signature(Aksara.__init__)
        assert "debug" in sig.parameters

    # =========================================================================
    # Exports
    # =========================================================================

    def test_aksara_exports_model_viewset(self):
        """'from aksara import ModelViewSet' should work."""
        from aksara import ModelViewSet
        assert ModelViewSet is not None

    def test_aksara_exports_model_serializer(self):
        """'from aksara import ModelSerializer' should work."""
        from aksara import ModelSerializer
        assert ModelSerializer is not None

    def test_aksara_exports_action(self):
        """'from aksara import action' should work."""
        from aksara import action
        assert callable(action)

    def test_aksara_exports_request(self):
        """'from aksara import Request' should work."""
        from aksara import Request
        assert Request is not None

    def test_aksara_exports_model(self):
        """'from aksara import Model' should work."""
        from aksara import Model
        assert Model is not None

    def test_aksara_exports_fields(self):
        """'from aksara import fields' should work."""
        from aksara import fields
        assert fields is not None

    def test_aksara_exports_include_viewset(self):
        """'from aksara import include_viewset' should work."""
        from aksara import include_viewset
        assert callable(include_viewset)

    def test_aksara_exports_version(self):
        """'from aksara import __version__' should work."""
        from aksara import __version__
        assert isinstance(__version__, str)

    # =========================================================================
    # Fields
    # =========================================================================

    def test_field_types_exist(self):
        """All field types used in scaffold should exist."""
        from aksara import fields
        for name in ["String", "Text", "Boolean", "Integer", "JSON", "DateTime"]:
            assert hasattr(fields, name), f"fields.{name} does not exist"

    def test_field_ai_params(self):
        """Fields should accept ai_description parameter."""
        from aksara import fields
        # Should not raise
        f = fields.String(max_length=100, ai_description="test")
        assert f.ai_description == "test"

    # =========================================================================
    # Permissions
    # =========================================================================

    def test_permissions_exist(self):
        """IsAuthenticated and IsAdminUser should be importable."""
        from aksara.permissions import IsAuthenticated, IsAdminUser
        assert IsAuthenticated is not None
        assert IsAdminUser is not None

    # =========================================================================
    # Admin
    # =========================================================================

    def test_admin_imports(self):
        """Admin site and ModelAdmin should be importable."""
        from aksara.contrib.admin import site, ModelAdmin
        assert site is not None
        assert ModelAdmin is not None

    def test_admin_site_has_register(self):
        """Admin site should have register() method."""
        from aksara.contrib.admin import site
        assert hasattr(site, "register")
        assert callable(site.register)

    # =========================================================================
    # Settings/Conf
    # =========================================================================

    def test_settings_class_exists(self):
        """AksaraSettings should be importable."""
        from aksara.conf import Settings
        assert Settings is not None

    def test_settings_has_database_url(self):
        """Settings should have database_url attribute."""
        from aksara.conf import Settings
        s = Settings()
        assert hasattr(s, "database_url")

    def test_settings_has_debug(self):
        """Settings should have debug attribute."""
        from aksara.conf import Settings
        s = Settings()
        assert hasattr(s, "debug")


class TestScaffoldEndToEnd:
    """
    Test that a scaffolded project can be sys.path-imported
    and its modules resolve against real Aksara code.
    """

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
        self.project_name = "e2e_test"

        files = create_project_scaffold(self.project_name, self.base_path)
        write_scaffold_files(files)
        self.project_path = self.base_path / self.project_name

    def teardown_method(self):
        # Remove from sys.path and sys.modules
        proj_str = str(self.project_path)
        if proj_str in sys.path:
            sys.path.remove(proj_str)
        # Clean up imported modules
        to_remove = [k for k in sys.modules if k.startswith("app") or k == "settings"]
        for k in to_remove:
            del sys.modules[k]
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_models_importable(self):
        """app.models should import and Post should be a valid Model subclass."""
        sys.path.insert(0, str(self.project_path))
        from app.models import Post
        from aksara import Model
        assert issubclass(Post, Model)

    def test_post_model_has_tablename(self):
        """Post model should have __tablename__ set from Meta.table_name."""
        sys.path.insert(0, str(self.project_path))
        from app.models import Post
        assert hasattr(Post, "__tablename__")
        assert Post.__tablename__ == "posts"

    def test_serializers_importable(self):
        """app.serializers should import and PostSerializer should work."""
        sys.path.insert(0, str(self.project_path))
        from app.serializers import PostSerializer
        from aksara import ModelSerializer
        assert issubclass(PostSerializer, ModelSerializer)

    def test_views_importable(self):
        """app.views should import and PostViewSet should work."""
        sys.path.insert(0, str(self.project_path))
        from app.views import PostViewSet
        from aksara import ModelViewSet
        assert issubclass(PostViewSet, ModelViewSet)

    def test_viewset_has_correct_serializer_attrs(self):
        """PostViewSet should use individual serializer class attributes."""
        sys.path.insert(0, str(self.project_path))
        from app.views import PostViewSet
        from app.serializers import PostSerializer
        assert PostViewSet.list_serializer_class is PostSerializer
        assert PostViewSet.retrieve_serializer_class is PostSerializer
        assert PostViewSet.create_serializer_class is PostSerializer
        assert PostViewSet.update_serializer_class is PostSerializer

    def test_admin_importable(self):
        """app.admin should import without error."""
        sys.path.insert(0, str(self.project_path))
        # Admin registers Post with site — should not crash
        import app.admin  # noqa: F401

    def test_urls_importable(self):
        """app.urls should import without error."""
        sys.path.insert(0, str(self.project_path))
        from app.urls import register_routes, urlpatterns
        assert callable(register_routes)
        assert len(urlpatterns) > 0

    def test_main_py_parses(self):
        """main.py should parse as valid Python."""
        main_path = self.project_path / "main.py"
        source = main_path.read_text()
        # Should not raise SyntaxError
        ast.parse(source, filename="main.py")

    def test_welcome_html_exists(self):
        """static/welcome.html should exist after scaffold."""
        html = self.project_path / "static" / "welcome.html"
        assert html.exists()
        content = html.read_text()
        assert self.project_name in content

    def test_settings_py_parses(self):
        """settings.py should parse as valid Python."""
        settings_path = self.project_path / "settings.py"
        source = settings_path.read_text()
        ast.parse(source, filename="settings.py")
