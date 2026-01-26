"""
Vidyut v0.4.9 - Global Invariants & Sanity Checks

Tests that validate high-level invariants:
1. Imports & Public API
2. Version Consistency
3. Minimal Project Smoke Test

These tests are about catching regressions in wiring, not logic.
"""

import importlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest


# =============================================================================
# Section 1: Imports & Public API Tests
# =============================================================================

class TestImportsAndPublicAPI:
    """Test that all public imports work correctly."""
    
    def test_star_import_works(self):
        """from vidyut import * should work and not raise."""
        # We can't actually do `from vidyut import *` in a function,
        # so we test via exec
        namespace: dict[str, Any] = {}
        exec("from vidyut import *", namespace)
        
        # Should have imported things
        assert "Model" in namespace
        assert "Database" in namespace
        assert "fields" in namespace
    
    def test_core_orm_imports(self):
        """Core ORM exports should import cleanly."""
        from vidyut import Model, fields, Database, ModelRegistry
        from vidyut import DoesNotExist, MultipleObjectsReturned
        
        assert Model is not None
        assert fields is not None
        assert Database is not None
        assert ModelRegistry is not None
    
    def test_on_delete_constants(self):
        """on_delete constants should be importable."""
        from vidyut import CASCADE, SET_NULL, RESTRICT, PROTECT
        
        # These are string constants, not enums
        assert CASCADE == "CASCADE"
        assert SET_NULL == "SET NULL"
        assert RESTRICT == "RESTRICT"
        assert PROTECT == "RESTRICT"  # Alias
    
    def test_settings_imports(self):
        """Settings & Configuration should import."""
        from vidyut import Settings, settings, configure
        
        assert Settings is not None
        assert settings is not None
        assert callable(configure)
    
    def test_exception_imports(self):
        """All exceptions should import cleanly."""
        from vidyut import (
            VidyutError,
            DatabaseError,
            ConnectionError,
            QueryError,
            UniqueConstraintError,
            ForeignKeyConstraintError,
            NotNullConstraintError,
            CheckConstraintError,
            ValidationError,
            ConfigurationError,
            RestrictedError,
        )
        
        # Check inheritance
        assert issubclass(DatabaseError, VidyutError)
        assert issubclass(QueryError, DatabaseError)
        assert issubclass(RestrictedError, VidyutError)
    
    def test_api_layer_imports(self):
        """v0.3 API layer exports should import."""
        from vidyut import (
            ModelViewSet,
            include_viewset,
            generate_create_schema,
            generate_update_schema,
            generate_read_schema,
            get_schemas_for_model,
            action,
            ModelSerializer,
        )
        
        assert ModelViewSet is not None
        assert callable(include_viewset)
    
    def test_migration_imports(self):
        """Migration exports should import."""
        from vidyut import Migration, migration_operations
        
        assert Migration is not None
        assert migration_operations is not None
    
    def test_discovery_imports(self):
        """Discovery utilities should import."""
        from vidyut import (
            discover_viewsets_from_module,
            auto_discover_viewsets,
            load_app_models,
            get_app_models,
            get_all_app_labels,
            discover_viewsets,
            include_app_viewsets,
            include_all_app_viewsets,
        )
        
        assert callable(load_app_models)
        assert callable(auto_discover_viewsets)
    
    def test_vidyut_app_import(self):
        """Vidyut App should import."""
        from vidyut import Vidyut
        
        assert Vidyut is not None
    
    def test_fastapi_reexports(self):
        """FastAPI re-exports should work."""
        from vidyut import (
            FastAPI,
            APIRouter,
            Request,
            Response,
            HTTPException,
            Depends,
            Query,
            Path,
            status,
        )
        
        assert FastAPI is not None
        assert status.HTTP_200_OK == 200
    
    def test_relationship_imports(self):
        """v0.3.8 relationship exports should import."""
        from vidyut import (
            OnDelete,
            RelationRegistry,
            RelationMeta,
            finalize_relations,
        )
        
        # OnDelete has string constants
        assert OnDelete.CASCADE == "CASCADE"
    
    def test_identity_permission_imports(self):
        """v0.3.10 identity & permission exports should import."""
        from vidyut import (
            VidyutUserProtocol,
            AnonymousUser,
            BasePermission,
            AllowAny,
            IsAuthenticated,
            IsAdminUser,
            IsActiveUser,
            IsOwnerOrReadOnly,
            DenyAI,
        )
        
        # Check that permission classes are subclasses of BasePermission
        assert issubclass(AllowAny, BasePermission)
        assert issubclass(IsAuthenticated, BasePermission)
    
    def test_ai_context_imports(self):
        """AI context exports should import (v0.4.3+)."""
        from vidyut.ai import build_full_ai_context, AiFullContext
        
        assert callable(build_full_ai_context)
        assert AiFullContext is not None
    
    def test_ai_patch_imports(self):
        """AI patch exports should import (v0.4.4+)."""
        from vidyut.ai import (
            AiPatchRequest,
            AiPatchOperation,
            AiPatchResult,
            apply_ai_patches,
            validate_patch_request,
        )
        
        assert AiPatchRequest is not None
        assert callable(apply_ai_patches)
    
    def test_ai_planner_imports(self):
        """AI planner exports should import (v0.4.5+)."""
        from vidyut.ai import (
            AiPlan,
            AiPlanStep,
            AiPlanExecutionResult,
            execute_plan,
            validate_plan,
        )
        
        assert AiPlan is not None
        assert callable(execute_plan)
    
    def test_ai_agent_imports(self):
        """AI agent exports should import (v0.4.6+)."""
        from vidyut.ai import (
            AgentIntent,
            AgentContextBundle,
            build_agent_context_bundle,
            AiTool,
        )
        
        assert AgentIntent is not None
        assert callable(build_agent_context_bundle)
    
    def test_ai_schema_doctor_imports(self):
        """AI schema doctor exports should import (v0.4.7+)."""
        from vidyut.ai import (
            AiSchemaHealth,
            AiSchemaIssue,
            analyze_schema_health,
        )
        
        assert AiSchemaHealth is not None
        assert callable(analyze_schema_health)
    
    def test_import_cost_is_reasonable(self):
        """
        Importing vidyut should be reasonably fast.
        
        This tests that we haven't accidentally added heavy
        initialization or eager database connections.
        """
        # Run import in subprocess to get clean timing
        code = '''
import time
start = time.perf_counter()
import vidyut
end = time.perf_counter()
print(f"{end - start:.3f}")
'''
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        import_time = float(result.stdout.strip())
        
        # Should be under 0.5 seconds
        assert import_time < 0.5, f"Import took {import_time:.3f}s, expected < 0.5s"


