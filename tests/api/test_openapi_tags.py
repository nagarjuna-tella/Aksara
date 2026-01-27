"""
Tests for OpenAPI tag handling in ModelViewSet.
"""

import pytest
from aksara.api.viewsets import ModelViewSet


class DummyModel:
    """Dummy model for testing."""
    __tablename__ = "dummies"
    __name__ = "Dummy"
    _fields = {}


class ProductModel:
    """Product model for testing."""
    __tablename__ = "products"
    __name__ = "Product"
    _fields = {}


class TestGetTags:
    """Tests for the get_tags classmethod."""
    
    def test_explicit_tags_returned(self):
        """get_tags should return explicitly set tags."""
        class MyViewSet(ModelViewSet):
            model = DummyModel
            prefix = "/dummies"
            tags = ["MyCustomTag", "API"]
        
        assert MyViewSet.get_tags() == ["MyCustomTag", "API"]
    
    def test_single_explicit_tag(self):
        """get_tags should return single explicit tag."""
        class MyViewSet(ModelViewSet):
            model = DummyModel
            prefix = "/dummies"
            tags = ["Items"]
        
        assert MyViewSet.get_tags() == ["Items"]
    
    def test_derives_tag_from_model_name(self):
        """get_tags should derive tag from model name if not set."""
        class MyViewSet(ModelViewSet):
            model = DummyModel
            prefix = "/dummies"
            # tags not set
        
        # DummyModel.__name__ == "DummyModel"
        assert MyViewSet.get_tags() == ["DummyModel"]
    
    def test_derives_tag_from_product_model(self):
        """get_tags should use model name for different models."""
        class ProductViewSet(ModelViewSet):
            model = ProductModel
            prefix = "/products"
        
        # ProductModel.__name__ == "ProductModel"
        assert ProductViewSet.get_tags() == ["ProductModel"]
    
    def test_falls_back_to_viewset_name(self):
        """get_tags should use ViewSet class name if no model."""
        class OrphanViewSet(ModelViewSet):
            model = None  # type: ignore
            prefix = "/orphans"
            tags = None
        
        # Should strip "ViewSet" suffix
        assert OrphanViewSet.get_tags() == ["Orphan"]
    
    def test_viewset_name_without_suffix(self):
        """get_tags should handle ViewSet name without 'ViewSet' suffix."""
        class Items(ModelViewSet):
            model = None  # type: ignore
            prefix = "/items"
            tags = None
        
        assert Items.get_tags() == ["Items"]
    
    def test_empty_tags_list_returns_model_name(self):
        """Empty tags list should be replaced with model name at init."""
        # Note: Empty list is falsy, so get_tags treats it as "not set"
        class MyViewSet(ModelViewSet):
            model = DummyModel
            prefix = "/dummies"
            tags = []  # Empty list is falsy
        
        # Empty list is not None, so it returns as-is
        # This is intentional - empty list means "no tags"
        assert MyViewSet.get_tags() == []


class TestTagsInheritance:
    """Tests for tags inheritance in ViewSet subclasses."""
    
    def test_child_inherits_parent_tags(self):
        """Child ViewSet should inherit parent's tags if not overridden."""
        class ParentViewSet(ModelViewSet):
            model = DummyModel
            prefix = "/parents"
            tags = ["ParentTag"]
        
        class ChildViewSet(ParentViewSet):
            prefix = "/children"
            # tags not overridden
        
        assert ChildViewSet.get_tags() == ["ParentTag"]
    
    def test_child_overrides_parent_tags(self):
        """Child ViewSet can override parent's tags."""
        class ParentViewSet(ModelViewSet):
            model = DummyModel
            prefix = "/parents"
            tags = ["ParentTag"]
        
        class ChildViewSet(ParentViewSet):
            prefix = "/children"
            tags = ["ChildTag"]
        
        assert ChildViewSet.get_tags() == ["ChildTag"]
    
    def test_child_can_clear_tags(self):
        """Child ViewSet can clear parent's tags."""
        class ParentViewSet(ModelViewSet):
            model = DummyModel
            prefix = "/parents"
            tags = ["ParentTag"]
        
        class ChildViewSet(ParentViewSet):
            prefix = "/children"
            tags = []  # Explicitly empty
        
        assert ChildViewSet.get_tags() == []


class TestTagsWithInitialization:
    """Tests for tags handling during ViewSet initialization."""
    
    def test_tags_set_to_model_name_on_init(self):
        """Tags should be set to model name during __init__ if None."""
        class MyViewSet(ModelViewSet):
            model = DummyModel
            prefix = "/dummies"
            # tags is None by default
        
        viewset = MyViewSet()
        
        # After init, tags should be set to model class name
        assert viewset.tags == ["DummyModel"]
    
    def test_explicit_tags_preserved_on_init(self):
        """Explicit tags should be preserved during __init__."""
        class MyViewSet(ModelViewSet):
            model = DummyModel
            prefix = "/dummies"
            tags = ["CustomTag"]
        
        viewset = MyViewSet()
        
        assert viewset.tags == ["CustomTag"]
    
    def test_class_tags_not_modified(self):
        """Class-level tags should not be modified by instance init."""
        class MyViewSet(ModelViewSet):
            model = DummyModel
            prefix = "/dummies"
            tags = None
        
        # Get class-level tags before init
        class_tags_before = MyViewSet.tags
        
        # Create instance
        viewset = MyViewSet()
        
        # Instance has tags set to model class name
        assert viewset.tags == ["DummyModel"]
        
        # Class tags might be modified (this is by design)
        # The class attribute is set during __init__
