"""
Tests for QuerySet.order_by() functionality.

Vidyut 0.3.20 - ORM Polish: Ordering API
"""

import pytest
from datetime import datetime, timedelta
from vidyut import Model, fields, ConfigurationError
from vidyut.manager import QuerySet, Manager


# =============================================================================
# Test Models
# =============================================================================

class OrderTestUser(Model):
    """Test model for ordering tests."""
    email = fields.Email(unique=True)
    name = fields.String(max_length=100)
    is_active = fields.Boolean(default=True)
    age = fields.Integer(default=0)
    
    class Meta:
        table_name = "order_test_users"


class OrderTestPost(Model):
    """Test model with ForeignKey for relation ordering tests."""
    title = fields.String(max_length=200)
    content = fields.Text(default="")
    author = fields.ForeignKey(OrderTestUser, on_delete="CASCADE")
    priority = fields.Integer(default=0)
    
    class Meta:
        table_name = "order_test_posts"


# =============================================================================
# Basic Ordering Tests
# =============================================================================

class TestOrderByBasic:
    """Tests for basic order_by() functionality."""
    
    def test_order_by_single_field_ascending(self):
        """order_by('field') should set ascending order."""
        qs = QuerySet(OrderTestUser).order_by("email")
        assert qs._order_by == ["email"]
    
    def test_order_by_single_field_descending(self):
        """order_by('-field') should set descending order."""
        qs = QuerySet(OrderTestUser).order_by("-email")
        assert qs._order_by == ["-email"]
    
    def test_order_by_multiple_fields(self):
        """order_by('field1', 'field2') should set multiple fields."""
        qs = QuerySet(OrderTestUser).order_by("is_active", "-email")
        assert qs._order_by == ["is_active", "-email"]
    
    def test_order_by_returns_new_queryset(self):
        """order_by() should return a new QuerySet (immutability)."""
        qs1 = QuerySet(OrderTestUser)
        qs2 = qs1.order_by("email")
        
        assert qs1 is not qs2
        assert qs1._order_by is None
        assert qs2._order_by == ["email"]
    
    def test_order_by_replaces_previous(self):
        """Chained order_by() calls should replace previous ordering."""
        qs = (
            QuerySet(OrderTestUser)
            .order_by("email")
            .order_by("-name")
        )
        assert qs._order_by == ["-name"]
    
    def test_order_by_id_field(self):
        """order_by('id') should work (id is always present)."""
        qs = QuerySet(OrderTestUser).order_by("id")
        assert qs._order_by == ["id"]
    
    def test_order_by_id_descending(self):
        """order_by('-id') should work."""
        qs = QuerySet(OrderTestUser).order_by("-id")
        assert qs._order_by == ["-id"]
    
    def test_order_by_created_at(self):
        """order_by('created_at') should work (auto field)."""
        qs = QuerySet(OrderTestUser).order_by("created_at")
        assert qs._order_by == ["created_at"]
    
    def test_order_by_updated_at(self):
        """order_by('-updated_at') should work (auto field)."""
        qs = QuerySet(OrderTestUser).order_by("-updated_at")
        assert qs._order_by == ["-updated_at"]


# =============================================================================
# Manager Integration Tests
# =============================================================================

class TestManagerOrderBy:
    """Tests for Manager.order_by() entry point."""
    
    def test_manager_order_by(self):
        """Manager.order_by() should create QuerySet with ordering."""
        manager = Manager(OrderTestUser)
        qs = manager.order_by("email")
        
        assert isinstance(qs, QuerySet)
        assert qs._order_by == ["email"]
    
    def test_manager_order_by_multiple_fields(self):
        """Manager.order_by() with multiple fields."""
        manager = Manager(OrderTestUser)
        qs = manager.order_by("is_active", "-name", "email")
        
        assert qs._order_by == ["is_active", "-name", "email"]


# =============================================================================
# Chaining Tests
# =============================================================================

class TestOrderByChaining:
    """Tests for order_by() chaining with other QuerySet methods."""
    
    def test_filter_then_order_by(self):
        """filter().order_by() should preserve both."""
        qs = (
            QuerySet(OrderTestUser)
            .filter(is_active=True)
            .order_by("email")
        )
        
        assert qs._filters == {"is_active": True}
        assert qs._order_by == ["email"]
    
    def test_order_by_then_filter(self):
        """order_by().filter() should preserve both."""
        qs = (
            QuerySet(OrderTestUser)
            .order_by("-created_at")
            .filter(is_active=True)
        )
        
        assert qs._filters == {"is_active": True}
        assert qs._order_by == ["-created_at"]
    
    def test_filter_order_by_filter(self):
        """filter().order_by().filter() should accumulate filters."""
        qs = (
            QuerySet(OrderTestUser)
            .filter(is_active=True)
            .order_by("email")
            .filter(age__gte=18)
        )
        
        assert qs._filters == {"is_active": True, "age__gte": 18}
        assert qs._order_by == ["email"]
    
    def test_order_by_with_select_related(self):
        """order_by() should work with select_related()."""
        qs = (
            QuerySet(OrderTestPost)
            .order_by("-priority")
            .select_related("author")
        )
        
        assert qs._order_by == ["-priority"]
        assert "author" in qs._select_related
    
    def test_select_related_then_order_by(self):
        """select_related().order_by() should preserve both."""
        qs = (
            QuerySet(OrderTestPost)
            .select_related("author")
            .order_by("title")
        )
        
        assert "author" in qs._select_related
        assert qs._order_by == ["title"]


