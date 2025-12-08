"""
Tests for Vidyut v0.2 Features

Tests for:
- Settings/Configuration
- Exceptions
- Query Lookups
- ForeignKey fields
- AI Metadata
- Registry Helpers
"""

from __future__ import annotations

import os
import pytest
from datetime import datetime
from unittest.mock import patch

from vidyut import Model, fields
from vidyut.conf import Settings, configure, settings, reset_settings
from vidyut.exceptions import (
    VidyutError,
    DatabaseError,
    ConnectionError,
    QueryError,
    UniqueConstraintError,
    ForeignKeyConstraintError,
    NotNullConstraintError,
    CheckConstraintError,
    map_database_error,
)
from vidyut.registry import (
    ModelRegistry,
    get_models,
    get_model_meta,
    get_model_fields,
    get_model_schema_for_ai,
    get_all_schemas_for_ai,
)
from vidyut.manager import Manager


# =============================================================================
# Test Settings
# =============================================================================

class TestSettings:
    """Tests for the Settings system."""
    
    def test_default_settings(self):
        """Test default settings values."""
        s = Settings(_configured=True)  # Skip env loading
        assert s.database_url is None
        assert s.debug is False
        assert s.pool_max_size == 20
        assert s.pool_min_size == 5
        assert s.migrations_dir == "migrations"
        assert s.ai_enabled is False
        assert s.mcp_enabled is False
    
    def test_settings_with_values(self):
        """Test settings with custom values."""
        s = Settings(
            database_url="postgresql://localhost/test",
            debug=True,
            pool_max_size=30,
            pool_min_size=10,
            migrations_dir="db/migrations",
            ai_enabled=True,
            mcp_enabled=True,
            _configured=True,
        )
        assert s.database_url == "postgresql://localhost/test"
        assert s.debug is True
        assert s.pool_max_size == 30
        assert s.pool_min_size == 10
        assert s.migrations_dir == "db/migrations"
        assert s.ai_enabled is True
        assert s.mcp_enabled is True
    
    def test_settings_uppercase_aliases(self):
        """Test uppercase property aliases."""
        s = Settings(
            database_url="postgresql://localhost/test",
            debug=True,
            pool_max_size=25,
            _configured=True,
        )
        assert s.DATABASE_URL == "postgresql://localhost/test"
        assert s.DEBUG is True
        assert s.POOL_SIZE == 25
    
    def test_settings_from_env(self):
        """Test loading settings from environment variables."""
        with patch.dict(os.environ, {
            "VIDYUT_DATABASE_URL": "postgresql://env/db",
            "VIDYUT_DEBUG": "true",
            "VIDYUT_POOL_SIZE": "25",
        }, clear=False):
            s = Settings()  # Will load from env
            assert s.database_url == "postgresql://env/db"
            assert s.debug is True
            assert s.pool_max_size == 25
    
    def test_configure_function(self):
        """Test the configure() function returns configured settings."""
        # Configure with explicit values
        new_settings = configure(debug=True, database_url="postgresql://test/db")
        
        # Check the returned settings object was configured
        assert new_settings.debug is True
        assert new_settings.database_url == "postgresql://test/db"
        
        # Reset for other tests
        reset_settings()


# =============================================================================
# Test Exceptions
# =============================================================================

