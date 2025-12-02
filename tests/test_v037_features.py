"""
Tests for v0.3.7 Features

Tests for:
- Non-nullable field validation
- Field validation (Email, URL, Decimal)
- ValidationError exception handling
- UniqueConstraintError exception handling  
- API error codes (404, 409, 422)
- Serializer read_only_fields
- Expand null relations
"""

import os
import pytest
from uuid import UUID
from decimal import Decimal

# Skip DB tests if DATABASE_URL is not set
pytestmark_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set"
)


# =============================================================================
# Unit Tests - No Database Required
# =============================================================================

class TestValidationError:
    """Tests for ValidationError exception."""
    
    def test_validation_error_basic(self):
        from vidyut.exceptions import ValidationError
        
        error = ValidationError("Invalid data")
        assert str(error) == "Invalid data"
        assert error.errors == {}
    
    def test_validation_error_with_errors(self):
        from vidyut.exceptions import ValidationError
        
        errors = {"email": "Invalid email", "name": "Name required"}
        error = ValidationError("Validation failed", errors=errors)
        
        assert error.errors == errors
        assert "email: Invalid email" in str(error)
        assert "name: Name required" in str(error)
    
    def test_validation_error_with_field_name(self):
        from vidyut.exceptions import ValidationError
        
        error = ValidationError("Invalid value", field_name="email")
        assert error.field_name == "email"


class TestFieldValidation:
    """Tests for field validation methods."""
    
    def test_email_validation_valid(self):
        from vidyut.fields import Email
        
        field = Email()
        # Should not raise
        field.validate("user@example.com")
        field.validate("test.user+tag@subdomain.example.co.uk")
    
    def test_email_validation_invalid(self):
        from vidyut.fields import Email
        
        field = Email()
        
        with pytest.raises(ValueError, match="Invalid email"):
            field.validate("not-an-email")
        
        with pytest.raises(ValueError, match="Invalid email"):
            field.validate("missing@domain")
        
        with pytest.raises(ValueError, match="Invalid email"):
            field.validate("@nodomain.com")
    
    def test_url_validation_valid(self):
        from vidyut.fields import URL
        
        field = URL()
        # Should not raise
        field.validate("http://example.com")
        field.validate("https://example.com/path?query=1")
        field.validate("https://subdomain.example.com:8080/path")
    
    def test_url_validation_invalid(self):
        from vidyut.fields import URL
        
        field = URL()
        
        with pytest.raises(ValueError, match="Invalid URL"):
            field.validate("not-a-url")
        
        with pytest.raises(ValueError, match="Invalid URL"):
            field.validate("ftp://invalid-scheme.com")
    
    def test_decimal_validation_valid(self):
        from vidyut.fields import Decimal as DecimalField
        
        field = DecimalField(max_digits=10, decimal_places=2)
        # Should not raise
        field.validate(Decimal("123.45"))
        field.validate(Decimal("0.01"))
        field.validate(Decimal("99999999.99"))
    
    def test_decimal_validation_too_many_digits(self):
        from vidyut.fields import Decimal as DecimalField
        
        field = DecimalField(max_digits=5, decimal_places=2)
        
        with pytest.raises(ValueError, match="digits"):
            field.validate(Decimal("12345.67"))  # 7 total digits
    
    def test_decimal_validation_too_many_decimal_places(self):
        """Decimal places exceeding limit are handled by database (no Python error)."""
        from vidyut.fields import Decimal as DecimalField
        
        field = DecimalField(max_digits=10, decimal_places=2)
        
        # Extra decimal places are truncated/rounded by DB, not validated in Python
        # This is consistent with how NUMERIC type works in PostgreSQL
        result = field.validate(Decimal("123.456"))
        assert result == Decimal("123.456")  # Returned as-is, DB handles truncation


