"""
Admin Site

Central AdminSite class for managing model registrations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Type

if TYPE_CHECKING:
    from aksara.model.base import Model
    from aksara.contrib.admin.options import ModelAdmin


class AdminSite:
    """
    Central admin site managing model registrations.
    
    Provides model registration and lookup functionality for the admin interface.
    
    Usage:
        from aksara.contrib.admin import site, ModelAdmin
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
    ):
        """
        Register a model with the admin site.
        
        Can be used as a direct method call or as a decorator:
        
        Direct call (without custom admin):
            site.register(Book)
        
        Direct call (with custom admin):
            site.register(Book, BookAdmin)
        
        As a decorator:
            @site.register(Book)
            class BookAdmin(ModelAdmin):
                list_display = ["title", "author"]
        
        Args:
            model: The Model class to register
            admin_class: Optional ModelAdmin subclass for customization
            
        Returns:
            When used as a decorator, returns a function that accepts the admin class.
            When used directly, returns None.
            
        Raises:
            ValueError: If the model is already registered
        """
        from aksara.contrib.admin.options import ModelAdmin as DefaultModelAdmin
        
        def decorator(admin_cls: Type["ModelAdmin"]) -> Type["ModelAdmin"]:
            """Inner decorator that registers the admin class."""
            if model in self._registry:
                raise ValueError(f"Model {model.__name__} is already registered.")
            self._registry[model] = admin_cls(model, self)
            return admin_cls
        
        # If admin_class is provided, register directly
        if admin_class is not None:
            if model in self._registry:
                raise ValueError(f"Model {model.__name__} is already registered.")
            self._registry[model] = admin_class(model, self)
            return None
        
        # Check if this is likely decorator usage (model is actually _just_ a model reference)
        # Decorator usage: @site.register(MyModel) followed by class definition
        # Direct usage: site.register(MyModel) as a standalone call
        # 
        # The key insight is that when used as @decorator(arg), Python first calls
        # register(MyModel) which returns the decorator function, then Python calls
        # that decorator with the class being decorated.
        #
        # When used directly as site.register(MyModel), the return value is ignored,
        # but we still need to register the model with a default admin.
        #
        # Unfortunately, we can't distinguish between these at call time.
        # The solution is to return a decorator that ALSO registers with default
        # if not called as a decorator within a reasonable time.
        #
        # Simpler approach: always return a decorator, but if it's used directly,
        # it won't matter since the return value is ignored. For direct usage with
        # default admin, we need to register immediately.
        
        # Return a decorator that can be used with @syntax
        # BUT also register with default admin for direct-call usage compatibility
        if model in self._registry:
            raise ValueError(f"Model {model.__name__} is already registered.")
        
        # Register with default admin immediately (for direct call usage)
        self._registry[model] = DefaultModelAdmin(model, self)
        
        # Return decorator for @syntax usage (it will re-register, overwriting default)
        def decorating_register(admin_cls: Type["ModelAdmin"]) -> Type["ModelAdmin"]:
            """Re-register with the actual admin class when used as decorator."""
            self._registry[model] = admin_cls(model, self)
            return admin_cls
        
        return decorating_register
    
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
