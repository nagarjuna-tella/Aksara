"""
Model Registry

Stores all discovered model classes for migrations and introspection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Type

if TYPE_CHECKING:
    from vidyut.model.base import Model


class ModelRegistry:
    """
    Registry to store all discovered model classes.
    
    Models are automatically registered when their class is created
    via the ModelMeta metaclass.
    """
    
    _models: Dict[str, Type["Model"]] = {}
    
    @classmethod
    def register(cls, model: Type["Model"]) -> None:
        """
        Register a model class.
        
        Args:
            model: The model class to register
        """
        cls._models[model.__name__] = model
    
    @classmethod
    def get(cls, name: str) -> Type["Model"]:
        """
        Get a model class by name.
        
        Args:
            name: The model class name
            
        Returns:
            The model class
            
        Raises:
            KeyError: If model not found
        """
        return cls._models[name]
    
    @classmethod
    def all(cls) -> Dict[str, Type["Model"]]:
        """
        Get all registered models.
        
        Returns:
            Dictionary of model name -> model class
        """
        return cls._models.copy()
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered models (useful for testing)."""
        cls._models.clear()