# =============================================================================
# SQL Generation Tests
# =============================================================================

class TestOrderBySQLGeneration:
    """Tests for ORDER BY SQL clause generation."""
    
    def test_build_order_by_clause_ascending(self):
        """_build_order_by_clause should generate ASC for normal fields."""
        qs = QuerySet(OrderTestUser).order_by("email")
        clause = qs._build_order_by_clause()
        
        assert clause == "ORDER BY email ASC"
    
    def test_build_order_by_clause_descending(self):
        """_build_order_by_clause should generate DESC for - prefix."""
        qs = QuerySet(OrderTestUser).order_by("-email")
        clause = qs._build_order_by_clause()
        
        assert clause == "ORDER BY email DESC"
    
    def test_build_order_by_clause_multiple(self):
        """_build_order_by_clause with multiple fields."""
        qs = QuerySet(OrderTestUser).order_by("is_active", "-email", "name")
        clause = qs._build_order_by_clause()
        
        assert clause == "ORDER BY is_active ASC, email DESC, name ASC"
    
    def test_build_order_by_clause_empty(self):
        """_build_order_by_clause should return empty string when no ordering."""
        qs = QuerySet(OrderTestUser)
        clause = qs._build_order_by_clause()
        
        assert clause == ""
    
    def test_build_order_by_clause_id(self):
        """_build_order_by_clause should handle id field."""
        qs = QuerySet(OrderTestUser).order_by("-id")
        clause = qs._build_order_by_clause()
        
        assert clause == "ORDER BY id DESC"


# =============================================================================
# Error Cases
# =============================================================================

class TestOrderByErrors:
    """Tests for order_by() error handling."""
    
    def test_order_by_no_arguments_raises(self):
        """order_by() with no arguments should raise ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            QuerySet(OrderTestUser).order_by()
        
        assert "requires at least one field" in str(exc_info.value)
    
    def test_order_by_unknown_field_raises(self):
        """order_by() with unknown field should raise ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            QuerySet(OrderTestUser).order_by("not_a_field")
        
        assert "does not exist" in str(exc_info.value)
        assert "OrderTestUser" in str(exc_info.value)
    
    def test_order_by_unknown_field_shows_available(self):
        """Error message should include available fields."""
        with pytest.raises(ConfigurationError) as exc_info:
            QuerySet(OrderTestUser).order_by("xyz")
        
        error_msg = str(exc_info.value)
        assert "Available fields:" in error_msg
        assert "email" in error_msg
    
    def test_order_by_double_minus_raises(self):
        """order_by('--field') should raise ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            QuerySet(OrderTestUser).order_by("--email")
        
        assert "Invalid order_by field" in str(exc_info.value)
    
    def test_order_by_empty_string_raises(self):
        """order_by('') should raise ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            QuerySet(OrderTestUser).order_by("")
        
        assert "requires at least one field" in str(exc_info.value) or "cannot be empty" in str(exc_info.value)
    
    def test_order_by_just_minus_raises(self):
        """order_by('-') should raise ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            QuerySet(OrderTestUser).order_by("-")
        
        assert "cannot be empty" in str(exc_info.value)
    
    def test_order_by_non_string_raises(self):
        """order_by(123) should raise ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            QuerySet(OrderTestUser).order_by(123)  # type: ignore
        
        assert "must be strings" in str(exc_info.value)
    
    def test_order_by_descending_unknown_field(self):
        """order_by('-unknown') should raise with correct field name."""
        with pytest.raises(ConfigurationError) as exc_info:
            QuerySet(OrderTestUser).order_by("-unknown")
        
        assert "unknown" in str(exc_info.value)
        assert "does not exist" in str(exc_info.value)


# =============================================================================
# ForeignKey Ordering Tests
# =============================================================================

class TestOrderByForeignKey:
    """Tests for ordering by ForeignKey fields."""
    
    def test_order_by_fk_id_field(self):
        """order_by('author_id') should work for FK field."""
        qs = QuerySet(OrderTestPost).order_by("author_id")
        assert qs._order_by == ["author_id"]
    
    def test_order_by_fk_id_descending(self):
        """order_by('-author_id') should work."""
        qs = QuerySet(OrderTestPost).order_by("-author_id")
        assert qs._order_by == ["-author_id"]
    
    def test_order_by_fk_field_without_id_suffix(self):
        """order_by('author') should also work (maps to author_id)."""
        # This may raise or work depending on implementation
        # Based on our code, it should work as we check for fk_field_name
        qs = QuerySet(OrderTestPost).order_by("author")
        assert qs._order_by == ["author"]