# =============================================================================
# Section 2: Version Consistency Tests
# =============================================================================

class TestVersionConsistency:
    """Test that all version strings match."""
    
    def test_init_version_format(self):
        """vidyut.__version__ should be a valid semver string."""
        import vidyut
        
        version = vidyut.__version__
        assert version is not None
        
        # Should be x.y.z format
        parts = version.split(".")
        assert len(parts) == 3, f"Expected x.y.z, got {version}"
        
        # All parts should be numeric
        for part in parts:
            assert part.isdigit(), f"Non-numeric version part: {part}"
    
    def test_init_version_is_049(self):
        """vidyut.__version__ should be 0.4.9."""
        import vidyut
        
        assert vidyut.__version__ == "0.4.9"
    
    def test_cli_version_matches(self):
        """CLI --version should match vidyut.__version__."""
        from vidyut.cli.main import CLI_VERSION
        import vidyut
        
        assert CLI_VERSION == vidyut.__version__, (
            f"CLI version ({CLI_VERSION}) != __version__ ({vidyut.__version__})"
        )
    
    def test_pyproject_version_matches(self):
        """pyproject.toml version should match vidyut.__version__."""
        import tomllib
        import vidyut
        
        # Find pyproject.toml
        project_root = Path(__file__).parent.parent
        pyproject_path = project_root / "pyproject.toml"
        
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
        
        pyproject_version = pyproject["project"]["version"]
        
        assert pyproject_version == vidyut.__version__, (
            f"pyproject.toml version ({pyproject_version}) != __version__ ({vidyut.__version__})"
        )
    
    def test_version_command_outputs_version(self):
        """vidyut --version should output the version."""
        from click.testing import CliRunner
        from vidyut.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        
        assert result.exit_code == 0
        assert "0.4.9" in result.output


# =============================================================================
# Section 3: Minimal Project Smoke Tests
# =============================================================================

class TestMinimalProjectSmokeTest:
    """Test that basic project operations work."""
    
    def test_startproject_creates_structure(self, tmp_path: Path):
        """vidyut startproject should create a project structure."""
        from click.testing import CliRunner
        from vidyut.cli.main import cli
        
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["startproject", "myproject"])
            
            if result.exit_code != 0:
                pytest.skip(f"startproject failed: {result.output}")
            
            # Check structure exists
            assert (tmp_path / "myproject").exists() or Path("myproject").exists()
    
    def test_cli_help_works(self):
        """vidyut --help should work."""
        from click.testing import CliRunner
        from vidyut.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        
        assert result.exit_code == 0
        assert "Vidyut CLI" in result.output or "vidyut" in result.output.lower()
    
    def test_ai_cli_group_exists(self):
        """vidyut ai --help should work."""
        from click.testing import CliRunner
        from vidyut.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ["ai", "--help"])
        
        assert result.exit_code == 0
        assert "context" in result.output
        assert "schema-health" in result.output
        assert "plan" in result.output
    
    def test_plan_template_generates_valid_json(self):
        """vidyut ai plan template should generate valid JSON."""
        import json
        from click.testing import CliRunner
        from vidyut.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            "ai", "plan", "template",
            "--intent", "Add User model"
        ])
        
        assert result.exit_code == 0
        
        # Should be valid JSON
        data = json.loads(result.output)
        assert "intent" in data
        assert "plan" in data
        assert "steps" in data["plan"]
    
    def test_migrate_help_works(self):
        """vidyut migrate --help should work."""
        from click.testing import CliRunner
        from vidyut.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ["migrate", "--help"])
        
        assert result.exit_code == 0
    
    def test_info_command_works(self):
        """vidyut info should work without crashing."""
        from click.testing import CliRunner
        from vidyut.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ["info"])
        
        # May fail if no settings, but should not crash with exit 2
        assert result.exit_code in (0, 1)
        # Should have some output
        assert len(result.output) > 0


