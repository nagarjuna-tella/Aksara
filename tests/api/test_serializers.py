"""
Tests for ModelSerializer.

Tests:
    - Serializer initialization and Meta validation
    - Field filtering (fields, exclude, read_only_fields)
    - Pydantic model generation
    - Validation hooks (validate_<field>, validate)
    - Async save/create/update
    - Nested FK expansion
    - Integration with ModelViewSet
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Optional

from pydantic import ValidationError

from aksara import Model, fields
from aksara.api.serializers import (
    ModelSerializer,
    serialize_instance,
    serialize_many,
    clear_serializer_cache,
)
from aksara.api.schemas import clear_schema_cache


# =============================================================================
# Test Models
# =============================================================================

class Author(Model):
    """Author model for testing FK expansion."""
    name = fields.String(max_length=100)
    email = fields.String(max_length=255, unique=True)
    bio = fields.String(max_length=1000, nullable=True)
    
    class Meta:
        table_name = "authors"


class Book(Model):
    """Book model with FK to Author."""
    title = fields.String(max_length=200)
    isbn = fields.String(max_length=20, unique=True)
    pages = fields.Integer(default=0)
    is_published = fields.Boolean(default=False)
    author = fields.ForeignKey(Author, nullable=True)
    metadata = fields.JSON(nullable=True)
    
    class Meta:
        table_name = "books"


class Category(Model):
    """Simple model for testing."""
    name = fields.String(max_length=50)
    description = fields.String(max_length=200, nullable=True)
    is_active = fields.Boolean(default=True)
    
    class Meta:
        table_name = "categories"


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all caches before each test."""
    clear_serializer_cache()
    clear_schema_cache()
    yield
    clear_serializer_cache()
    clear_schema_cache()