class TestSerializerReadOnlyFields:
    """Tests for read_only_fields in serializers."""
    
    def test_read_only_fields_not_in_input_model(self):
        """Read-only fields should be excluded from input model."""
        from vidyut import Model, fields
        from vidyut.api.serializers import ModelSerializer, clear_serializer_cache
        
        clear_serializer_cache()
        
        class DummyModel(Model):
            __tablename__ = "dummy_test"
            name = fields.String()
            computed = fields.String(nullable=True)
        
        class DummySerializer(ModelSerializer):
            class Meta:
                model = DummyModel
                fields = ["id", "name", "computed", "created_at"]
                read_only_fields = ["id", "computed", "created_at"]
        
        # Get input model
        input_model = DummySerializer._get_or_create_input_model()
        input_fields = input_model.model_fields
        
        # read_only_fields should not be in input model
        assert "id" not in input_fields
        assert "computed" not in input_fields
        assert "created_at" not in input_fields
        
        # writable field should be there
        assert "name" in input_fields
    
    def test_read_only_fields_ignored_in_validation(self):
        """Read-only fields passed in data should be silently ignored."""
        from vidyut import Model, fields
        from vidyut.api.serializers import ModelSerializer, clear_serializer_cache
        
        clear_serializer_cache()
        
        class DummyModel(Model):
            __tablename__ = "dummy_test2"
            name = fields.String()
            readonly_field = fields.String(nullable=True)
        
        class DummySerializer(ModelSerializer):
            class Meta:
                model = DummyModel
                fields = ["id", "name", "readonly_field"]
                read_only_fields = ["id", "readonly_field"]
        
        # Pass read_only field in data - should be ignored
        serializer = DummySerializer(data={
            "name": "Test",
            "readonly_field": "Should be ignored",
            "id": "should-also-be-ignored"
        })
        
        assert serializer.is_valid()
        
        # The read_only field should not be in validated_data
        assert "readonly_field" not in serializer.validated_data
        assert "id" not in serializer.validated_data
        assert serializer.validated_data["name"] == "Test"


# =============================================================================
# Integration Tests - Database Required
# =============================================================================

