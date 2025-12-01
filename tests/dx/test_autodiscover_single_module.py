"""
Tests for auto-discovery of ViewSets from a single module.
"""

import sys
import types
import pytest
from unittest.mock import patch, MagicMock

from vidyut.core.discovery import (
    discover_viewsets_from_module,
    import_module_safely,
    auto_discover_viewsets,
)
from vidyut.api.viewsets import ModelViewSet


class DummyModel:
    """Dummy model for testing."""
    __tablename__ = "dummies"
    __name__ = "Dummy"
    _fields = {}


class DummyViewSet(ModelViewSet):
    """A valid ViewSet for testing."""
    model = DummyModel
    prefix = "/dummies"


class AnotherViewSet(ModelViewSet):
    """Another valid ViewSet for testing."""
    model = DummyModel
    prefix = "/others"


class NotAViewSet:
    """A class that is not a ViewSet."""
    pass


class AbstractViewSet(ModelViewSet):
    """An abstract ViewSet without a model (should be ignored)."""
    pass


class TestDiscoverViewsetsFromModule:
    """Tests for discover_viewsets_from_module function."""
    
    def test_discovers_viewsets(self):
        """Should discover ViewSet classes from a module."""
        # Create a fake module
        fake_module = types.ModuleType("fake_views")
        fake_module.DummyViewSet = DummyViewSet
        fake_module.AnotherViewSet = AnotherViewSet
        
        viewsets = discover_viewsets_from_module(fake_module)
        
        assert len(viewsets) == 2
        assert DummyViewSet in viewsets
        assert AnotherViewSet in viewsets
    
    def test_ignores_non_viewsets(self):
        """Should ignore classes that aren't ViewSets."""
        fake_module = types.ModuleType("fake_views")
        fake_module.DummyViewSet = DummyViewSet
        fake_module.NotAViewSet = NotAViewSet
        fake_module.some_function = lambda: None
        fake_module.SOME_CONSTANT = "value"
        
        viewsets = discover_viewsets_from_module(fake_module)
        
        assert len(viewsets) == 1
        assert DummyViewSet in viewsets
        assert NotAViewSet not in viewsets
    
    def test_ignores_abstract_viewsets(self):
        """Should ignore ViewSets without a model (abstract)."""
        fake_module = types.ModuleType("fake_views")
        fake_module.DummyViewSet = DummyViewSet
        fake_module.AbstractViewSet = AbstractViewSet
        
        viewsets = discover_viewsets_from_module(fake_module)
        
        assert len(viewsets) == 1
        assert DummyViewSet in viewsets
        assert AbstractViewSet not in viewsets
    
    def test_ignores_base_modelviewset(self):
        """Should ignore the base ModelViewSet class."""
        fake_module = types.ModuleType("fake_views")
        fake_module.DummyViewSet = DummyViewSet
        fake_module.ModelViewSet = ModelViewSet  # Imported in module
        
        viewsets = discover_viewsets_from_module(fake_module)
        
        # Should only find DummyViewSet, not ModelViewSet itself
        assert len(viewsets) == 1
        assert DummyViewSet in viewsets
        assert ModelViewSet not in viewsets
    
    def test_empty_module(self):
        """Should return empty list for module with no ViewSets."""
        fake_module = types.ModuleType("empty_module")
        fake_module.some_var = "value"
        
        viewsets = discover_viewsets_from_module(fake_module)
        
        assert viewsets == []


class TestImportModuleSafely:
    """Tests for import_module_safely function."""
    
    def test_imports_existing_module(self):
        """Should import an existing module."""
        module = import_module_safely("os")
        assert module is not None
        assert hasattr(module, "path")
    
    def test_returns_none_for_missing_module(self):
        """Should return None for non-existent module."""
        module = import_module_safely("nonexistent.module.path")
        assert module is None
    
    def test_returns_none_for_invalid_syntax(self):
        """Should return None for import errors."""
        # This module path syntax is valid but unlikely to exist
        module = import_module_safely("..invalid..path")
        assert module is None


class TestAutoDiscoverViewsets:
    """Tests for auto_discover_viewsets function."""
    
    def test_discovers_from_single_module(self):
        """Should discover from a specified views_module."""
        fake_module = types.ModuleType("myapp.views")
        fake_module.DummyViewSet = DummyViewSet
        
        with patch.dict(sys.modules, {"myapp.views": fake_module}):
            with patch("vidyut.core.discovery.import_module_safely", return_value=fake_module):
                viewsets = auto_discover_viewsets(views_module="myapp.views")
        
        assert len(viewsets) == 1
        assert DummyViewSet in viewsets
    
    def test_discovers_from_settings_apps(self):
        """Should discover from settings.apps when no views_module."""
        fake_views_1 = types.ModuleType("blog.views")
        fake_views_1.DummyViewSet = DummyViewSet
        
        fake_views_2 = types.ModuleType("users.views")
        fake_views_2.AnotherViewSet = AnotherViewSet
        
        def mock_import(path):
            if path == "blog.views":
                return fake_views_1
            elif path == "users.views":
                return fake_views_2
            return None
        
        with patch("vidyut.core.discovery.import_module_safely", side_effect=mock_import):
            with patch("vidyut.conf.settings") as mock_settings:
                mock_settings.apps = ["blog", "users"]
                viewsets = auto_discover_viewsets()
        
        assert len(viewsets) == 2
        assert DummyViewSet in viewsets
        assert AnotherViewSet in viewsets
    
    def test_handles_missing_views_module_gracefully(self):
        """Should skip apps without views.py."""
        fake_views = types.ModuleType("blog.views")
        fake_views.DummyViewSet = DummyViewSet
        
        def mock_import(path):
            if path == "blog.views":
                return fake_views
            # users.views doesn't exist
            return None
        
        with patch("vidyut.core.discovery.import_module_safely", side_effect=mock_import):
            with patch("vidyut.conf.settings") as mock_settings:
                mock_settings.apps = ["blog", "users"]
                viewsets = auto_discover_viewsets()
        
        # Should only find from blog, users.views is missing
        assert len(viewsets) == 1
        assert DummyViewSet in viewsets
    
    def test_empty_apps_returns_empty_list(self):
        """Should return empty list when no apps configured."""
        with patch("vidyut.conf.settings") as mock_settings:
            mock_settings.apps = []
            viewsets = auto_discover_viewsets()
        
        assert viewsets == []
    
    def test_deduplicates_viewsets(self):
        """Should not return duplicate ViewSets."""
        fake_views = types.ModuleType("app.views")
        fake_views.DummyViewSet = DummyViewSet
        fake_views.DuplicateDummyViewSet = DummyViewSet  # Same class, different name
        
        with patch("vidyut.core.discovery.import_module_safely", return_value=fake_views):
            viewsets = auto_discover_viewsets(views_module="app.views")
        
        # Should have unique classes only - same class with different names should be deduplicated
        assert len(viewsets) == 1
        assert DummyViewSet in viewsets