class TestExceptions:
    """Tests for the exception hierarchy."""
    
    def test_vidyut_error_is_base(self):
        """Test VidyutError is the base exception."""
        assert issubclass(DatabaseError, VidyutError)
        assert issubclass(ConnectionError, VidyutError)
        assert issubclass(QueryError, VidyutError)
    
    def test_constraint_errors(self):
        """Test constraint error hierarchy."""
        assert issubclass(UniqueConstraintError, DatabaseError)
        assert issubclass(ForeignKeyConstraintError, DatabaseError)
        assert issubclass(NotNullConstraintError, DatabaseError)
        assert issubclass(CheckConstraintError, DatabaseError)
    
    def test_exception_messages(self):
        """Test exception can carry messages."""
        err = UniqueConstraintError("Duplicate email")
        assert "Duplicate email" in str(err)
        
        err = ForeignKeyConstraintError("Invalid user_id reference")
        assert "Invalid user_id reference" in str(err)
    
    def test_map_database_error_unique(self):
        """Test mapping unique constraint errors."""
        import asyncpg
        
        # Use actual asyncpg exception type
        exc = asyncpg.UniqueViolationError("Key (email)=(test@test.com) already exists")
        mapped = map_database_error(exc)
        assert isinstance(mapped, UniqueConstraintError)
    
    def test_map_database_error_foreign_key(self):
        """Test mapping foreign key constraint errors."""
        import asyncpg
        
        exc = asyncpg.ForeignKeyViolationError('Key (user_id)=(999) is not present in table "users"')
        mapped = map_database_error(exc)
        assert isinstance(mapped, ForeignKeyConstraintError)
    
    def test_map_database_error_not_null(self):
        """Test mapping not null constraint errors."""
        import asyncpg
        
        exc = asyncpg.NotNullViolationError('null value in column "name"')
        mapped = map_database_error(exc)
        assert isinstance(mapped, NotNullConstraintError)
    
    def test_map_database_error_connection(self):
        """Test mapping connection errors."""
        import asyncpg
        
        exc = asyncpg.PostgresConnectionError("Connection refused")
        mapped = map_database_error(exc)
        assert isinstance(mapped, ConnectionError)
    
    def test_map_database_error_unknown(self):
        """Test mapping unknown errors."""
        exc = Exception("Some unknown error")
        mapped = map_database_error(exc)
        assert isinstance(mapped, DatabaseError)


# =============================================================================
# Test Query Lookups
# =============================================================================

class TestQueryLookups:
    """Tests for query lookup operators."""
    
    @pytest.fixture
    def queryset(self):
        """Create a QuerySet for testing."""
        from vidyut.manager import QuerySet, parse_lookup
        
        # Clear registry before re-registering
        ModelRegistry.clear()
        
        # Create a simple test model
        class TestModel(Model):
            id = fields.UUID(primary_key=True)
            name = fields.String(max_length=100)
            age = fields.Integer()
            active = fields.Boolean(default=True)
            
            class Meta:
                table_name = "test_lookup"
        
        return QuerySet(TestModel)
    
    def test_parse_lookup_simple(self, queryset):
        """Test parsing simple field name."""
        from vidyut.manager import parse_lookup
        field, lookup = parse_lookup("name")
        assert field == "name"
        assert lookup == "exact"
    
    def test_parse_lookup_gt(self, queryset):
        """Test parsing __gt lookup."""
        from vidyut.manager import parse_lookup
        field, lookup = parse_lookup("age__gt")
        assert field == "age"
        assert lookup == "gt"
    
    def test_parse_lookup_gte(self, queryset):
        """Test parsing __gte lookup."""
        from vidyut.manager import parse_lookup
        field, lookup = parse_lookup("age__gte")
        assert field == "age"
        assert lookup == "gte"
    
    def test_parse_lookup_lt(self, queryset):
        """Test parsing __lt lookup."""
        from vidyut.manager import parse_lookup
        field, lookup = parse_lookup("age__lt")
        assert field == "age"
        assert lookup == "lt"
    
    def test_parse_lookup_lte(self, queryset):
        """Test parsing __lte lookup."""
        from vidyut.manager import parse_lookup
        field, lookup = parse_lookup("age__lte")
        assert field == "age"
        assert lookup == "lte"
    
    def test_parse_lookup_in(self, queryset):
        """Test parsing __in lookup."""
        from vidyut.manager import parse_lookup
        field, lookup = parse_lookup("age__in")
        assert field == "age"
        assert lookup == "in"
    
    def test_parse_lookup_isnull(self, queryset):
        """Test parsing __isnull lookup."""
        from vidyut.manager import parse_lookup
        field, lookup = parse_lookup("name__isnull")
        assert field == "name"
        assert lookup == "isnull"
    
    def test_parse_lookup_icontains(self, queryset):
        """Test parsing __icontains lookup."""
        from vidyut.manager import parse_lookup
        field, lookup = parse_lookup("name__icontains")
        assert field == "name"
        assert lookup == "icontains"
    
    def test_build_where_clause_gt(self, queryset):
        """Test building WHERE clause with __gt."""
        qs = queryset.filter(age__gt=18)
        clause, params = qs._build_where_clause()
        assert "age > $1" in clause
        assert params == [18]
    
    def test_build_where_clause_in(self, queryset):
        """Test building WHERE clause with __in."""
        qs = queryset.filter(age__in=[18, 21, 25])
        clause, params = qs._build_where_clause()
        assert "age IN ($1, $2, $3)" in clause
        assert params == [18, 21, 25]
    
    def test_build_where_clause_isnull_true(self, queryset):
        """Test building WHERE clause with __isnull=True."""
        qs = queryset.filter(name__isnull=True)
        clause, params = qs._build_where_clause()
        assert "name IS NULL" in clause
        assert params == []
    
    def test_build_where_clause_isnull_false(self, queryset):
        """Test building WHERE clause with __isnull=False."""
        qs = queryset.filter(name__isnull=False)
        clause, params = qs._build_where_clause()
        assert "name IS NOT NULL" in clause
        assert params == []
    
    def test_build_where_clause_icontains(self, queryset):
        """Test building WHERE clause with __icontains."""
        qs = queryset.filter(name__icontains="john")
        clause, params = qs._build_where_clause()
        assert "name ILIKE $1" in clause
        assert params == ["%john%"]