@pytest.fixture
async def db():
    """Create database connection and clean up tables."""
    from vidyut.db import Database
    from vidyut.registry import ModelRegistry
    
    ModelRegistry.clear()
    
    database_url = os.getenv("DATABASE_URL")
    database = Database(database_url)
    await database.connect()
    
    yield database
    
    # Clean up
    try:
        await database.execute("DROP TABLE IF EXISTS v037_test_users CASCADE")
        await database.execute("DROP TABLE IF EXISTS v037_test_posts CASCADE")
        await database.execute("DROP TABLE IF EXISTS v037_test_profiles CASCADE")
    except Exception:
        pass
    
    await database.disconnect()
    ModelRegistry.clear()


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestNonNullableValidation:
    """Tests for non-nullable field validation."""
    
    @pytest.mark.asyncio
    async def test_non_nullable_field_fails_on_none(self, db):
        """Non-nullable field without default should fail if None."""
        from vidyut import Model, fields
        from vidyut.exceptions import ValidationError
        
        class V037User(Model):
            __tablename__ = "v037_test_users"
            email = fields.String()  # Non-nullable, no default
            name = fields.String(nullable=True)
        
        # Create table
        await db.execute(V037User.get_create_table_sql())
        
        # Try to create with None email - should fail validation
        with pytest.raises(ValidationError, match="email.*cannot be null"):
            user = V037User(email=None)
            await user.save()
    
    @pytest.mark.asyncio
    async def test_non_nullable_with_default_passes(self, db):
        """Non-nullable field with default should pass."""
        from vidyut import Model, fields
        
        class V037User(Model):
            __tablename__ = "v037_test_users"
            email = fields.String()
            status = fields.String(default="active")  # Has default
        
        # Create table
        await db.execute(V037User.get_create_table_sql())
        
        # Should work - status has default
        user = V037User(email="test@example.com")
        await user.save()
        
        assert user.status == "active"
    
    @pytest.mark.asyncio
    async def test_nullable_field_allows_none(self, db):
        """Nullable field should allow None."""
        from vidyut import Model, fields
        
        class V037User(Model):
            __tablename__ = "v037_test_users"
            email = fields.String()
            bio = fields.String(nullable=True)  # Nullable
        
        # Create table
        await db.execute(V037User.get_create_table_sql())
        
        # Should work - bio is nullable
        user = V037User(email="test@example.com", bio=None)
        await user.save()
        
        assert user.bio is None


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestFieldValidationIntegration:
    """Integration tests for field validation on save."""
    
    @pytest.mark.asyncio
    async def test_invalid_email_fails_save(self, db):
        """Invalid email should fail validation on save."""
        from vidyut import Model, fields
        from vidyut.exceptions import ValidationError
        
        class V037Profile(Model):
            __tablename__ = "v037_test_profiles"
            email = fields.Email()
        
        await db.execute(V037Profile.get_create_table_sql())
        
        profile = V037Profile(email="not-an-email")
        
        with pytest.raises(ValidationError, match="Invalid email"):
            await profile.save()
    
    @pytest.mark.asyncio
    async def test_valid_email_passes_save(self, db):
        """Valid email should pass validation on save."""
        from vidyut import Model, fields
        
        class V037Profile(Model):
            __tablename__ = "v037_test_profiles"
            email = fields.Email()
        
        await db.execute(V037Profile.get_create_table_sql())
        
        profile = V037Profile(email="valid@example.com")
        await profile.save()
        
        assert profile.id is not None
    
    @pytest.mark.asyncio
    async def test_invalid_url_fails_save(self, db):
        """Invalid URL should fail validation on save."""
        from vidyut import Model, fields
        from vidyut.exceptions import ValidationError
        
        class V037Profile(Model):
            __tablename__ = "v037_test_profiles"
            website = fields.URL()
        
        await db.execute(V037Profile.get_create_table_sql())
        
        profile = V037Profile(website="not-a-url")
        
        with pytest.raises(ValidationError, match="Invalid URL"):
            await profile.save()


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestUniqueConstraintError:
    """Tests for unique constraint error handling."""
    
    @pytest.mark.asyncio
    async def test_duplicate_raises_unique_error(self, db):
        """Duplicate unique field should raise UniqueConstraintError."""
        from vidyut import Model, fields
        from vidyut.exceptions import UniqueConstraintError
        
        class V037User(Model):
            __tablename__ = "v037_test_users"
            email = fields.Email(unique=True)
        
        await db.execute(V037User.get_create_table_sql())
        
        # Create first user
        user1 = V037User(email="unique@example.com")
        await user1.save()
        
        # Try to create second with same email
        user2 = V037User(email="unique@example.com")
        
        with pytest.raises(UniqueConstraintError):
            await user2.save()


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestExpandNullRelations:
    """Tests for expanding null FK relations."""
    
    @pytest.mark.asyncio
    async def test_expand_null_fk_returns_null(self, db):
        """Expanding a null FK should return null, not error."""
        from vidyut import Model, fields
        from vidyut.api.serializers import ModelSerializer, clear_serializer_cache
        from vidyut.registry import ModelRegistry
        
        clear_serializer_cache()
        
        class V037Author(Model):
            __tablename__ = "v037_test_authors"
            name = fields.String()
        
        class V037Post(Model):
            __tablename__ = "v037_test_posts"
            title = fields.String()
            author = fields.ForeignKey("V037Author", nullable=True)
        
        # Create tables
        await db.execute(V037Author.get_create_table_sql())
        await db.execute(V037Post.get_create_table_sql())
        
        # Create post without author
        post = V037Post(title="Orphan Post", author=None)
        await post.save()
        
        # Serializer with expand
        class PostSerializer(ModelSerializer):
            class Meta:
                model = V037Post
                fields = ["id", "title", "author"]
                expand = ["author"]
        
        serializer = PostSerializer(instance=post)
        data = serializer.to_representation()
        
        # Should have null for expanded author, not error
        assert "author" in data
        assert data["author"] is None
        
        # Clean up
        await db.execute("DROP TABLE IF EXISTS v037_test_posts CASCADE")
        await db.execute("DROP TABLE IF EXISTS v037_test_authors CASCADE")


# =============================================================================
# API Exception Handler Tests
# =============================================================================