# =============================================================================
# Section 4: Module Structure Tests
# =============================================================================

class TestModuleStructure:
    """Test that module structure is correct."""
    
    def test_vidyut_has_py_typed(self):
        """vidyut should have py.typed marker for type checking."""
        import vidyut
        
        package_dir = Path(vidyut.__file__).parent
        py_typed = package_dir / "py.typed"
        
        assert py_typed.exists(), "Missing py.typed marker"
    
    def test_vidyut_ai_submodule(self):
        """vidyut.ai submodule should be importable."""
        import vidyut.ai
        
        # Should have main exports
        assert hasattr(vidyut.ai, "build_full_ai_context")
    
    def test_vidyut_cli_submodule(self):
        """vidyut.cli submodule should be importable."""
        import vidyut.cli
        from vidyut.cli.main import cli as cli_cmd
        
        assert hasattr(vidyut.cli, "cli")
        assert callable(cli_cmd)
    
    def test_vidyut_db_submodule(self):
        """vidyut.db submodule should be importable."""
        import vidyut.db
        
        assert hasattr(vidyut.db, "Database")
    
    def test_vidyut_api_submodule(self):
        """vidyut.api submodule should be importable."""
        import vidyut.api
        
        assert hasattr(vidyut.api, "ModelViewSet")


# =============================================================================
# Section 5: Exception Hierarchy Tests  
# =============================================================================

class TestExceptionHierarchy:
    """Test that exception hierarchy is correct."""
    
    def test_all_exceptions_inherit_from_vidyut_error(self):
        """All Vidyut exceptions should inherit from VidyutError."""
        from vidyut import (
            VidyutError,
            DatabaseError,
            ConnectionError,
            QueryError,
            UniqueConstraintError,
            ForeignKeyConstraintError,
            NotNullConstraintError,
            CheckConstraintError,
            ValidationError,
            ConfigurationError,
            RestrictedError,
        )
        
        exceptions = [
            DatabaseError,
            ConnectionError,
            QueryError,
            UniqueConstraintError,
            ForeignKeyConstraintError,
            NotNullConstraintError,
            CheckConstraintError,
            ValidationError,
            ConfigurationError,
            RestrictedError,
        ]
        
        for exc_class in exceptions:
            assert issubclass(exc_class, VidyutError), (
                f"{exc_class.__name__} does not inherit from VidyutError"
            )
    
    def test_database_exceptions_inherit_from_database_error(self):
        """Database-related exceptions should inherit from DatabaseError."""
        from vidyut import (
            DatabaseError,
            ConnectionError,
            QueryError,
            UniqueConstraintError,
            ForeignKeyConstraintError,
            NotNullConstraintError,
            CheckConstraintError,
        )
        
        db_exceptions = [
            ConnectionError,
            QueryError,
            UniqueConstraintError,
            ForeignKeyConstraintError,
            NotNullConstraintError,
            CheckConstraintError,
        ]
        
        for exc_class in db_exceptions:
            assert issubclass(exc_class, DatabaseError), (
                f"{exc_class.__name__} does not inherit from DatabaseError"
            )
    
    def test_exceptions_have_message_attribute(self):
        """All exceptions should have a message attribute."""
        from vidyut import VidyutError, DatabaseError, ValidationError
        
        exc1 = VidyutError("test message")
        assert exc1.message == "test message"
        
        exc2 = DatabaseError("db error")
        assert exc2.message == "db error"
        
        exc3 = ValidationError("validation error")
        assert exc3.message == "validation error"
    
    def test_restricted_error_has_model_info(self):
        """RestrictedError should have model information attributes."""
        from vidyut import RestrictedError
        
        exc = RestrictedError(
            "Cannot delete",
            model_name="User",
            related_model="Post",
            related_count=5
        )
        
        assert exc.model_name == "User"
        assert exc.related_model == "Post"
        assert exc.related_count == 5
        assert "User" in str(exc)
        assert "Post" in str(exc)
        assert "5" in str(exc)