# =============================================================================
# Test ForeignKey Field
# =============================================================================

class TestForeignKey:
    """Tests for ForeignKey field."""
    
    def test_foreign_key_db_column_name(self):
        """Test ForeignKey generates correct column name."""
        fk = fields.ForeignKey("User")
        fk.name = "author"
        assert fk.db_column_name == "author_id"
    
    def test_foreign_key_custom_column_name(self):
        """Test ForeignKey with custom column name."""
        fk = fields.ForeignKey("User", column_name="user_fk")
        fk.name = "author"
        assert fk.db_column_name == "user_fk"
    
    def test_foreign_key_on_delete_cascade(self):
        """Test ForeignKey with CASCADE on delete."""
        fk = fields.ForeignKey("User", on_delete="CASCADE")
        assert fk.on_delete == "CASCADE"
    
    def test_foreign_key_on_delete_set_null(self):
        """Test ForeignKey with SET NULL on delete."""
        fk = fields.ForeignKey("User", on_delete="SET NULL")
        assert fk.on_delete == "SET NULL"
    
    def test_foreign_key_default_sql_type(self):
        """Test ForeignKey default SQL type is UUID."""
        fk = fields.ForeignKey("User")
        # Default is UUID when target model not resolved
        assert fk.sql_type == "UUID"
    
    def test_foreign_key_get_column_definition(self):
        """Test ForeignKey column definition."""
        fk = fields.ForeignKey("User")
        fk.name = "author"
        definition = fk.get_column_definition()
        assert "author_id" in definition
        assert "UUID" in definition
        assert "NOT NULL" in definition
    
    def test_foreign_key_nullable(self):
        """Test nullable ForeignKey."""
        fk = fields.ForeignKey("User", nullable=True)
        fk.name = "author"
        definition = fk.get_column_definition()
        # Should NOT have NOT NULL
        assert "NOT NULL" not in definition
    
    def test_foreign_key_not_nullable(self):
        """Test non-nullable ForeignKey."""
        fk = fields.ForeignKey("User", nullable=False)
        fk.name = "author"
        definition = fk.get_column_definition()
        assert "NOT NULL" in definition
    
    def test_foreign_key_constraint_definition(self):
        """Test ForeignKey constraint generation."""
        fk = fields.ForeignKey("User", on_delete="CASCADE")
        fk.name = "author"
        constraint = fk.get_constraint_definition()
        assert "FOREIGN KEY (author_id)" in constraint
        assert 'REFERENCES "users"(id)' in constraint
        assert "ON DELETE CASCADE" in constraint
    
    def test_model_with_foreign_key_sql(self):
        """Test model with ForeignKey generates correct SQL."""
        ModelRegistry.clear()
        
        class User(Model):
            id = fields.UUID(primary_key=True)
            name = fields.String(max_length=100)
            
            class Meta:
                table_name = "users"
        
        class Post(Model):
            id = fields.UUID(primary_key=True)
            title = fields.String(max_length=200)
            author = fields.ForeignKey(User)
            
            class Meta:
                table_name = "posts"
        
        sql = Post.get_create_table_sql()
        
        # Check column exists
        assert "author_id" in sql
        assert "UUID" in sql


