"""
Tests for AI CodeGen (v0.4.2).

Tests:
- AiFieldSpec model validation
- AiModelSpec model validation
- AiCodegenRequest model validation
- generate_model_code for various field types
- generate_viewset_code output
- generate_serializer_code output
- generate_admin_code output
- generate_app_skeleton structure
- generate_migration_stub structure
- generate_code dispatcher
- Endpoint integration tests
"""

import pytest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
from fastapi.testclient import TestClient
from fastapi import FastAPI

from aksara.ai.codegen import (
    AiFieldSpec,
    AiModelSpec,
    AiCodegenRequest,
    AiCodegenResult,
    AiCodegenTarget,
    FIELD_TYPE_MAPPING,
    generate_model_code,
    generate_viewset_code,
    generate_serializer_code,
    generate_admin_code,
    generate_app_skeleton,
    generate_migration_stub,
    generate_code,
    get_codegen_schemas,
)
from aksara.ai.fastapi import router


# =============================================================================
# Model Validation Tests
# =============================================================================

class TestAiFieldSpec:
    """Tests for AiFieldSpec model."""
    
    def test_string_field(self):
        """Test string field specification."""
        field = AiFieldSpec(
            name="title",
            type="string",
            max_length=200
        )
        assert field.name == "title"
        assert field.type == "string"
        assert field.max_length == 200
    
    def test_integer_field(self):
        """Test integer field specification."""
        field = AiFieldSpec(
            name="count",
            type="integer",
            default=0
        )
        assert field.type == "integer"
        assert field.default == 0
    
    def test_boolean_field(self):
        """Test boolean field specification."""
        field = AiFieldSpec(
            name="is_active",
            type="boolean",
            default=True
        )
        assert field.type == "boolean"
        assert field.default is True
    
    def test_datetime_field(self):
        """Test datetime field specification."""
        field = AiFieldSpec(
            name="created_at",
            type="datetime",
        )
        assert field.type == "datetime"
    
    def test_uuid_field(self):
        """Test UUID field specification."""
        field = AiFieldSpec(
            name="uuid",
            type="uuid",
        )
        assert field.type == "uuid"
    
    def test_decimal_field(self):
        """Test decimal field specification."""
        field = AiFieldSpec(
            name="price",
            type="decimal",
        )
        assert field.type == "decimal"
    
    def test_email_field(self):
        """Test email field specification."""
        field = AiFieldSpec(
            name="email",
            type="email",
            unique=True
        )
        assert field.type == "email"
        assert field.unique is True
    
    def test_url_field(self):
        """Test URL field specification."""
        field = AiFieldSpec(
            name="website",
            type="url",
            required=False
        )
        assert field.type == "url"
        assert field.required is False
    
    def test_json_field(self):
        """Test JSON field specification."""
        field = AiFieldSpec(
            name="metadata",
            type="json",
            default={}
        )
        assert field.type == "json"
    
    def test_text_field(self):
        """Test text field specification."""
        field = AiFieldSpec(
            name="description",
            type="text"
        )
        assert field.type == "text"
    
    def test_fk_field(self):
        """Test foreign key field specification."""
        field = AiFieldSpec(
            name="author",
            type="fk",
            fk_model="User",
        )
        assert field.type == "fk"
        assert field.fk_model == "User"
    
    def test_m2m_field(self):
        """Test many-to-many field specification."""
        field = AiFieldSpec(
            name="tags",
            type="m2m",
            fk_model="Tag"
        )
        assert field.type == "m2m"
        assert field.fk_model == "Tag"
    
    def test_field_with_help_text(self):
        """Test field with help text."""
        field = AiFieldSpec(
            name="slug",
            type="string",
            max_length=100,
            help_text="URL-friendly identifier"
        )
        assert field.help_text == "URL-friendly identifier"


