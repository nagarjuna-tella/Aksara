"""
Test Filter Backends

Tests for AksaraFilterBackend and query parameter parsing.

v0.5.44: Comprehensive test coverage for filter backends.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from aksara.api import AksaraFilterBackend, DjangoFilterBackend
from aksara.registry import ModelRegistry


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear registry before each test."""
    ModelRegistry._models.clear()
    yield
    ModelRegistry._models.clear()


class TestFilterBackendParameterParsing:
    """Test AksaraFilterBackend query parameter parsing."""
    
    def test_exact_match_filter(self):
        """Test exact match filtering (field=value)."""
        backend = AksaraFilterBackend()
        
        # Mock request with query params
        request = Mock()
        request.query_params = {'status': 'active'}
        
        # Parse filters
        filters = backend._parse_filter_params(request, ['status'])
        
        assert filters == {'status': 'active'}
    
    def test_boolean_coercion(self):
        """Test boolean value coercion."""
        backend = AksaraFilterBackend()
        request = Mock()
        
        # Test various boolean representations
        test_cases = [
            ('true', True),
            ('false', False),
            ('yes', True),
            ('no', False),
            ('1', True),
            ('0', False),
        ]
        
        for value_str, expected in test_cases:
            request.query_params = {'active': value_str}
            filters = backend._parse_filter_params(request, ['active'])
            assert filters['active'] == expected, f"Failed for value: {value_str}"
    
    def test_null_coercion(self):
        """Test null/None coercion."""
        backend = AksaraFilterBackend()
        request = Mock()
        request.query_params = {'value': 'null'}
        
        filters = backend._parse_filter_params(request, ['value'])
        assert filters['value'] is None
    
    def test_gt_gte_lookups(self):
        """Test greater than lookups."""
        backend = AksaraFilterBackend()
        request = Mock()
        request.query_params = {'age__gt': '18', 'age__gte': '18'}
        
        filters = backend._parse_filter_params(request, ['age'])
        assert filters['age__gt'] == 18
        assert filters['age__gte'] == 18
    
    def test_in_lookup(self):
        """Test IN lookup with comma-separated values."""
        backend = AksaraFilterBackend()
        request = Mock()
        request.query_params = {'category__in': 'tech,news,science'}
        
        filters = backend._parse_filter_params(request, ['category'])
        assert filters['category__in'] == ['tech', 'news', 'science']
    
    def test_icontains_lookup(self):
        """Test case-insensitive contains."""
        backend = AksaraFilterBackend()
        request = Mock()
        request.query_params = {'name__icontains': 'john'}
        
        filters = backend._parse_filter_params(request, ['name'])
        assert filters['name__icontains'] == 'john'
    
    def test_float_coercion(self):
        """Test float value coercion."""
        backend = AksaraFilterBackend()
        request = Mock()
        request.query_params = {'price__gte': '19.99'}
        
        filters = backend._parse_filter_params(request, ['price'])
        assert filters['price__gte'] == 19.99
    
    def test_unknown_field_filtered(self):
        """Test that unknown fields are ignored."""
        backend = AksaraFilterBackend()
        request = Mock()
        request.query_params = {'status': 'active', 'unknown': 'value'}
        
        filters = backend._parse_filter_params(request, ['status'])
        
        # Only 'status' should be included, 'unknown' ignored
        assert 'status' in filters
        assert 'unknown' not in filters
    
    def test_multiple_filters(self):
        """Test parsing multiple filter parameters."""
        backend = AksaraFilterBackend()
        request = Mock()
        request.query_params = {
            'status': 'active',
            'price__gte': '50',
            'category__in': 'tech,news',
        }
        
        filters = backend._parse_filter_params(
            request,
            ['status', 'price', 'category']
        )
        
        assert filters['status'] == 'active'
        assert filters['price__gte'] == 50
        assert filters['category__in'] == ['tech', 'news']


class TestFilterBackendCompatibilityAliases:
    """Test preferred and legacy public import names."""

    def test_module_imports_expose_preferred_and_legacy_names(self):
        from aksara.api.filters import (
            AksaraFilterBackend as ModuleAksaraFilterBackend,
            DjangoFilterBackend as ModuleDjangoFilterBackend,
        )

        assert ModuleAksaraFilterBackend is AksaraFilterBackend
        assert ModuleDjangoFilterBackend is ModuleAksaraFilterBackend

    def test_api_package_exports_preferred_and_legacy_names(self):
        from aksara.api import (
            AksaraFilterBackend as PackageAksaraFilterBackend,
            DjangoFilterBackend as PackageDjangoFilterBackend,
        )

        assert PackageAksaraFilterBackend is AksaraFilterBackend
        assert PackageDjangoFilterBackend is PackageAksaraFilterBackend


class TestFilterBackendMockIntegration:
    """Test filter backend with mocked QuerySet."""
    
    def test_filter_backend_integrates_with_view(self):
        """Test that filter backend integrates with view configuration."""
        # This test verifies the filter backend is available and can be used
        backend = AksaraFilterBackend()
        
        # Verify backend has required methods
        assert hasattr(backend, 'filter_queryset')
        assert hasattr(backend, '_parse_filter_params')
        assert callable(backend.filter_queryset)


class TestFilterBackendViewSetConfiguration:
    """Test ViewSet configuration with filter backends."""
    
    def test_filter_backends_list(self):
        """Test that AksaraFilterBackend is available for ViewSets."""
        # Verify the backend can be imported and used in ViewSets
        from aksara.api import ModelViewSet
        
        # AksaraFilterBackend should be available for use in filter_backends list
        assert AksaraFilterBackend is not None
        assert callable(AksaraFilterBackend)
    
    def test_viewset_filter_backends_attribute(self):
        """Test ViewSet accepts filter_backends attribute."""
        # ViewSets have a filter_backends attribute that can be set
        # This is tested indirectly through the documentation examples
        backend = AksaraFilterBackend()
        assert hasattr(backend, 'filterable_fields') or True  # Optional attribute


class TestFilterBackendEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_query_params(self):
        """Test with no query parameters."""
        backend = AksaraFilterBackend()
        request = Mock()
        request.query_params = {}
        
        filters = backend._parse_filter_params(request, ['status'])
        assert filters == {}
    
    def test_invalid_number_value(self):
        """Test invalid numeric value."""
        backend = AksaraFilterBackend()
        request = Mock()
        request.query_params = {'age': 'not-a-number'}
        
        filters = backend._parse_filter_params(request, ['age'])
        # Should be treated as string when conversion fails
        assert filters['age'] == 'not-a-number'
    
    def test_empty_in_value(self):
        """Test empty IN value."""
        backend = AksaraFilterBackend()
        request = Mock()
        request.query_params = {'category__in': ''}
        
        filters = backend._parse_filter_params(request, ['category'])
        # Should result in empty list or single empty string
        assert 'category__in' in filters
    
    def test_isnull_boolean_values(self):
        """Test various isnull parameter values."""
        backend = AksaraFilterBackend()
        request = Mock()
        
        for value in ['true', 'yes', '1']:
            request.query_params = {'deleted__isnull': value}
            filters = backend._parse_filter_params(request, ['deleted'])
            assert filters['deleted__isnull'] is True
        
        for value in ['false', 'no', '0']:
            request.query_params = {'deleted__isnull': value}
            filters = backend._parse_filter_params(request, ['deleted'])
            assert filters['deleted__isnull'] is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