# =============================================================================
# Test AI Metadata on Fields
# =============================================================================

class TestAIMetadataFields:
    """Tests for AI metadata on fields."""
    
    def test_field_ai_description(self):
        """Test field AI description."""
        f = fields.String(max_length=100, ai_description="User's email address")
        assert f.ai_description == "User's email address"
    
    def test_field_ai_sensitive(self):
        """Test field AI sensitive flag."""
        f = fields.String(max_length=100, ai_sensitive=True)
        assert f.ai_sensitive is True
    
    def test_field_ai_agent_writable(self):
        """Test field AI agent writable flag."""
        f = fields.Integer(ai_agent_writable=False)
        assert f.ai_agent_writable is False
    
    def test_field_default_ai_values(self):
        """Test default AI metadata values."""
        f = fields.String(max_length=100)
        assert f.ai_description is None
        assert f.ai_sensitive is False
        assert f.ai_agent_writable is True
    
    def test_common_field_types_support_ai_metadata(self):
        """Test common field types support AI metadata."""
        field_types = [
            fields.Integer(ai_description="test"),
            fields.String(max_length=10, ai_description="test"),
            fields.Boolean(ai_description="test"),
            fields.DateTime(ai_description="test"),
            fields.JSON(ai_description="test"),
            fields.UUID(ai_description="test"),
            fields.ForeignKey("User", ai_description="test"),
        ]
        
        for f in field_types:
            assert f.ai_description == "test"
    
    def test_field_get_ai_metadata(self):
        """Test field.get_ai_metadata() method."""
        f = fields.String(
            max_length=100,
            nullable=True,
            unique=True,
            ai_description="User email",
            ai_sensitive=True,
            ai_agent_writable=False,
        )
        f.name = "email"
        
        meta = f.get_ai_metadata()
        
        assert meta["name"] == "email"
        assert meta["type"] == "String"
        assert meta["sql_type"] == "VARCHAR(100)"
        assert meta["nullable"] is True
        assert meta["unique"] is True
        assert meta["description"] == "User email"
        assert meta["sensitive"] is True
        assert meta["agent_writable"] is False


# =============================================================================
# Test AI Metadata on Models
# =============================================================================

class TestAIMetadataModels:
    """Tests for AI metadata on models."""
    
    def test_model_ai_meta(self):
        """Test model AI metadata."""
        ModelRegistry.clear()
        
        class Article(Model):
            id = fields.UUID(primary_key=True)
            title = fields.String(max_length=200)
            
            class Meta:
                table_name = "articles"
                ai_name = "Article"
                ai_description = "Blog article content"
                ai_agent_exposed = True
                ai_permissions = ["read", "write"]
        
        # _ai_meta is a ModelAIMeta dataclass
        assert Article._ai_meta.ai_name == "Article"
        assert Article._ai_meta.ai_description == "Blog article content"
        assert Article._ai_meta.ai_agent_exposed is True
        assert Article._ai_meta.ai_permissions == ["read", "write"]
    
    def test_model_ai_meta_defaults(self):
        """Test model AI metadata defaults."""
        ModelRegistry.clear()
        
        class SimpleModel(Model):
            id = fields.UUID(primary_key=True)
            
            class Meta:
                table_name = "simple"
        
        # Should have default values
        assert SimpleModel._ai_meta.ai_agent_exposed is True


# =============================================================================
# Test Registry Helpers
# =============================================================================