class TestAiModelSpec:
    """Tests for AiModelSpec model."""
    
    def test_minimal_spec(self):
        """Test minimal model specification."""
        spec = AiModelSpec(
            app_label="blog",
            name="Article",
            fields=[
                AiFieldSpec(name="title", type="string", max_length=200)
            ]
        )
        assert spec.app_label == "blog"
        assert spec.name == "Article"
        assert len(spec.fields) == 1
    
    def test_spec_with_all_options(self):
        """Test model specification with all options."""
        spec = AiModelSpec(
            app_label="blog",
            name="Article",
            fields=[
                AiFieldSpec(name="title", type="string", max_length=200),
                AiFieldSpec(name="body", type="text"),
            ],
            add_viewset=True,
            add_serializer=True,
            add_admin=True,
            ai_exposed=True,
        )
        assert spec.add_viewset is True
        assert spec.add_serializer is True
        assert spec.add_admin is True
        assert spec.ai_exposed is True
    
    def test_spec_with_multiple_fields(self):
        """Test model specification with multiple field types."""
        spec = AiModelSpec(
            app_label="store",
            name="Product",
            fields=[
                AiFieldSpec(name="id", type="uuid"),
                AiFieldSpec(name="name", type="string", max_length=100),
                AiFieldSpec(name="price", type="decimal"),
                AiFieldSpec(name="in_stock", type="boolean", default=True),
                AiFieldSpec(name="category", type="fk", fk_model="Category"),
                AiFieldSpec(name="tags", type="m2m", fk_model="Tag"),
            ]
        )
        assert len(spec.fields) == 6


class TestAiCodegenRequest:
    """Tests for AiCodegenRequest model."""
    
    def test_model_target(self):
        """Test codegen request for model target."""
        request = AiCodegenRequest(
            target=AiCodegenTarget.MODEL,
            model_spec=AiModelSpec(
                app_label="blog",
                name="Post",
                fields=[AiFieldSpec(name="title", type="string", max_length=200)]
            )
        )
        assert request.target == AiCodegenTarget.MODEL
    
    def test_viewset_target(self):
        """Test codegen request for viewset target."""
        request = AiCodegenRequest(
            target=AiCodegenTarget.VIEWSET,
            model_spec=AiModelSpec(
                app_label="blog",
                name="Post",
                fields=[AiFieldSpec(name="title", type="string", max_length=200)]
            )
        )
        assert request.target == AiCodegenTarget.VIEWSET
    
    def test_app_target(self):
        """Test codegen request for app skeleton."""
        request = AiCodegenRequest(
            target=AiCodegenTarget.APP,
            app_name="blog",
        )
        assert request.target == AiCodegenTarget.APP
    
    def test_migration_target(self):
        """Test codegen request for migration stub."""
        request = AiCodegenRequest(
            target=AiCodegenTarget.MIGRATION,
            model_spec=AiModelSpec(
                app_label="blog",
                name="Post",
                fields=[AiFieldSpec(name="title", type="string", max_length=200)]
            )
        )
        assert request.target == AiCodegenTarget.MIGRATION


class TestAiCodegenResult:
    """Tests for AiCodegenResult model."""
    
    def test_result_structure(self):
        """Test result structure."""
        result = AiCodegenResult(
            files={"blog/models.py": "class Post(Model): pass"},
            notes=["Add 'blog' to INSTALLED_APPS"]
        )
        assert "blog/models.py" in result.files
        assert len(result.notes) == 1


# =============================================================================
# Field Type Mapping Tests
# =============================================================================

class TestFieldTypeMapping:
    """Tests for field type mapping."""
    
    def test_all_types_mapped(self):
        """Test all expected field types are mapped."""
        expected_types = {
            "string", "text", "integer", "boolean", "datetime",
            "uuid", "decimal", "email", "url", "json", "fk", "m2m"
        }
        assert set(FIELD_TYPE_MAPPING.keys()) == expected_types
    
    def test_string_maps_to_fields_string(self):
        """Test string maps to fields.String."""
        assert FIELD_TYPE_MAPPING["string"] == "fields.String"
    
    def test_text_maps_to_fields_text(self):
        """Test text maps to fields.Text."""
        assert FIELD_TYPE_MAPPING["text"] == "fields.Text"
    
    def test_fk_maps_to_fields_foreignkey(self):
        """Test fk maps to fields.ForeignKey."""
        assert FIELD_TYPE_MAPPING["fk"] == "fields.ForeignKey"
    
    def test_m2m_maps_to_fields_manytomany(self):
        """Test m2m maps to fields.ManyToMany."""
        assert FIELD_TYPE_MAPPING["m2m"] == "fields.ManyToMany"


# =============================================================================
# Code Generation Tests
# =============================================================================