class TestAPIExceptionHandlers:
    """Tests for API exception handlers in Vidyut app."""
    
    def test_exception_handlers_registered(self):
        """Test that exception handlers are registered for our errors."""
        from vidyut import Vidyut
        from vidyut.manager import DoesNotExist
        from vidyut.exceptions import ValidationError, UniqueConstraintError
        
        # Create app without DB (just for testing handlers)
        app = Vidyut(database_url=None, auto_discover_views=False)
        
        # Check handlers are registered
        assert DoesNotExist in app.exception_handlers
        assert ValidationError in app.exception_handlers
        assert UniqueConstraintError in app.exception_handlers


class TestManyToManyIdempotent:
    """Tests for ManyToMany.add() idempotency."""
    
    def test_add_sql_has_on_conflict(self):
        """Verify ManyToMany.add() uses ON CONFLICT DO NOTHING."""
        from vidyut.fields import ManyToMany
        
        # The ManyToMany.add() implementation uses ON CONFLICT DO NOTHING
        # This is verified by reading the source - just a sanity check here
        import vidyut.fields as f
        import inspect
        
        source = inspect.getsource(f.ManyToManyManager.add)
        assert "ON CONFLICT" in source or "on conflict" in source.lower()


# =============================================================================
# Additional Unit Tests for v0.3.7
# =============================================================================

class TestEnumValidation:
    """Tests for Enum field validation."""
    
    def test_enum_validation_valid_name(self):
        from vidyut.fields import Enum
        from enum import Enum as PyEnum
        
        class Status(PyEnum):
            ACTIVE = "active"
            INACTIVE = "inactive"
        
        field = Enum(Status)
        result = field.validate("ACTIVE")
        assert result == Status.ACTIVE
    
    def test_enum_validation_valid_value(self):
        from vidyut.fields import Enum
        from enum import Enum as PyEnum
        
        class Status(PyEnum):
            ACTIVE = "active"
            INACTIVE = "inactive"
        
        field = Enum(Status)
        result = field.validate("active")
        assert result == Status.ACTIVE
    
    def test_enum_validation_invalid(self):
        from vidyut.fields import Enum
        from enum import Enum as PyEnum
        
        class Status(PyEnum):
            ACTIVE = "active"
        
        field = Enum(Status)
        
        with pytest.raises(ValueError, match="Invalid enum value"):
            field.validate("unknown")


class TestValidationErrorDetails:
    """Tests for ValidationError with multiple field errors."""
    
    def test_multiple_errors_collected(self):
        """All validation errors should be collected, not just the first."""
        from vidyut.exceptions import ValidationError
        
        errors = {
            "email": "Invalid email format",
            "name": "Name is required",
            "age": "Age must be positive"
        }
        error = ValidationError("Multiple validation errors", errors=errors)
        
        # All errors should be in the dict
        assert len(error.errors) == 3
        assert "email" in error.errors
        assert "name" in error.errors
        assert "age" in error.errors


class TestValidationEdgeCases:
    """Tests for edge cases in field validation."""
    
    def test_email_with_special_characters(self):
        from vidyut.fields import Email
        
        field = Email()
        # Valid emails with special chars
        field.validate("user+tag@example.com")
        field.validate("user.name@example.com")
        field.validate("user_name@example.com")
    
    def test_url_with_port(self):
        from vidyut.fields import URL
        
        field = URL()
        field.validate("http://localhost:8000")
        field.validate("https://example.com:443/path")
    
    def test_url_with_query_and_fragment(self):
        from vidyut.fields import URL
        
        field = URL()
        field.validate("https://example.com/path?query=1&foo=bar")
        field.validate("https://example.com/path#section")
        field.validate("https://example.com/path?q=1#section")
    
    def test_decimal_negative_values(self):
        from vidyut.fields import Decimal as DecimalField
        from decimal import Decimal
        
        field = DecimalField(max_digits=10, decimal_places=2)
        result = field.validate(Decimal("-123.45"))
        assert result == Decimal("-123.45")
    
    def test_decimal_zero(self):
        from vidyut.fields import Decimal as DecimalField
        from decimal import Decimal
        
        field = DecimalField(max_digits=10, decimal_places=2)
        result = field.validate(Decimal("0"))
        assert result == Decimal("0")
    
    def test_nullable_field_validate_none(self):
        from vidyut.fields import Email, URL, Decimal as DecimalField
        from decimal import Decimal
        
        # Nullable fields should accept None
        email_field = Email(nullable=True)
        assert email_field.validate(None) is None
        
        url_field = URL(nullable=True)
        assert url_field.validate(None) is None
        
        decimal_field = DecimalField(nullable=True)
        assert decimal_field.validate(None) is None
    
    def test_non_nullable_field_validate_none_raises(self):
        from vidyut.fields import Email, URL, Decimal as DecimalField
        
        # Non-nullable fields should raise on None
        with pytest.raises(ValueError):
            Email(nullable=False).validate(None)
        
        with pytest.raises(ValueError):
            URL(nullable=False).validate(None)
        
        with pytest.raises(ValueError):
            DecimalField(nullable=False).validate(None)


