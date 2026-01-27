"""
Sanity Audit Tests (v0.3.18+)

Comprehensive tests to verify all subsystems work correctly
as a pre-0.4.0 hardening measure.

Tests cover:
- Public API exports
- Field edge cases
- QuerySet operations
- M2M edge cases
- Error mapping consistency
- Context var isolation
- Exception message formatting
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum


# =============================================================================
# Test Public API Exports
# =============================================================================

class TestPublicAPIExports:
    """Verify all public APIs are properly exported from aksara package."""
    
    def test_core_exports(self):
        """Core ORM exports should be available."""
        import aksara
        
        # Core ORM
        assert hasattr(aksara, 'Model')
        assert hasattr(aksara, 'fields')
        assert hasattr(aksara, 'Database')
        
        # Exceptions
        assert hasattr(aksara, 'AksaraError')
        assert hasattr(aksara, 'DatabaseError')
        assert hasattr(aksara, 'ValidationError')
        assert hasattr(aksara, 'ConfigurationError')
        assert hasattr(aksara, 'UniqueConstraintError')
        assert hasattr(aksara, 'ForeignKeyConstraintError')
        assert hasattr(aksara, 'NotNullConstraintError')
        assert hasattr(aksara, 'RestrictedError')
        assert hasattr(aksara, 'DoesNotExist')
        assert hasattr(aksara, 'MultipleObjectsReturned')
        
        # on_delete constants
        assert hasattr(aksara, 'CASCADE')
        assert hasattr(aksara, 'SET_NULL')
        assert hasattr(aksara, 'RESTRICT')
        assert hasattr(aksara, 'PROTECT')
    
    def test_api_layer_exports(self):
        """API layer exports should be available."""
        import aksara
        
        assert hasattr(aksara, 'ModelViewSet')
        assert hasattr(aksara, 'ModelSerializer')
        assert hasattr(aksara, 'action')
        assert hasattr(aksara, 'include_viewset')
        assert hasattr(aksara, 'discover_viewsets')
    
    def test_permission_exports(self):
        """Permission exports should be available."""
        import aksara
        
        assert hasattr(aksara, 'BasePermission')
        assert hasattr(aksara, 'AllowAny')
        assert hasattr(aksara, 'IsAuthenticated')
        assert hasattr(aksara, 'IsAdminUser')
        assert hasattr(aksara, 'IsActiveUser')
        assert hasattr(aksara, 'IsOwnerOrReadOnly')
        assert hasattr(aksara, 'DenyAI')
        assert hasattr(aksara, 'AND')
        assert hasattr(aksara, 'OR')
        assert hasattr(aksara, 'check_permissions')
    
    def test_identity_exports(self):
        """Identity exports should be available."""
        import aksara
        
        assert hasattr(aksara, 'AksaraUserProtocol')
        assert hasattr(aksara, 'AnonymousUser')
    
    def test_migration_exports(self):
        """Migration exports should be available."""
        import aksara
        
        assert hasattr(aksara, 'Migration')
        assert hasattr(aksara, 'migration_operations')
    
    def test_fastapi_re_exports(self):
        """FastAPI re-exports should be available."""
        import aksara
        
        assert hasattr(aksara, 'Aksara')
        assert hasattr(aksara, 'FastAPI')
        assert hasattr(aksara, 'APIRouter')
        assert hasattr(aksara, 'HTTPException')
        assert hasattr(aksara, 'Depends')


# =============================================================================
# Test Field Edge Cases
# =============================================================================

class TestFieldEdgeCases:
    """Test field edge cases and validation."""
    
    def test_string_field_default_value(self):
        """String field with default should use default."""
        from aksara.fields import String
        
        field = String(default="hello")
        assert field.get_default_value() == "hello"
    
    def test_string_field_callable_default(self):
        """String field with callable default should call it."""
        from aksara.fields import String
        
        counter = [0]
        def get_default():
            counter[0] += 1
            return f"value_{counter[0]}"
        
        field = String(default=get_default)
        
        assert field.get_default_value() == "value_1"
        assert field.get_default_value() == "value_2"
    
    def test_email_field_normalization(self):
        """Email field should normalize values."""
        from aksara.fields import Email
        
        field = Email()
        
        assert field.to_python("Test@EXAMPLE.COM") == "test@example.com"
        assert field.to_python("  user@domain.org  ") == "user@domain.org"
        assert field.to_python(None) is None
    
    def test_email_field_validation(self):
        """Email field should validate format."""
        from aksara.fields import Email
        
        field = Email()
        field.name = "email"
        
        # Valid emails should pass
        field.validate("user@example.com")
        field.validate("test.user+tag@sub.domain.org")
        
        # Invalid emails should raise
        with pytest.raises(ValueError, match="Invalid email"):
            field.validate("not-an-email")
        
        with pytest.raises(ValueError, match="Invalid email"):
            field.validate("@missing-local.com")
    
    def test_decimal_field_precision(self):
        """Decimal field should respect precision settings."""
        from aksara.fields import Decimal as DecimalField
        
        field = DecimalField(max_digits=6, decimal_places=2)
        
        assert field.sql_type == "NUMERIC(6, 2)"
        
        # Valid precision
        result = field.to_python("1234.56")
        assert result == Decimal("1234.56")
    
    def test_enum_field_roundtrip(self):
        """Enum field should preserve value through to_python/to_db cycle."""
        from aksara.fields import EnumField
        
        class Status(Enum):
            ACTIVE = "active"
            INACTIVE = "inactive"
        
        field = EnumField(Status)
        
        # to_db should store the value
        assert field.to_db(Status.ACTIVE) == "active"
        
        # to_python should restore the enum
        assert field.to_python("active") == Status.ACTIVE
    
    def test_json_field_dict_default(self):
        """JSON field with dict default should work correctly."""
        from aksara.fields import JSON
        
        field = JSON(default=dict)
        
        # Callable default should create new dict each time
        d1 = field.get_default_value()
        d2 = field.get_default_value()
        
        assert d1 == {}
        assert d2 == {}
        assert d1 is not d2  # Different objects
    
    def test_uuid_field_primary_key_auto_generates(self):
        """UUID field as primary key should auto-generate."""
        from aksara.fields import UUID
        import uuid as uuid_lib
        
        field = UUID(primary_key=True)
        
        default = field.get_default_value()
        assert isinstance(default, uuid_lib.UUID)
    
    def test_boolean_field_default(self):
        """Boolean field should handle defaults correctly."""
        from aksara.fields import Boolean
        
        field_true = Boolean(default=True)
        field_false = Boolean(default=False)
        
        assert field_true.get_default_value() is True
        assert field_false.get_default_value() is False


# =============================================================================
# Test Exception Consistency
# =============================================================================

class TestExceptionConsistency:
    """Test exception messages and structure."""
    
    def test_validation_error_structure(self):
        """ValidationError should have proper structure."""
        from aksara.exceptions import ValidationError
        
        error = ValidationError(
            "Validation failed",
            errors={"email": "Invalid format", "age": "Must be positive"},
        )
        
        assert error.errors == {"email": "Invalid format", "age": "Must be positive"}
        assert "email: Invalid format" in str(error)
        assert "age: Must be positive" in str(error)
    
    def test_restricted_error_message(self):
        """RestrictedError should have informative message."""
        from aksara.exceptions import RestrictedError
        
        error = RestrictedError(
            model_name="User",
            related_model="Post",
            related_count=5,
        )
        
        message = str(error)
        assert "User" in message
        assert "Post" in message
        assert "5" in message
        assert "RESTRICT" in message
    
    def test_unique_constraint_error_field(self):
        """UniqueConstraintError should identify field."""
        from aksara.exceptions import UniqueConstraintError
        
        error = UniqueConstraintError(
            field_name="email",
            value="test@example.com",
        )
        
        assert error.field_name == "email"
        assert "email" in str(error)
    
    def test_database_error_preserves_original(self):
        """DatabaseError should preserve original exception."""
        from aksara.exceptions import DatabaseError
        
        original = ValueError("Original error")
        error = DatabaseError(
            "Database operation failed",
            original_exception=original,
            query="SELECT * FROM users",
        )
        
        assert error.original_exception is original
        assert error.query == "SELECT * FROM users"


# =============================================================================
# Test QuerySet Edge Cases
# =============================================================================

class TestQuerySetEdgeCases:
    """Test QuerySet edge cases."""
    
    def test_empty_in_lookup_returns_false(self):
        """Empty __in lookup should match nothing."""
        from aksara import Model, fields
        from aksara.manager import QuerySet
        from aksara.registry import ModelRegistry
        
        ModelRegistry.clear()
        
        class User(Model):
            status = fields.String()
        
        qs = QuerySet(User).filter(status__in=[])
        where, values = qs._build_where_clause()
        
        assert "FALSE" in where
        assert values == []
        
        ModelRegistry.clear()
    
    def test_isnull_true_lookup(self):
        """__isnull=True should generate IS NULL."""
        from aksara import Model, fields
        from aksara.manager import QuerySet
        from aksara.registry import ModelRegistry
        
        ModelRegistry.clear()
        
        class Article(Model):
            author = fields.String(nullable=True)
        
        qs = QuerySet(Article).filter(author__isnull=True)
        where, values = qs._build_where_clause()
        
        assert "IS NULL" in where
        assert values == []
        
        ModelRegistry.clear()
    
    def test_isnull_false_lookup(self):
        """__isnull=False should generate IS NOT NULL."""
        from aksara import Model, fields
        from aksara.manager import QuerySet
        from aksara.registry import ModelRegistry
        
        ModelRegistry.clear()
        
        class Article(Model):
            author = fields.String(nullable=True)
        
        qs = QuerySet(Article).filter(author__isnull=False)
        where, values = qs._build_where_clause()
        
        assert "IS NOT NULL" in where
        assert values == []
        
        ModelRegistry.clear()
    
    def test_unknown_field_raises(self):
        """Unknown field in filter should raise ValueError."""
        from aksara import Model, fields
        from aksara.manager import QuerySet
        from aksara.registry import ModelRegistry
        
        ModelRegistry.clear()
        
        class Item(Model):
            name = fields.String()
        
        qs = QuerySet(Item).filter(nonexistent_field="value")
        
        with pytest.raises(ValueError, match="Unknown field"):
            qs._build_where_clause()
        
        ModelRegistry.clear()
    
    def test_filter_chaining_immutable(self):
        """Filter chaining should not mutate original QuerySet."""
        from aksara import Model, fields
        from aksara.manager import QuerySet
        from aksara.registry import ModelRegistry
        
        ModelRegistry.clear()
        
        class Item(Model):
            status = fields.String()
            priority = fields.Integer(default=0)
        
        qs1 = QuerySet(Item)
        qs2 = qs1.filter(status="active")
        qs3 = qs2.filter(priority__gte=5)
        
        # Original should be unchanged
        assert qs1._filters == {}
        assert qs2._filters == {"status": "active"}
        assert qs3._filters == {"status": "active", "priority__gte": 5}
        
        ModelRegistry.clear()


# =============================================================================
# Test Permission Edge Cases
# =============================================================================

class TestPermissionEdgeCases:
    """Test permission edge cases."""
    
    def test_permission_and_short_circuits(self):
        """AND permission should short-circuit on first failure."""
        from aksara.permissions import AND, BasePermission
        
        class AlwaysDeny(BasePermission):
            def has_permission(self, request, view=None):
                return False
        
        class NeverCalled(BasePermission):
            def has_permission(self, request, view=None):
                raise AssertionError("Should not be called")
        
        perm = AND(AlwaysDeny(), NeverCalled())
        request = MagicMock()
        
        # Should not raise, because AND short-circuits
        result = perm.has_permission(request)
        assert result is False
    
    def test_permission_or_short_circuits(self):
        """OR permission should short-circuit on first success."""
        from aksara.permissions import OR, BasePermission
        
        class AlwaysAllow(BasePermission):
            def has_permission(self, request, view=None):
                return True
        
        class NeverCalled(BasePermission):
            def has_permission(self, request, view=None):
                raise AssertionError("Should not be called")
        
        perm = OR(AlwaysAllow(), NeverCalled())
        request = MagicMock()
        
        # Should not raise, because OR short-circuits
        result = perm.has_permission(request)
        assert result is True
    
    def test_permission_ai_allow_aggregation(self):
        """ai_allow should aggregate correctly in compositions."""
        from aksara.permissions import AND, OR, AllowAny, DenyAI
        
        # AND: all must allow AI
        perm_and = AND(AllowAny(), DenyAI())
        assert perm_and.ai_allow is False  # DenyAI blocks
        
        # OR: any can allow AI
        perm_or = OR(AllowAny(), DenyAI())
        assert perm_or.ai_allow is True  # AllowAny allows


# =============================================================================
# Test Identity Edge Cases
# =============================================================================

class TestIdentityEdgeCases:
    """Test identity edge cases."""
    
    def test_anonymous_user_is_falsy(self):
        """AnonymousUser should be falsy."""
        from aksara.identity import AnonymousUser
        
        anon = AnonymousUser()
        assert not anon
        assert bool(anon) is False
    
    def test_anonymous_user_has_no_id(self):
        """AnonymousUser should have None id."""
        from aksara.identity import AnonymousUser
        
        anon = AnonymousUser()
        assert anon.id is None
    
    def test_anonymous_user_not_authenticated(self):
        """AnonymousUser should not be authenticated."""
        from aksara.identity import AnonymousUser
        
        anon = AnonymousUser()
        assert anon.is_authenticated is False
        assert anon.is_active is False
        assert anon.is_staff is False
        assert anon.is_superuser is False
    
    def test_anonymous_users_are_equal(self):
        """All AnonymousUser instances should be equal."""
        from aksara.identity import AnonymousUser
        
        a1 = AnonymousUser()
        a2 = AnonymousUser()
        
        assert a1 == a2
        assert hash(a1) == hash(a2)


# =============================================================================
# Test Middleware Context Isolation
# =============================================================================

class TestMiddlewareContextIsolation:
    """Test that context vars are properly isolated."""
    
    def test_context_vars_default_to_none(self):
        """Context vars should default to None outside request."""
        from aksara.middleware import request_id_var, tenant_id_var, user_id_var
        
        assert request_id_var.get() is None
        assert tenant_id_var.get() is None
        assert user_id_var.get() is None


# =============================================================================
# Test on_delete Constants Consistency
# =============================================================================

class TestOnDeleteConsistency:
    """Test on_delete constants are consistent."""
    
    def test_on_delete_values_match(self):
        """on_delete module-level and class constants should match."""
        from aksara.fields import CASCADE, SET_NULL, RESTRICT, PROTECT, OnDelete
        
        assert CASCADE == OnDelete.CASCADE
        assert SET_NULL == OnDelete.SET_NULL
        assert RESTRICT == OnDelete.RESTRICT
        assert PROTECT == OnDelete.PROTECT
    
    def test_protect_is_restrict_alias(self):
        """PROTECT should be an alias for RESTRICT."""
        from aksara.fields import PROTECT, RESTRICT
        
        assert PROTECT == RESTRICT


# =============================================================================
# Test Migration Graph Consistency
# =============================================================================

class TestMigrationGraphConsistency:
    """Test migration graph consistency."""
    
    def test_empty_graph_has_no_heads(self):
        """Empty graph should have no heads for any app."""
        from aksara.migrations.graph import MigrationGraph
        
        graph = MigrationGraph()
        assert graph.heads_for_app("nonexistent") == []
    
    def test_graph_len(self):
        """Graph len should count nodes."""
        from aksara.migrations.graph import MigrationGraph, MigrationNode
        
        graph = MigrationGraph()
        assert len(graph) == 0
        
        graph.add_node(MigrationNode(app_label="app", name="0001"))
        assert len(graph) == 1
        
        graph.add_node(MigrationNode(app_label="app", name="0002"))
        assert len(graph) == 2


# =============================================================================
# Test Settings Edge Cases
# =============================================================================

class TestSettingsEdgeCases:
    """Test settings edge cases."""
    
    def test_settings_has_debug_attribute(self):
        """Settings should have debug attribute."""
        from aksara.conf import Settings
        
        s = Settings()
        assert hasattr(s, 'debug')
        assert isinstance(s.debug, bool)
    
    def test_settings_has_database_url_attribute(self):
        """Settings should have database_url attribute."""
        from aksara.conf import Settings
        
        s = Settings()
        assert hasattr(s, 'database_url')


# =============================================================================
# Test Admin Site Consistency
# =============================================================================

class TestAdminSiteConsistency:
    """Test admin site registration consistency."""
    
    def test_register_model_unregister_and_reregister(self):
        """Unregistering and re-registering should work."""
        from aksara import Model, fields
        from aksara.contrib.admin import site
        from aksara.registry import ModelRegistry
        
        ModelRegistry.clear()
        site.clear()
        
        class TestModel(Model):
            name = fields.String()
        
        site.register(TestModel)
        assert site.is_registered(TestModel)
        
        site.unregister(TestModel)
        assert not site.is_registered(TestModel)
        
        # Should be able to re-register now
        site.register(TestModel)
        assert site.is_registered(TestModel)
        
        ModelRegistry.clear()
        site.clear()
    
    def test_get_app_list_empty(self):
        """get_app_list on empty site should return empty dict."""
        from aksara.contrib.admin import site
        
        site.clear()
        
        result = site.get_app_list()
        assert result == {} or len(result) == 0


# =============================================================================
# Test Serializer Edge Cases  
# =============================================================================

class TestSerializerEdgeCases:
    """Test serializer edge cases."""
    
    def test_serializer_with_all_fields(self):
        """Serializer with __all__ should include all fields."""
        from aksara import Model, fields
        from aksara.api import ModelSerializer
        from aksara.registry import ModelRegistry
        from aksara.api.serializers import clear_serializer_cache
        
        ModelRegistry.clear()
        clear_serializer_cache()
        
        class Person(Model):
            name = fields.String()
            age = fields.Integer(default=0)
            email = fields.Email(nullable=True)
        
        class PersonSerializer(ModelSerializer):
            class Meta:
                model = Person
                fields = "__all__"
        
        field_names = PersonSerializer._get_field_names()
        
        assert "id" in field_names
        assert "name" in field_names
        assert "age" in field_names
        assert "email" in field_names
        
        ModelRegistry.clear()
        clear_serializer_cache()
    
    def test_serializer_exclude_works(self):
        """Serializer exclude should remove fields."""
        from aksara import Model, fields
        from aksara.api import ModelSerializer
        from aksara.registry import ModelRegistry
        from aksara.api.serializers import clear_serializer_cache
        
        ModelRegistry.clear()
        clear_serializer_cache()
        
        class Item(Model):
            name = fields.String()
            secret = fields.String(nullable=True)
        
        class ItemSerializer(ModelSerializer):
            class Meta:
                model = Item
                fields = "__all__"
                exclude = ["secret"]
        
        field_names = ItemSerializer._get_field_names()
        
        assert "name" in field_names
        assert "secret" not in field_names
        
        ModelRegistry.clear()
        clear_serializer_cache()


# =============================================================================
# Test ViewSet Action Consistency
# =============================================================================

class TestViewSetActionConsistency:
    """Test ViewSet action decorator consistency."""
    
    def test_action_decorator_stores_metadata(self):
        """Action decorator should store metadata on function."""
        from aksara.api import action, get_action_metadata, is_action
        
        @action(detail=True, methods=["post"], summary="Test action")
        async def test_action(self, pk):
            pass
        
        assert is_action(test_action) is True
        
        metadata = get_action_metadata(test_action)
        assert metadata["detail"] is True
        assert "post" in [m.lower() for m in metadata["methods"]]
        assert metadata["summary"] == "Test action"
    
    def test_action_ai_exposed_default(self):
        """Action should be AI exposed by default."""
        from aksara.api import action, is_action_ai_exposed
        
        @action(detail=False, methods=["get"])
        async def exposed_action(self):
            pass
        
        assert is_action_ai_exposed(exposed_action) is True
    
    def test_action_ai_exposed_false(self):
        """Action can be hidden from AI."""
        from aksara.api import action, is_action_ai_exposed
        
        @action(detail=False, methods=["post"], ai_exposed=False)
        async def hidden_action(self):
            pass
        
        assert is_action_ai_exposed(hidden_action) is False