# =============================================================================
# Edge Cases
# =============================================================================

class TestOrderByEdgeCases:
    """Tests for edge cases in order_by()."""
    
    def test_order_by_duplicate_fields(self):
        """order_by('field', 'field') - redundant but allowed."""
        qs = QuerySet(OrderTestUser).order_by("email", "email")
        assert qs._order_by == ["email", "email"]
    
    def test_order_by_same_field_different_directions(self):
        """order_by('field', '-field') - contradictory but allowed."""
        qs = QuerySet(OrderTestUser).order_by("email", "-email")
        assert qs._order_by == ["email", "-email"]
    
    def test_order_by_preserves_filters_on_chain(self):
        """Multiple chained operations preserve all state."""
        qs = (
            QuerySet(OrderTestUser)
            .filter(is_active=True)
            .order_by("email")
            .order_by("-name")
            .filter(age__gt=18)
        )
        
        assert qs._filters == {"is_active": True, "age__gt": 18}
        assert qs._order_by == ["-name"]  # Last order_by wins
    
    def test_queryset_immutability_on_error(self):
        """Failed order_by should not modify original QuerySet."""
        qs1 = QuerySet(OrderTestUser).filter(is_active=True)
        
        with pytest.raises(ConfigurationError):
            qs1.order_by("invalid_field")
        
        # Original should be unchanged
        assert qs1._order_by is None
        assert qs1._filters == {"is_active": True}


# =============================================================================
# Integration with all() / first()
# =============================================================================

class TestOrderByQueryExecution:
    """Tests for order_by integration with query execution methods."""
    
    def test_order_by_all_includes_order(self):
        """Verify order_by is included when calling all()."""
        qs = QuerySet(OrderTestUser).order_by("email", "-created_at")
        
        # Check internal state before execution
        assert qs._order_by == ["email", "-created_at"]
        
        # Build the order clause
        clause = qs._build_order_by_clause()
        assert "ORDER BY" in clause
        assert "email ASC" in clause
        assert "created_at DESC" in clause
    
    def test_order_by_first_includes_order(self):
        """Verify order_by is included when calling first()."""
        qs = QuerySet(OrderTestUser).order_by("-id")
        
        assert qs._order_by == ["-id"]
        clause = qs._build_order_by_clause()
        assert clause == "ORDER BY id DESC"
    
    def test_filter_and_order_by_for_first(self):
        """filter().order_by().first() should have correct SQL structure."""
        qs = (
            QuerySet(OrderTestUser)
            .filter(is_active=True)
            .order_by("-created_at")
        )
        
        where_clause, _ = qs._build_where_clause()
        order_clause = qs._build_order_by_clause()
        
        assert "WHERE" in where_clause
        assert "ORDER BY" in order_clause
        assert "created_at DESC" in order_clause


# =============================================================================
# Column Name Mapping Tests  
# =============================================================================

class TestOrderByColumnMapping:
    """Tests for field name to column name mapping in ORDER BY."""
    
    def test_order_by_maps_field_to_column(self):
        """order_by should use the actual column name from field metadata."""
        qs = QuerySet(OrderTestUser).order_by("email")
        clause = qs._build_order_by_clause()
        
        # email field's column_name should be used
        assert "email" in clause
        assert "ASC" in clause
    
    def test_order_by_fk_uses_column_name(self):
        """order_by FK field should use the _id column name."""
        qs = QuerySet(OrderTestPost).order_by("author_id")
        clause = qs._build_order_by_clause()
        
        # author_id field's actual column should be used
        assert "author_id" in clause


# =============================================================================
# Comprehensive Chaining Test
# =============================================================================

class TestOrderByComprehensiveChaining:
    """Comprehensive tests for complex chaining scenarios."""
    
    def test_full_chain_filter_order_select(self):
        """Full chain: filter -> order_by -> select_related."""
        qs = (
            QuerySet(OrderTestPost)
            .filter(priority__gte=5)
            .order_by("-priority", "title")
            .select_related("author")
        )
        
        assert qs._filters == {"priority__gte": 5}
        assert qs._order_by == ["-priority", "title"]
        assert "author" in qs._select_related
    
    def test_manager_full_chain(self):
        """Manager entry point with full chain."""
        manager = Manager(OrderTestUser)
        qs = (
            manager
            .filter(is_active=True)
            .order_by("email")
            .filter(age__gte=18)
        )
        
        assert qs._filters == {"is_active": True, "age__gte": 18}
        assert qs._order_by == ["email"]
    
    def test_manager_order_by_then_filter(self):
        """Manager.order_by() then filter()."""
        manager = Manager(OrderTestUser)
        qs = (
            manager
            .order_by("-created_at")
            .filter(is_active=True)
        )
        
        assert qs._filters == {"is_active": True}
        assert qs._order_by == ["-created_at"]