class TestManagerCreateValidation:
    """Tests that Manager.create() also triggers validation."""
    
    def test_manager_create_calls_save(self):
        """Manager.create() should call save() which triggers validation."""
        import vidyut.manager as m
        import inspect
        
        # Verify create method calls save
        source = inspect.getsource(m.Manager.create)
        assert "await instance.save()" in source or "save()" in source


class TestSerializerValidationIntegration:
    """Tests for serializer validation integration."""
    
    def test_serializer_validates_field_types(self):
        """Serializer should validate field values using Pydantic."""
        from vidyut import Model, fields
        from vidyut.api.serializers import ModelSerializer, clear_serializer_cache
        
        clear_serializer_cache()
        
        class TestModel(Model):
            __tablename__ = "test_validate"
            count = fields.Integer()
        
        class TestSerializer(ModelSerializer):
            class Meta:
                model = TestModel
                fields = ["count"]
        
        # Invalid integer should fail Pydantic validation
        serializer = TestSerializer(data={"count": "not-an-integer"})
        assert not serializer.is_valid()
        assert "count" in serializer.errors


class TestExceptionInheritance:
    """Tests for exception class hierarchy."""
    
    def test_validation_error_is_vidyut_error(self):
        from vidyut.exceptions import ValidationError, VidyutError
        
        error = ValidationError("test")
        assert isinstance(error, VidyutError)
    
    def test_unique_constraint_error_is_database_error(self):
        from vidyut.exceptions import UniqueConstraintError, DatabaseError
        
        error = UniqueConstraintError("test")
        assert isinstance(error, DatabaseError)


# =============================================================================
# Additional Integration Tests
# =============================================================================