class TestGenerateModelCode:
    """Tests for generate_model_code function."""
    
    def test_basic_model(self):
        """Test basic model code generation."""
        spec = AiModelSpec(
            app_label="blog",
            name="Article",
            fields=[
                AiFieldSpec(name="title", type="string", max_length=200),
            ]
        )
        files = generate_model_code(spec)
        
        assert "blog/models.py" in files
        code = files["blog/models.py"]
        assert "class Article(Model):" in code
        assert "title" in code
        assert "fields.String" in code
        assert "max_length=200" in code
    
    def test_model_with_imports(self):
        """Test model includes proper imports."""
        spec = AiModelSpec(
            app_label="blog",
            name="Article",
            fields=[
                AiFieldSpec(name="title", type="string", max_length=200),
            ]
        )
        files = generate_model_code(spec)
        code = files["blog/models.py"]
        
        assert "from aksara import Model, fields" in code
    
    def test_model_with_fk(self):
        """Test model with ForeignKey."""
        spec = AiModelSpec(
            app_label="blog",
            name="Article",
            fields=[
                AiFieldSpec(name="author", type="fk", fk_model="User"),
            ]
        )
        files = generate_model_code(spec)
        code = files["blog/models.py"]
        
        assert "fields.ForeignKey" in code
        assert "User" in code
    
    def test_model_with_m2m(self):
        """Test model with ManyToMany."""
        spec = AiModelSpec(
            app_label="blog",
            name="Article",
            fields=[
                AiFieldSpec(name="tags", type="m2m", fk_model="Tag"),
            ]
        )
        files = generate_model_code(spec)
        code = files["blog/models.py"]
        
        assert "fields.ManyToMany" in code or "tags" in code


class TestGenerateViewsetCode:
    """Tests for generate_viewset_code function."""
    
    def test_basic_viewset(self):
        """Test basic viewset code generation."""
        spec = AiModelSpec(
            app_label="blog",
            name="Article",
            fields=[
                AiFieldSpec(name="title", type="string", max_length=200),
            ]
        )
        files = generate_viewset_code(spec)
        
        assert "blog/views.py" in files
        code = files["blog/views.py"]
        assert "ViewSet" in code
        assert "Article" in code
    
    def test_viewset_imports(self):
        """Test viewset has correct imports."""
        spec = AiModelSpec(
            app_label="blog",
            name="Article",
            fields=[
                AiFieldSpec(name="title", type="string", max_length=200),
            ],
        )
        files = generate_viewset_code(spec)
        code = files["blog/views.py"]
        
        assert "from aksara.api import ModelViewSet" in code


class TestGenerateSerializerCode:
    """Tests for generate_serializer_code function."""
    
    def test_basic_serializer(self):
        """Test basic serializer code generation."""
        spec = AiModelSpec(
            app_label="blog",
            name="Article",
            fields=[
                AiFieldSpec(name="title", type="string", max_length=200),
                AiFieldSpec(name="body", type="text"),
            ]
        )
        files = generate_serializer_code(spec)
        
        assert "blog/serializers.py" in files
        code = files["blog/serializers.py"]
        assert "Serializer" in code
        assert "Article" in code
    
    def test_serializer_with_fields(self):
        """Test serializer includes fields."""
        spec = AiModelSpec(
            app_label="blog",
            name="Article",
            fields=[
                AiFieldSpec(name="title", type="string", max_length=200),
                AiFieldSpec(name="body", type="text"),
            ]
        )
        files = generate_serializer_code(spec)
        code = files["blog/serializers.py"]
        
        assert "title" in code
        assert "fields" in code


class TestGenerateAdminCode:
    """Tests for generate_admin_code function."""
    
    def test_basic_admin(self):
        """Test basic admin code generation."""
        spec = AiModelSpec(
            app_label="blog",
            name="Article",
            fields=[
                AiFieldSpec(name="title", type="string", max_length=200),
            ]
        )
        files = generate_admin_code(spec)
        
        assert "blog/admin.py" in files
        code = files["blog/admin.py"]
        assert "Article" in code
        assert "Admin" in code


