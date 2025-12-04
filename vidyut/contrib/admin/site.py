"""
Admin Site

Central AdminSite class for managing model registrations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Type

if TYPE_CHECKING:
    from vidyut.model.base import Model
    from vidyut.contrib.admin.options import ModelAdmin


class AdminSite:
    """
    Central admin site managing model registrations.
    
    Provides model registration and lookup functionality for the admin interface.
    
    Usage:
        from vidyut.contrib.admin import site, ModelAdmin
        from myapp.models import Article
        
        # Simple registration
        site.register(Article)
        
        # Custom admin class
        class ArticleAdmin(ModelAdmin):
            list_display = ["title", "author", "created_at"]
            search_fields = ["title", "body"]
        
        site.register(Article, ArticleAdmin)
    """
    
    def __init__(self, name: str = "admin"):
        """
        Initialize the admin site.
        
        Args:
            name: Name identifier for this admin site (default: "admin")
        """
        self.name = name
        self._registry: Dict[Type["Model"], "ModelAdmin"] = {}
    
    def register(
        self,
        model: Type["Model"],
        admin_class: Optional[Type["ModelAdmin"]] = None,
    ) -> None:
        """
        Register a model with the admin site.
        
        Args:
            model: The Model class to register
            admin_class: Optional ModelAdmin subclass for customization
            
        Raises:
            ValueError: If the model is already registered
            
        Example:
            from vidyut.contrib.admin import site, ModelAdmin
            
            class BookAdmin(ModelAdmin):
                list_display = ["title", "author"]
            
            site.register(Book, BookAdmin)
        """
        from vidyut.contrib.admin.options import ModelAdmin as DefaultModelAdmin
        
        if admin_class is None:
            admin_class = DefaultModelAdmin
        
        if model in self._registry:
            raise ValueError(f"Model {model.__name__} is already registered.")
        
        self._registry[model] = admin_class(model, self)
    
    def unregister(self, model: Type["Model"]) -> None:
        """
        Unregister a model from the admin site.
        
        Args:
            model: The Model class to unregister
        """
        self._registry.pop(model, None)
    
    def is_registered(self, model: Type["Model"]) -> bool:
        """
        Check if a model is registered.
        
        Args:
            model: The Model class to check
            
        Returns:
            True if the model is registered
        """
        return model in self._registry
    
    @property
    def registry(self) -> Dict[Type["Model"], "ModelAdmin"]:
        """
        Get the model registry.
        
        Returns:
            Dictionary mapping Model classes to ModelAdmin instances
        """
        return self._registry
    
    def get_model_admin(self, model: Type["Model"]) -> Optional["ModelAdmin"]:
        """
        Get the ModelAdmin for a registered model.
        
        Args:
            model: The Model class to look up
            
        Returns:
            The ModelAdmin instance or None if not registered
        """
        return self._registry.get(model)
    
    def get_model_by_name(
        self,
        app_label: str,
        model_name: str,
    ) -> Optional[Type["Model"]]:
        """
        Look up a registered model by app_label and model name.
        
        Args:
            app_label: The app_label (from Model.meta.app_label)
            model_name: The model class name (case-insensitive)
            
        Returns:
            The Model class or None if not found
        """
        model_name_lower = model_name.lower()
        
        for model in self._registry:
            model_app_label = model.meta.app_label or "default"
            if model_app_label == app_label and model.__name__.lower() == model_name_lower:
                return model
        
        return None
    
    def get_app_list(self) -> Dict[str, list]:
        """
        Get models grouped by app_label.
        
        Returns:
            Dictionary mapping app_label to list of Model classes
        """
        apps: Dict[str, list] = {}
        
        for model in self._registry:
            app_label = model.meta.app_label or "default"
            apps.setdefault(app_label, []).append(model)
        
        return apps
    
    def clear(self) -> None:
        """
        Clear all registered models.
        
        Useful for testing.
        """
        self._registry.clear()