@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestMultipleValidationErrors:
    """Tests for multiple validation errors at once."""
    
    @pytest.mark.asyncio
    async def test_multiple_errors_reported(self, db):
        """Multiple validation failures should all be in errors dict."""
        from vidyut import Model, fields
        from vidyut.exceptions import ValidationError
        
        class V037MultiError(Model):
            __tablename__ = "v037_test_users"
            email = fields.Email()
            website = fields.URL()
        
        await db.execute(V037MultiError.get_create_table_sql())
        
        # Both fields invalid
        instance = V037MultiError(email="bad-email", website="bad-url")
        
        with pytest.raises(ValidationError) as exc_info:
            await instance.save()
        
        # Both errors should be captured
        assert len(exc_info.value.errors) == 2
        assert "email" in exc_info.value.errors
        assert "website" in exc_info.value.errors


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestUpdateValidation:
    """Tests that validation runs on update, not just create."""
    
    @pytest.mark.asyncio
    async def test_validation_on_update(self, db):
        """Validation should run when updating existing records."""
        from vidyut import Model, fields
        from vidyut.exceptions import ValidationError
        
        class V037User(Model):
            __tablename__ = "v037_test_users"
            email = fields.Email()
            name = fields.String(nullable=True)
        
        await db.execute(V037User.get_create_table_sql())
        
        # Create valid user
        user = V037User(email="valid@example.com", name="Test")
        await user.save()
        
        # Update with invalid email
        user.email = "invalid-email"
        
        with pytest.raises(ValidationError, match="Invalid email"):
            await user.save()


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestManyToManyIdempotentIntegration:
    """Integration tests for ManyToMany.add() idempotency."""
    
    @pytest.mark.asyncio
    async def test_add_same_item_twice_no_error(self, db):
        """Adding the same item twice should not raise an error."""
        from vidyut import Model, fields
        from vidyut.registry import ModelRegistry
        
        class V037Tag(Model):
            __tablename__ = "v037_test_tags"
            name = fields.String()
        
        class V037Article(Model):
            __tablename__ = "v037_test_articles"
            title = fields.String()
            tags = fields.ManyToMany("V037Tag")
        
        # Create tables using the ORM's SQL generation
        await db.execute(V037Tag.get_create_table_sql())
        await db.execute(V037Article.get_create_table_sql())
        
        # Use the M2M field's join table SQL generator
        m2m_field = V037Article._m2m_fields["tags"]
        await db.execute(m2m_field.get_join_table_sql())
        
        # Create tag and article
        tag = V037Tag(name="Python")
        await tag.save()
        
        article = V037Article(title="Test Article")
        await article.save()
        
        # Add same tag twice - should not error
        await article.tags.add(tag)
        await article.tags.add(tag)  # Second add should be idempotent
        
        # Should still only have one association
        tags = await article.tags.all()
        assert len(tags) == 1
        
        # Clean up
        join_table = m2m_field.join_table_name
        await db.execute(f"DROP TABLE IF EXISTS {join_table} CASCADE")
        await db.execute("DROP TABLE IF EXISTS v037_test_articles CASCADE")
        await db.execute("DROP TABLE IF EXISTS v037_test_tags CASCADE")


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestDecimalValidationIntegration:
    """Integration tests for Decimal field validation."""
    
    @pytest.mark.asyncio
    async def test_decimal_too_many_digits_fails(self, db):
        """Decimal with too many digits should fail validation."""
        from vidyut import Model, fields
        from vidyut.exceptions import ValidationError
        from decimal import Decimal
        
        class V037Product(Model):
            __tablename__ = "v037_test_profiles"
            price = fields.Decimal(max_digits=5, decimal_places=2)
        
        await db.execute(V037Product.get_create_table_sql())
        
        # Too many integer digits (999.99 is max for 5,2)
        product = V037Product(price=Decimal("12345.67"))
        
        with pytest.raises(ValidationError, match="digits"):
            await product.save()
    
    @pytest.mark.asyncio
    async def test_valid_decimal_saves(self, db):
        """Valid decimal should save successfully."""
        from vidyut import Model, fields
        from decimal import Decimal
        
        class V037Product(Model):
            __tablename__ = "v037_test_profiles"
            price = fields.Decimal(max_digits=10, decimal_places=2)
        
        await db.execute(V037Product.get_create_table_sql())
        
        product = V037Product(price=Decimal("99.99"))
        await product.save()
        
        assert product.id is not None


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestEnumValidationIntegration:
    """Integration tests for Enum field validation."""
    
    @pytest.mark.asyncio
    async def test_invalid_enum_fails_save(self, db):
        """Invalid enum value should fail validation on save."""
        from vidyut import Model, fields
        from vidyut.exceptions import ValidationError
        from enum import Enum as PyEnum
        
        class Status(PyEnum):
            ACTIVE = "active"
            INACTIVE = "inactive"
        
        class V037Item(Model):
            __tablename__ = "v037_test_profiles"
            status = fields.Enum(Status)
        
        await db.execute(V037Item.get_create_table_sql())
        
        item = V037Item(status="unknown")
        
        with pytest.raises(ValidationError, match="Invalid enum"):
            await item.save()
    
    @pytest.mark.asyncio
    async def test_valid_enum_saves(self, db):
        """Valid enum should save successfully."""
        from vidyut import Model, fields
        from enum import Enum as PyEnum
        
        class Status(PyEnum):
            ACTIVE = "active"
            INACTIVE = "inactive"
        
        class V037Item(Model):
            __tablename__ = "v037_test_profiles"
            status = fields.Enum(Status)
        
        await db.execute(V037Item.get_create_table_sql())
        
        item = V037Item(status=Status.ACTIVE)
        await item.save()
        
        assert item.id is not None