class TestGenerateAppSkeleton:
    """Tests for generate_app_skeleton function."""
    
    def test_app_skeleton_structure(self):
        """Test app skeleton includes all necessary files."""
        files = generate_app_skeleton("blog")
        
        # Should include models.py at minimum
        assert any("models" in f for f in files.keys())
        assert any("__init__" in f for f in files.keys())
    
    def test_app_skeleton_has_views(self):
        """Test app skeleton includes views."""
        files = generate_app_skeleton("blog")
        
        assert any("views" in f for f in files.keys())
    
    def test_app_skeleton_has_serializers(self):
        """Test app skeleton includes serializers."""
        files = generate_app_skeleton("blog")
        
        assert any("serializers" in f for f in files.keys())
    
    def test_app_skeleton_has_admin(self):
        """Test app skeleton includes admin."""
        files = generate_app_skeleton("blog")
        
        assert any("admin" in f for f in files.keys())


class TestGenerateMigrationStub:
    """Tests for generate_migration_stub function."""
    
    def test_migration_stub(self):
        """Test migration stub generation."""
        spec = AiModelSpec(
            app_label="blog",
            name="Article",
            fields=[
                AiFieldSpec(name="title", type="string", max_length=200),
            ]
        )
        files = generate_migration_stub(spec)
        
        # Should have a migration file
        assert len(files) == 1
        file_path = list(files.keys())[0]
        assert "migrations" in file_path
        
        code = list(files.values())[0]
        assert "Article" in code or "article" in code.lower()


class TestGenerateCode:
    """Tests for generate_code dispatcher function."""
    
    def test_dispatch_to_model(self):
        """Test dispatch to model generation."""
        request = AiCodegenRequest(
            target=AiCodegenTarget.MODEL,
            model_spec=AiModelSpec(
                app_label="blog",
                name="Article",
                fields=[AiFieldSpec(name="title", type="string", max_length=200)]
            )
        )
        result = generate_code(request)
        
        assert isinstance(result, AiCodegenResult)
        assert len(result.files) >= 1
    
    def test_dispatch_to_viewset(self):
        """Test dispatch to viewset generation."""
        request = AiCodegenRequest(
            target=AiCodegenTarget.VIEWSET,
            model_spec=AiModelSpec(
                app_label="blog",
                name="Article",
                fields=[AiFieldSpec(name="title", type="string", max_length=200)]
            )
        )
        result = generate_code(request)
        
        assert isinstance(result, AiCodegenResult)
    
    def test_dispatch_to_serializer(self):
        """Test dispatch to serializer generation."""
        request = AiCodegenRequest(
            target=AiCodegenTarget.SERIALIZER,
            model_spec=AiModelSpec(
                app_label="blog",
                name="Article",
                fields=[AiFieldSpec(name="title", type="string", max_length=200)]
            )
        )
        result = generate_code(request)
        
        assert isinstance(result, AiCodegenResult)
    
    def test_dispatch_to_app(self):
        """Test dispatch to app skeleton generation."""
        request = AiCodegenRequest(
            target=AiCodegenTarget.APP,
            app_name="blog",
        )
        result = generate_code(request)
        
        assert isinstance(result, AiCodegenResult)
        # App skeleton generates multiple files
        assert len(result.files) >= 1
    
    def test_dispatch_to_migration(self):
        """Test dispatch to migration stub generation."""
        request = AiCodegenRequest(
            target=AiCodegenTarget.MIGRATION,
            model_spec=AiModelSpec(
                app_label="blog",
                name="Article",
                fields=[AiFieldSpec(name="title", type="string", max_length=200)]
            )
        )
        result = generate_code(request)
        
        assert isinstance(result, AiCodegenResult)
    
    def test_model_with_viewset_and_serializer(self):
        """Test model generation with viewset and serializer enabled."""
        request = AiCodegenRequest(
            target=AiCodegenTarget.MODEL,
            model_spec=AiModelSpec(
                app_label="blog",
                name="Article",
                fields=[AiFieldSpec(name="title", type="string", max_length=200)],
                add_viewset=True,
                add_serializer=True,
                add_admin=True,
            )
        )
        result = generate_code(request)
        
        # Should have multiple files: models.py, views.py, serializers.py, admin.py
        assert len(result.files) >= 4


# =============================================================================
# Schema Helper Tests
# =============================================================================

class TestGetCodegenSchemas:
    """Tests for get_codegen_schemas function."""
    
    def test_returns_schemas_dict(self):
        """Test returns dictionary of schemas."""
        schemas = get_codegen_schemas()
        
        assert isinstance(schemas, dict)
        assert "AiFieldSpec" in schemas
        assert "AiModelSpec" in schemas
        assert "AiCodegenRequest" in schemas
    
    def test_schemas_are_json_schema(self):
        """Test schemas are valid JSON schemas."""
        schemas = get_codegen_schemas()
        
        for name, schema in schemas.items():
            assert "type" in schema or "properties" in schema or "$defs" in schema


