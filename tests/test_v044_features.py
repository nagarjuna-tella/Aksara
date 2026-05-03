"""
Test v0.5.44 DX Features - Unit Tests

Unit tests for all new v0.5.44 enterprise DX features.
These tests verify that all new features are properly implemented and accessible.

v0.5.44 Features Tested:
1. DjangoFilterBackend (see test_v044_filter_backends.py)
2. Pagination backends (see test_v044_pagination.py)
3. Bulk operations (bulk_create, bulk_update)
4. Upsert operations
5. Soft deletes (SoftDeleteModel)
6. Fixture management (dump_data, load_data)
"""

import pytest
from aksara import Model, fields
from aksara.registry import ModelRegistry


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear registry before each test."""
    ModelRegistry._models.clear()
    yield
    ModelRegistry._models.clear()


# ─── Bulk Operations Tests ────────────────────────────────────────────────

class TestBulkOperationsAPI:
    """Test that bulk operations are available and properly exposed."""
    
    def test_bulk_create_exists(self):
        """Test bulk_create method exists on Manager."""
        class TestModel(Model):
            title = fields.String()
        
        assert hasattr(TestModel.objects.__class__, 'bulk_create')
    
    def test_bulk_update_exists(self):
        """Test bulk_update method exists on Manager."""
        class TestModel(Model):
            title = fields.String()
        
        assert hasattr(TestModel.objects.__class__, 'bulk_update')
    
    def test_bulk_create_callable(self):
        """Test bulk_create is callable."""
        class TestModel(Model):
            title = fields.String()
        
        assert callable(getattr(TestModel.objects.__class__, 'bulk_create'))
    
    def test_bulk_update_callable(self):
        """Test bulk_update is callable."""
        class TestModel(Model):
            title = fields.String()
        
        assert callable(getattr(TestModel.objects.__class__, 'bulk_update'))


# ─── Upsert Operations Tests ──────────────────────────────────────────────

class TestUpsertAPI:
    """Test that upsert operations are available."""
    
    def test_upsert_exists(self):
        """Test upsert method exists on Manager."""
        class TestModel(Model):
            title = fields.String()
        
        assert hasattr(TestModel.objects.__class__, 'upsert')
    
    def test_upsert_callable(self):
        """Test upsert is callable."""
        class TestModel(Model):
            title = fields.String()
        
        assert callable(getattr(TestModel.objects.__class__, 'upsert'))


# ─── Soft Delete Tests ────────────────────────────────────────────────────

class TestSoftDeleteAPI:
    """Test that soft delete features are available."""
    
    def test_soft_delete_model_import(self):
        """Test SoftDeleteModel can be imported."""
        from aksara.contrib.soft_delete import SoftDeleteModel
        assert SoftDeleteModel is not None
    
    def test_with_deleted_import(self):
        """Test with_deleted helper can be imported."""
        from aksara.contrib.soft_delete import with_deleted
        assert callable(with_deleted)
    
    def test_only_deleted_import(self):
        """Test only_deleted helper can be imported."""
        from aksara.contrib.soft_delete import only_deleted
        assert callable(only_deleted)
    
    def test_soft_delete_mixin_has_delete(self):
        """Test SoftDeleteModel mixin provides delete method."""
        from aksara.contrib.soft_delete import SoftDeleteModel
        
        # Create a test model with soft delete
        class User(SoftDeleteModel):
            email = fields.String(unique=True)
        
        # Should have delete method
        assert hasattr(User, 'delete')
    
    def test_soft_delete_mixin_has_undelete(self):
        """Test SoftDeleteModel mixin provides undelete method."""
        from aksara.contrib.soft_delete import SoftDeleteModel
        
        class User(SoftDeleteModel):
            email = fields.String(unique=True)
        
        # Should have undelete method
        assert hasattr(User, 'undelete')


# ─── Fixture Tests ────────────────────────────────────────────────────────

class TestFixturesAPI:
    """Test that fixture features are available."""
    
    def test_dump_data_import(self):
        """Test dump_data can be imported."""
        from aksara.fixtures import dump_data
        assert callable(dump_data)
    
    def test_load_data_import(self):
        """Test load_data can be imported."""
        from aksara.fixtures import load_data
        assert callable(load_data)
    
    def test_dump_database_import(self):
        """Test dump_database can be imported."""
        from aksara.fixtures import dump_database
        assert callable(dump_database)


# ─── Integration Tests ────────────────────────────────────────────────────

class TestPublicAPIExports:
    """Test that all new features are properly exported from main modules."""
    
    def test_soft_delete_in_main_export(self):
        """Test SoftDeleteModel is exported from aksara."""
        from aksara import SoftDeleteModel
        assert SoftDeleteModel is not None
    
    def test_fixtures_in_main_export(self):
        """Test fixture functions are exported from aksara."""
        from aksara import dump_data, load_data, dump_database
        assert dump_data is not None
        assert load_data is not None
        assert dump_database is not None
    
    def test_filter_backends_in_api_export(self):
        """Test filter backends are exported from aksara.api."""
        from aksara.api import DjangoFilterBackend
        assert DjangoFilterBackend is not None
    
    def test_pagination_in_api_export(self):
        """Test pagination classes are exported from aksara.api."""
        from aksara.api import PageNumberPagination, LimitOffsetPagination, CursorPagination
        assert PageNumberPagination is not None
        assert LimitOffsetPagination is not None
        assert CursorPagination is not None


# ─── Documentation Compliance Tests ────────────────────────────────────────

class TestDocumentationExamples:
    """Test that code examples in documentation are valid."""
    
    def test_django_filter_backend_example(self):
        """Test DjangoFilterBackend example code is valid."""
        from aksara.api import ModelViewSet, DjangoFilterBackend
        
        class TestModel(Model):
            status = fields.String()
            category = fields.String()
        
        class TestViewSet(ModelViewSet):
            model = TestModel
            filter_backends = [DjangoFilterBackend]
            filterable_fields = ['status', 'category']
        
        # Should construct without errors
        assert TestViewSet is not None
    
    def test_soft_delete_example(self):
        """Test soft delete example code is valid."""
        from aksara.contrib.soft_delete import SoftDeleteModel
        
        class User(SoftDeleteModel):
            email = fields.String(unique=True)
            name = fields.String()
        
        # Should construct without errors
        assert User is not None
        assert hasattr(User, 'delete')
        assert hasattr(User, 'undelete')
    
    def test_pagination_example(self):
        """Test pagination example code is valid."""
        from aksara.api import ModelViewSet, PageNumberPagination
        
        class TestModel(Model):
            title = fields.String()
        
        class TestViewSet(ModelViewSet):
            model = TestModel
            pagination_class = PageNumberPagination
        
        # Should construct without errors
        assert TestViewSet is not None


# ─── Feature Availability Tests ───────────────────────────────────────────

class Testv044Features:
    """Test all v0.5.44 features are available."""
    
    def test_category_1_features(self):
        """Test Category 1 (API & ViewSet DX) features are available."""
        from aksara.api import DjangoFilterBackend, SearchFilter, OrderingFilter
        from aksara.api import PageNumberPagination, LimitOffsetPagination, CursorPagination
        
        # All Category 1 features should be importable
        assert DjangoFilterBackend is not None
        assert SearchFilter is not None
        assert OrderingFilter is not None
        assert PageNumberPagination is not None
        assert LimitOffsetPagination is not None
        assert CursorPagination is not None
    
    def test_category_2_features(self):
        """Test Category 2 (Database & ORM DX) features are available."""
        from aksara import SoftDeleteModel
        from aksara.fixtures import dump_data, load_data, dump_database
        
        # All Category 2 features should be importable
        assert SoftDeleteModel is not None
        assert dump_data is not None
        assert load_data is not None
        assert dump_database is not None
    
    def test_signals_integration(self):
        """Test signals system is available (already integrated)."""
        from aksara.signals import pre_save, post_save, pre_delete, post_delete
        
        # All signal types should be available
        assert pre_save is not None
        assert post_save is not None
        assert pre_delete is not None
        assert post_delete is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