class TestRegistryHelpers:
    """Tests for registry helper functions."""
    
    @pytest.fixture(autouse=True)
    def setup_models(self):
        """Set up test models."""
        ModelRegistry.clear()
        
        class User(Model):
            id = fields.UUID(primary_key=True)
            email = fields.String(
                max_length=255,
                ai_description="User email address",
                ai_sensitive=True,
            )
            password_hash = fields.String(
                max_length=255,
                ai_sensitive=True,
                ai_agent_writable=False,
            )
            name = fields.String(max_length=100, ai_description="Display name")
            
            class Meta:
                table_name = "users"
                ai_name = "User"
                ai_description = "System user account"
                ai_agent_exposed = True
                ai_permissions = ["read"]
        
        class InternalLog(Model):
            id = fields.UUID(primary_key=True)
            message = fields.String(max_length=1000)
            
            class Meta:
                table_name = "internal_logs"
                ai_agent_exposed = False
        
        self.User = User
        self.InternalLog = InternalLog
    
    def test_get_models_all(self):
        """Test get_models returns all models."""
        models = get_models()
        assert len(models) == 2
        model_names = {m.__name__ for m in models}
        assert "User" in model_names
        assert "InternalLog" in model_names
    
    def test_get_models_ai_exposed_only(self):
        """Test get_models with ai_exposed_only filter."""
        models = get_models(ai_exposed_only=True)
        assert len(models) == 1
        assert models[0].__name__ == "User"
    
    def test_get_model_meta(self):
        """Test get_model_meta returns correct metadata."""
        meta = get_model_meta(self.User)
        
        assert meta["name"] == "User"
        assert meta["description"] == "System user account"
        assert meta["table"] == "users"
        assert meta["ai_agent_exposed"] is True
        assert meta["ai_permissions"] == ["read"]
        assert "fields" in meta
    
    def test_get_model_fields(self):
        """Test get_model_fields returns field metadata."""
        fields_meta = get_model_fields(self.User)
        
        # Should exclude sensitive fields by default
        field_names = {f["name"] for f in fields_meta}
        assert "id" in field_names
        assert "name" in field_names
        # Sensitive fields excluded
        assert "email" not in field_names
        assert "password_hash" not in field_names
    
    def test_get_model_fields_include_sensitive(self):
        """Test get_model_fields with include_sensitive."""
        fields_meta = get_model_fields(self.User, include_sensitive=True)
        
        field_names = {f["name"] for f in fields_meta}
        assert "email" in field_names
        assert "password_hash" in field_names
    
    def test_get_model_fields_writable_only(self):
        """Test get_model_fields with writable_only filter."""
        fields_meta = get_model_fields(
            self.User,
            include_sensitive=True,
            writable_only=True,
        )
        
        field_names = {f["name"] for f in fields_meta}
        # password_hash is not writable
        assert "password_hash" not in field_names
        # Other fields are writable
        assert "name" in field_names
    
    def test_get_model_schema_for_ai(self):
        """Test get_model_schema_for_ai returns complete schema."""
        schema = get_model_schema_for_ai(self.User)
        
        assert schema["model"] == "User"
        assert schema["description"] == "System user account"
        assert schema["table"] == "users"
        assert schema["permissions"] == ["read"]
        assert "fields" in schema
        assert "writable_fields" in schema
    
    def test_get_all_schemas_for_ai(self):
        """Test get_all_schemas_for_ai returns all exposed schemas."""
        schemas = get_all_schemas_for_ai()
        
        # Should only include AI-exposed models
        assert len(schemas) == 1
        assert schemas[0]["model"] == "User"


# =============================================================================
# Test Migration CLI Components
# =============================================================================

class TestMigrationHelpers:
    """Tests for migration helper functions."""
    
    def test_generate_migration_name(self):
        """Test migration name generation."""
        from vidyut.cli.main import generate_migration_name
        
        name = generate_migration_name("create_users")
        
        # Should start with timestamp
        assert name.startswith("20")
        # Should end with prefix
        assert name.endswith("_create_users")
        # Should have underscore separator
        assert "_" in name
    
    def test_compute_checksum(self):
        """Test SQL checksum computation."""
        from vidyut.cli.main import compute_checksum
        
        sql = "CREATE TABLE users (id INT PRIMARY KEY);"
        checksum = compute_checksum(sql)
        
        # Should be 16 characters (hex)
        assert len(checksum) == 16
        # Should be consistent
        assert compute_checksum(sql) == checksum
        # Different SQL should have different checksum
        assert compute_checksum("SELECT 1;") != checksum
    
    def test_migration_table_sql(self):
        """Test migration table SQL structure."""
        from vidyut.cli.main import MIGRATION_TABLE_SQL
        
        assert "vidyut_migrations" in MIGRATION_TABLE_SQL
        assert "name VARCHAR(255)" in MIGRATION_TABLE_SQL
        assert "checksum VARCHAR(64)" in MIGRATION_TABLE_SQL
        assert "applied_at TIMESTAMP" in MIGRATION_TABLE_SQL