# =============================================================================
# Endpoint Integration Tests
# =============================================================================

def create_test_app() -> FastAPI:
    """Create a test FastAPI app with AI router."""
    app = FastAPI()
    app.include_router(router)
    return app


class TestCodegenSchemaEndpoint:
    """Tests for POST /ai/codegen/schema endpoint."""
    
    def test_get_schema(self):
        """Test schema endpoint returns valid structure."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.post("/ai/codegen/schema")
        assert response.status_code == 200
        
        data = response.json()
        assert "schemas" in data
        assert "supported_targets" in data
        assert "supported_field_types" in data
        assert "version" in data
        assert data["version"] == "0.4.2"
    
    def test_schema_includes_field_types(self):
        """Test schema includes all field types."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.post("/ai/codegen/schema")
        data = response.json()
        
        field_types = data["supported_field_types"]
        assert "string" in field_types
        assert "integer" in field_types
        assert "fk" in field_types
        assert "m2m" in field_types


class TestCodegenPreviewEndpoint:
    """Tests for POST /ai/codegen/preview endpoint."""
    
    def test_invalid_request_returns_400(self):
        """Test invalid request returns 400."""
        app = create_test_app()
        client = TestClient(app)
        
        # Empty body
        response = client.post("/ai/codegen/preview", json={})
        assert response.status_code == 400
    
    def test_missing_target_returns_400(self):
        """Test missing target returns 400."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.post("/ai/codegen/preview", json={
            "model_spec": {
                "app_label": "blog",
                "name": "Article",
                "fields": [{"name": "title", "type": "string"}]
            }
        })
        assert response.status_code == 400
    
    def test_valid_model_request(self):
        """Test valid model generation request."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.post("/ai/codegen/preview", json={
            "target": "model",
            "model_spec": {
                "app_label": "blog",
                "name": "Article",
                "fields": [
                    {"name": "title", "type": "string", "max_length": 200},
                    {"name": "body", "type": "text"}
                ]
            }
        })
        assert response.status_code == 200
        
        data = response.json()
        assert "files" in data
        assert "notes" in data
    
    def test_valid_app_skeleton_request(self):
        """Test valid app skeleton generation request."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.post("/ai/codegen/preview", json={
            "target": "app",
            "app_name": "blog",
        })
        assert response.status_code == 200
        
        data = response.json()
        assert "files" in data


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_fields_raises_validation_error(self):
        """Test model spec with empty fields raises error."""
        # Empty fields should still be allowed by model but generate empty model
        spec = AiModelSpec(
            app_label="blog",
            name="Article",
            fields=[]
        )
        files = generate_model_code(spec)
        assert "blog/models.py" in files
    
    def test_reserved_field_names(self):
        """Test fields with reserved names work."""
        spec = AiModelSpec(
            app_label="test",
            name="Test",
            fields=[
                AiFieldSpec(name="id", type="uuid"),
            ]
        )
        files = generate_model_code(spec)
        code = files["test/models.py"]
        assert "id" in code
    
    def test_field_with_all_options(self):
        """Test field with all possible options."""
        field = AiFieldSpec(
            name="description",
            type="string",
            max_length=500,
            required=False,
            unique=False,
            default="",
            help_text="A description field",
        )
        spec = AiModelSpec(
            app_label="test",
            name="Test",
            fields=[field]
        )
        files = generate_model_code(spec)
        code = files["test/models.py"]
        assert "description" in code
    
    def test_long_model_name(self):
        """Test handling of long model names."""
        spec = AiModelSpec(
            app_label="myapp",
            name="VeryLongModelNameThatMightCauseIssues",
            fields=[
                AiFieldSpec(name="field", type="string", max_length=100),
            ]
        )
        files = generate_model_code(spec)
        code = files["myapp/models.py"]
        assert "VeryLongModelNameThatMightCauseIssues" in code
    
    def test_special_characters_in_app_label(self):
        """Test app label with underscores."""
        files = generate_app_skeleton("my_app_module")
        assert any("my_app_module" in f for f in files.keys())