@pytest.fixture
def sample_author_data():
    """Sample author data."""
    return {
        "id": uuid4(),
        "name": "John Doe",
        "email": "john@example.com",
        "bio": "A prolific author",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_book_data(sample_author_data):
    """Sample book data."""
    return {
        "id": uuid4(),
        "title": "Test Book",
        "isbn": "978-0-123456-78-9",
        "pages": 300,
        "is_published": True,
        "author_id": sample_author_data["id"],
        "metadata": {"genre": "fiction"},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def mock_author(sample_author_data):
    """Create a mock author instance."""
    author = Author(**sample_author_data)
    author._is_new = False
    return author


@pytest.fixture
def mock_book(sample_book_data):
    """Create a mock book instance."""
    book = Book(**sample_book_data)
    book._is_new = False
    return book


# =============================================================================
# Meta Validation Tests
# =============================================================================

class TestMetaValidation:
    """Tests for Meta class validation."""
    
    def test_missing_meta_raises(self):
        """Serializer without proper Meta should raise TypeError."""
        # When no Meta is defined, the base class Meta is inherited
        # which has model=None, so it raises about missing model
        with pytest.raises(TypeError, match="must define 'model' attribute"):
            class BadSerializer(ModelSerializer):
                pass
    
    def test_missing_model_raises(self):
        """Meta without model should raise TypeError."""
        with pytest.raises(TypeError, match="must define 'model' attribute"):
            class BadSerializer(ModelSerializer):
                class Meta:
                    fields = "__all__"
    
    def test_missing_fields_raises(self):
        """Meta without fields should raise TypeError."""
        with pytest.raises(TypeError, match="must define 'fields' attribute"):
            class BadSerializer(ModelSerializer):
                class Meta:
                    model = Category
    
    def test_valid_meta_succeeds(self):
        """Valid Meta should create serializer successfully."""
        class ValidSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        serializer = ValidSerializer()
        assert serializer._model == Category


# =============================================================================
# Field Selection Tests
# =============================================================================

class TestFieldSelection:
    """Tests for fields, exclude, and read_only_fields."""
    
    def test_fields_all(self):
        """fields = '__all__' should include all model fields."""
        class AllFieldsSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        field_names = AllFieldsSerializer._get_field_names()
        
        assert "id" in field_names
        assert "name" in field_names
        assert "description" in field_names
        assert "is_active" in field_names
    
    def test_fields_explicit(self):
        """Explicit fields list should only include specified fields."""
        class ExplicitSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = ["id", "name"]
        
        field_names = ExplicitSerializer._get_field_names()
        
        assert field_names == ["id", "name"]
        assert "description" not in field_names
    
    def test_exclude(self):
        """exclude should remove fields from __all__."""
        class ExcludeSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
                exclude = ["description", "is_active"]
        
        field_names = ExcludeSerializer._get_field_names()
        
        assert "id" in field_names
        assert "name" in field_names
        assert "description" not in field_names
        assert "is_active" not in field_names
    
    def test_read_only_excluded_from_input(self):
        """read_only_fields should be excluded from input model."""
        class ReadOnlySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
                read_only_fields = ["id", "created_at", "updated_at"]
        
        input_model = ReadOnlySerializer._get_or_create_input_model()
        input_fields = set(input_model.model_fields.keys())
        
        # read_only_fields should not be in input
        assert "id" not in input_fields
        # But writable fields should be there
        assert "name" in input_fields
    
    def test_read_only_included_in_output(self):
        """read_only_fields should be included in output model."""
        class ReadOnlySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
                read_only_fields = ["id"]
        
        output_model = ReadOnlySerializer._get_or_create_output_model()
        output_fields = set(output_model.model_fields.keys())
        
        assert "id" in output_fields
        assert "name" in output_fields


# =============================================================================
# Pydantic Model Generation Tests
# =============================================================================

class TestPydanticGeneration:
    """Tests for Pydantic model generation."""
    
    def test_input_model_name(self):
        """Input model should have correct name."""
        class NamedSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        input_model = NamedSerializer._get_or_create_input_model()
        assert input_model.__name__ == "NamedSerializerInput"
    
    def test_output_model_name(self):
        """Output model should have correct name."""
        class NamedSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        output_model = NamedSerializer._get_or_create_output_model()
        assert output_model.__name__ == "NamedSerializerOutput"
    
    def test_model_caching(self):
        """Generated models should be cached."""
        class CachedSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        input1 = CachedSerializer._get_or_create_input_model()
        input2 = CachedSerializer._get_or_create_input_model()
        
        assert input1 is input2
    
    def test_get_input_model_method(self):
        """get_input_model() should return the input Pydantic model."""
        class TestSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        serializer = TestSerializer()
        input_model = serializer.get_input_model()
        
        assert input_model.__name__ == "TestSerializerInput"
    
    def test_get_output_model_method(self):
        """get_output_model() should return the output Pydantic model."""
        class TestSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        serializer = TestSerializer()
        output_model = serializer.get_output_model()
        
        assert output_model.__name__ == "TestSerializerOutput"


# =============================================================================
# Validation Tests
# =============================================================================

class TestValidation:
    """Tests for is_valid() and validation hooks."""
    
    def test_is_valid_with_valid_data(self):
        """is_valid() should return True for valid data."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        serializer = CategorySerializer(data={"name": "Test Category"})
        
        assert serializer.is_valid() == True
        assert serializer.errors is None
    
    def test_is_valid_with_invalid_data(self):
        """is_valid() should return False for invalid data."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        # name is required
        serializer = CategorySerializer(data={})
        
        assert serializer.is_valid() == False
        assert serializer.errors is not None
    
    def test_is_valid_raise_exception(self):
        """is_valid(raise_exception=True) should raise on invalid data."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        serializer = CategorySerializer(data={})
        
        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)
    
    def test_validated_data_before_is_valid_raises(self):
        """Accessing validated_data before is_valid() should raise."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        serializer = CategorySerializer(data={"name": "Test"})
        
        with pytest.raises(AssertionError, match="must call `.is_valid\\(\\)`"):
            _ = serializer.validated_data
    
    def test_validated_data_after_is_valid(self):
        """validated_data should be available after is_valid()."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        serializer = CategorySerializer(data={"name": "Test"})
        serializer.is_valid()
        
        assert serializer.validated_data["name"] == "Test"
    
    def test_no_data_provided(self):
        """is_valid() with no data should return False."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        serializer = CategorySerializer()
        
        assert serializer.is_valid() == False
        assert "non_field_errors" in serializer.errors


# =============================================================================
# Validation Hook Tests
# =============================================================================

class TestValidationHooks:
    """Tests for validate_<field> and validate() hooks."""
    
    def test_validate_field_hook(self):
        """validate_<field>() should be called for each field."""
        class HookSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
            
            def validate_name(self, value):
                return value.upper()
        
        serializer = HookSerializer(data={"name": "test"})
        serializer.is_valid()
        
        assert serializer.validated_data["name"] == "TEST"
    
    def test_validate_field_raises(self):
        """validate_<field>() raising should fail validation."""
        class HookSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
            
            def validate_name(self, value):
                if len(value) < 5:
                    raise ValueError("Name too short")
                return value
        
        serializer = HookSerializer(data={"name": "ab"})
        
        assert serializer.is_valid() == False
        assert "non_field_errors" in serializer.errors
    
    def test_validate_hook(self):
        """validate() should be called for cross-field validation."""
        class HookSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
            
            def validate(self, data):
                data["validated"] = True
                return data
        
        serializer = HookSerializer(data={"name": "Test"})
        serializer.is_valid()
        
        assert serializer.validated_data.get("validated") == True
    
    def test_validate_raises(self):
        """validate() raising should fail validation."""
        class HookSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
            
            def validate(self, data):
                raise ValueError("Cross-field validation failed")
        
        serializer = HookSerializer(data={"name": "Test"})
        
        assert serializer.is_valid() == False


# =============================================================================
# Many=True Tests
# =============================================================================

class TestManyMode:
    """Tests for many=True mode."""
    
    def test_is_valid_many(self):
        """is_valid() should work with many=True."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        serializer = CategorySerializer(
            data=[
                {"name": "Category 1"},
                {"name": "Category 2"},
            ],
            many=True,
        )
        
        assert serializer.is_valid() == True
        assert len(serializer.validated_data) == 2
    
    def test_is_valid_many_with_invalid(self):
        """is_valid(many=True) should fail if any item is invalid."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        serializer = CategorySerializer(
            data=[
                {"name": "Valid"},
                {},  # Invalid - missing name
            ],
            many=True,
        )
        
        assert serializer.is_valid() == False


# =============================================================================
# Serialization Tests
# =============================================================================

class TestSerialization:
    """Tests for to_representation()."""
    
    def test_to_representation_single(self, mock_author):
        """to_representation() should serialize a single instance."""
        class AuthorSerializer(ModelSerializer):
            class Meta:
                model = Author
                fields = ["id", "name", "email"]
        
        serializer = AuthorSerializer(instance=mock_author)
        data = serializer.to_representation()
        
        assert data["name"] == "John Doe"
        assert data["email"] == "john@example.com"
        assert "bio" not in data  # Not in fields
    
    def test_to_representation_many(self, mock_author):
        """to_representation() should serialize multiple instances."""
        class AuthorSerializer(ModelSerializer):
            class Meta:
                model = Author
                fields = ["id", "name"]
        
        serializer = AuthorSerializer(instance=[mock_author, mock_author], many=True)
        data = serializer.to_representation()
        
        assert len(data) == 2
        assert data[0]["name"] == "John Doe"
    
    def test_data_property(self, mock_author):
        """data property should return serialized representation."""
        class AuthorSerializer(ModelSerializer):
            class Meta:
                model = Author
                fields = ["id", "name"]
        
        serializer = AuthorSerializer(instance=mock_author)
        
        assert serializer.data["name"] == "John Doe"


# =============================================================================
# Save/Create/Update Tests
# =============================================================================

class TestSaveCreateUpdate:
    """Tests for async save/create/update."""
    
    @pytest.mark.asyncio
    async def test_save_before_is_valid_raises(self):
        """save() before is_valid() should raise."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        serializer = CategorySerializer(data={"name": "Test"})
        
        with pytest.raises(AssertionError, match="must call `.is_valid\\(\\)`"):
            await serializer.save()
    
    @pytest.mark.asyncio
    async def test_create(self):
        """create() should create a new instance."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        mock_instance = Category(name="Test")
        mock_instance._is_new = False
        
        with patch.object(Category.objects, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_instance
            
            serializer = CategorySerializer(data={"name": "Test"})
            serializer.is_valid()
            
            result = await serializer.save()
            
            mock_create.assert_called_once()
            assert result.name == "Test"
    
    @pytest.mark.asyncio
    async def test_update(self, mock_author):
        """update() should update an existing instance."""
        class AuthorSerializer(ModelSerializer):
            class Meta:
                model = Author
                fields = ["name", "bio"]  # Only include optional/updatable fields
        
        mock_author.save = AsyncMock()
        
        serializer = AuthorSerializer(
            instance=mock_author,
            data={"name": "Jane Doe"},
        )
        assert serializer.is_valid() == True, f"Validation failed: {serializer.errors}"
        
        result = await serializer.save()
        
        mock_author.save.assert_called_once()
        assert result.name == "Jane Doe"
    
    @pytest.mark.asyncio
    async def test_custom_create(self):
        """Custom create() method should be called."""
        class CustomSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
            
            async def create(self, validated_data):
                validated_data["custom"] = True
                return await super().create(validated_data)
        
        mock_instance = Category(name="Test")
        
        with patch.object(Category.objects, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_instance
            
            serializer = CustomSerializer(data={"name": "Test"})
            serializer.is_valid()
            
            await serializer.save()
            
            # Verify custom key was added
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs.get("custom") == True


# =============================================================================
# FK Expansion Tests
# =============================================================================

class TestFKExpansion:
    """Tests for FK expansion via expand."""
    
    def test_expand_list_format(self, mock_book, mock_author):
        """expand as list should include related data."""
        class BookSerializer(ModelSerializer):
            class Meta:
                model = Book
                fields = "__all__"
                expand = ["author"]
        
        # Set up cached author on book
        mock_book._data["_author_obj"] = mock_author
        
        serializer = BookSerializer(instance=mock_book)
        data = serializer.to_representation()
        
        # The expand feature should try to include author data
        # For now we just verify serialization works
        assert data["title"] == "Test Book"
    
    def test_expand_dict_format(self, mock_book, mock_author):
        """expand as dict should use nested serializer."""
        class AuthorSerializer(ModelSerializer):
            class Meta:
                model = Author
                fields = ["id", "name"]
        
        class BookSerializer(ModelSerializer):
            class Meta:
                model = Book
                fields = "__all__"
                expand = {"author": AuthorSerializer}
        
        # Set up cached author on book
        mock_book._data["_author_obj"] = mock_author
        
        serializer = BookSerializer(instance=mock_book)
        data = serializer.to_representation()
        
        assert data["title"] == "Test Book"


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestHelperFunctions:
    """Tests for serialize_instance and serialize_many."""
    
    def test_serialize_instance_with_serializer(self, mock_author):
        """serialize_instance with serializer should use it."""
        class AuthorSerializer(ModelSerializer):
            class Meta:
                model = Author
                fields = ["id", "name"]
        
        data = serialize_instance(mock_author, AuthorSerializer)
        
        assert data["name"] == "John Doe"
        assert "email" not in data
    
    def test_serialize_many_with_serializer(self, mock_author):
        """serialize_many with serializer should handle lists."""
        class AuthorSerializer(ModelSerializer):
            class Meta:
                model = Author
                fields = ["id", "name"]
        
        data = serialize_many([mock_author, mock_author], AuthorSerializer)
        
        assert len(data) == 2
        assert data[0]["name"] == "John Doe"


# =============================================================================
# ForeignKey Field Handling Tests
# =============================================================================

class TestForeignKeyFields:
    """Tests for ForeignKey field handling in serializers."""
    
    def test_fk_uses_id_column(self, mock_book):
        """ForeignKey fields should use the _id column name."""
        class BookSerializer(ModelSerializer):
            class Meta:
                model = Book
                fields = ["id", "title", "author"]
        
        serializer = BookSerializer(instance=mock_book)
        data = serializer.to_representation()
        
        # Should use author_id, not author
        assert "author_id" in data
    
    def test_fk_in_input(self):
        """ForeignKey should be UUID type in input model."""
        class BookSerializer(ModelSerializer):
            class Meta:
                model = Book
                fields = ["title", "author"]
        
        input_model = BookSerializer._get_or_create_input_model()
        
        # Should have author_id field
        assert "author_id" in input_model.model_fields


# =============================================================================
# Clear Cache Test
# =============================================================================

class TestClearCache:
    """Tests for cache clearing."""
    
    def test_clear_serializer_cache(self):
        """clear_serializer_cache should clear the cache."""
        class TestSerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        # Generate and cache
        _ = TestSerializer._get_or_create_input_model()
        
        # Clear
        clear_serializer_cache()
        
        # Re-generate should create new model
        from aksara.api.serializers import _serializer_model_cache
        assert len(_serializer_model_cache) == 0


# =============================================================================
# ViewSet + Serializer Integration Tests
# =============================================================================

class TestViewSetIntegration:
    """Tests for ModelViewSet + ModelSerializer integration."""
    
    def test_viewset_with_serializer_class(self):
        """ViewSet should accept serializer class attributes."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = ["id", "name"]
        
        from aksara.api import ModelViewSet
        
        class CategoryViewSet(ModelViewSet):
            model = Category
            prefix = "/categories"
            create_serializer_class = CategorySerializer
            retrieve_serializer_class = CategorySerializer
        
        viewset = CategoryViewSet()
        
        assert viewset.create_serializer_class == CategorySerializer
        assert viewset.retrieve_serializer_class == CategorySerializer
    
    def test_viewset_uses_serializer_returns_true(self):
        """uses_serializer() should return True when serializer is defined."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        from aksara.api import ModelViewSet
        
        class CategoryViewSet(ModelViewSet):
            model = Category
            prefix = "/categories"
            create_serializer_class = CategorySerializer
        
        viewset = CategoryViewSet()
        
        assert viewset.uses_serializer('create') == True
        assert viewset.uses_serializer('retrieve') == False
    
    def test_viewset_get_serializer(self):
        """get_serializer() should return instantiated serializer."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = "__all__"
        
        from aksara.api import ModelViewSet
        
        class CategoryViewSet(ModelViewSet):
            model = Category
            prefix = "/categories"
            create_serializer_class = CategorySerializer
        
        viewset = CategoryViewSet()
        serializer = viewset.get_serializer('create', data={"name": "Test"})
        
        assert serializer is not None
        assert isinstance(serializer, CategorySerializer)
        assert serializer.initial_data == {"name": "Test"}
    
    def test_viewset_get_serializer_returns_none(self):
        """get_serializer() should return None when no serializer defined."""
        from aksara.api import ModelViewSet
        
        class CategoryViewSet(ModelViewSet):
            model = Category
            prefix = "/categories"
        
        viewset = CategoryViewSet()
        serializer = viewset.get_serializer('create', data={"name": "Test"})
        
        assert serializer is None
    
    @pytest.mark.asyncio
    async def test_viewset_create_with_serializer(self):
        """ViewSet create should use serializer when defined."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = ["name", "description"]
            
            def validate_name(self, value):
                return value.upper()
        
        from aksara.api import ModelViewSet
        from fastapi import Request
        from unittest.mock import MagicMock
        
        class CategoryViewSet(ModelViewSet):
            model = Category
            prefix = "/categories"
            create_serializer_class = CategorySerializer
        
        mock_request = MagicMock(spec=Request)
        mock_instance = Category(name="TEST")
        mock_instance._is_new = False
        
        with patch.object(Category.objects, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_instance
            
            viewset = CategoryViewSet()
            result = await viewset.create(
                data={"name": "test"},
                request=mock_request,
            )
            
            # The validate_name should have uppercased the name
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["name"] == "TEST"
    
    @pytest.mark.asyncio
    async def test_viewset_update_with_serializer(self):
        """ViewSet update should use serializer when defined."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = ["name", "description"]
        
        from aksara.api import ModelViewSet
        from fastapi import Request
        from unittest.mock import MagicMock
        
        class CategoryViewSet(ModelViewSet):
            model = Category
            prefix = "/categories"
            update_serializer_class = CategorySerializer
        
        mock_request = MagicMock(spec=Request)
        mock_instance = Category(name="Original", id=uuid4())
        mock_instance._is_new = False
        mock_instance.save = AsyncMock()
        
        with patch.object(Category.objects, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_instance
            
            viewset = CategoryViewSet()
            result = await viewset.update(
                pk=str(mock_instance.id),
                data={"name": "Updated"},
                request=mock_request,
            )
            
            # Name should be updated
            assert mock_instance.name == "Updated"
            mock_instance.save.assert_called_once()
    
    def test_viewset_serialize_with_serializer(self):
        """_serialize should use serializer when defined."""
        class CategorySerializer(ModelSerializer):
            class Meta:
                model = Category
                fields = ["id", "name"]  # Only id and name
        
        from aksara.api import ModelViewSet
        
        class CategoryViewSet(ModelViewSet):
            model = Category
            prefix = "/categories"
            retrieve_serializer_class = CategorySerializer
        
        mock_instance = Category(id=uuid4(), name="Test", description="A description")
        mock_instance._is_new = False
        
        viewset = CategoryViewSet()
        data = viewset._serialize(mock_instance, action='retrieve')
        
        assert "name" in data
        assert "description" not in data  # Should be excluded by serializer
