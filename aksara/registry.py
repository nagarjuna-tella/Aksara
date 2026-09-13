"""
Model Registry

Stores all discovered model classes for migrations and introspection.
Provides AI metadata helper functions for model/field introspection.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aksara.model.base import Model


class AmbiguousModelError(LookupError):
    """Raised when a simple model name identifies more than one model."""

    def __init__(self, name: str, candidates: list[str]):
        self.name = name
        self.candidates = tuple(sorted(candidates))
        choices = ", ".join(self.candidates)
        super().__init__(
            f"Model name '{name}' is ambiguous. Use one of: {choices}"
        )


class ModelRegistry:
    """
    Registry to store all discovered model classes.

    Models are automatically registered when their class is created
    via the ModelMeta metaclass.
    """

    _models: dict[str, type[Model]] = {}
    _view: Mapping[str, type[Model]] = MappingProxyType(_models)
    _version: int = 0

    @staticmethod
    def identity(model: type[Model]) -> str:
        """Return the stable qualified identity used for ambiguous models."""
        return f"{model.__module__}.{model.__qualname__}"

    @classmethod
    def _sort_models(cls) -> None:
        """Keep enumeration deterministic without replacing the live mapping."""
        ordered = sorted(cls._models.items())
        cls._models.clear()
        cls._models.update(ordered)

    @classmethod
    def register(cls, model: type[Model]) -> None:
        """
        Register a model class.

        Args:
            model: The model class to register
        """
        simple_name = model.__name__
        identity = cls.identity(model)
        same_name = {
            key: registered
            for key, registered in cls._models.items()
            if registered.__name__ == simple_name
        }
        other_identities = {
            cls.identity(registered)
            for registered in same_name.values()
            if cls.identity(registered) != identity
        }

        for key, registered in same_name.items():
            if cls.identity(registered) == identity:
                del cls._models[key]

        if other_identities:
            for key, registered in list(same_name.items()):
                registered_identity = cls.identity(registered)
                if registered_identity != identity:
                    cls._models.pop(key, None)
                    cls._models[registered_identity] = registered
            cls._models[identity] = model
        else:
            cls._models[simple_name] = model

        cls._sort_models()
        cls._version += 1

    @classmethod
    def get(cls, name: str) -> type[Model]:
        """
        Get a model class by name.

        Args:
            name: An unambiguous class name or exact qualified identity

        Returns:
            The model class

        Raises:
            KeyError: If model not found
            AmbiguousModelError: If a simple name identifies multiple models
        """
        if "." in name:
            for model in cls._models.values():
                if cls.identity(model) == name:
                    return model
            raise KeyError(name)

        matches = [
            model for model in cls._models.values()
            if model.__name__ == name
        ]
        if not matches:
            raise KeyError(name)
        if len(matches) > 1:
            raise AmbiguousModelError(
                name,
                [cls.identity(model) for model in matches],
            )
        return matches[0]

    @classmethod
    def reference(cls, model: type[Model]) -> str:
        """Return the shortest registry reference that identifies ``model``."""
        matches = [
            registered for registered in cls._models.values()
            if registered.__name__ == model.__name__
        ]
        identities = {cls.identity(registered) for registered in matches}
        if identities == {cls.identity(model)}:
            return model.__name__
        return cls.identity(model)

    @classmethod
    def all(cls) -> Mapping[str, type[Model]]:
        """
        Get all registered models as a read-only view of the live registry.

        Returns:
            Read-only mapping of model reference -> model class. Unambiguous
            models use their simple class name; collisions use qualified identities.
        """
        return cls._view

    @classmethod
    def snapshot(cls) -> dict[str, type[Model]]:
        """Return a shallow copy of the registry for callers that need stability."""
        return cls._models.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear all registered models (useful for testing)."""
        cls._models.clear()
        cls._version = 0


# =============================================================================
# AI Metadata Helper Functions
# =============================================================================

def get_models(ai_exposed_only: bool = False) -> list[type[Model]]:
    """
    Get all registered models.
    
    Args:
        ai_exposed_only: If True, only return models with ai_agent_exposed=True
        
    Returns:
        List of model classes
    """
    models = list(ModelRegistry.all().values())
    
    if ai_exposed_only:
        models = [
            m for m in models 
            if getattr(getattr(m, '_ai_meta', None), 'ai_agent_exposed', True)
        ]
    
    return models


def get_model_meta(model: type[Model]) -> dict[str, Any]:
    """
    Get AI metadata for a model.
    
    Args:
        model: The model class
        
    Returns:
        Dictionary with AI metadata:
            - name: The model name (ai_name or class name)
            - description: AI description of the model
            - table: The database table name
            - ai_agent_exposed: Whether AI agents can access this model
            - ai_permissions: List of allowed operations
            - fields: List of field metadata dicts
    """
    ai_meta = getattr(model, '_ai_meta', None)
    
    if ai_meta is None:
        # No AI metadata, use defaults
        return {
            'name': model.__name__,
            'description': '',
            'table': model.__tablename__,
            'ai_agent_exposed': True,
            'ai_permissions': ['read', 'write', 'delete'],
            'fields': get_model_fields(model),
        }
    
    return {
        'name': ai_meta.ai_name or model.__name__,
        'description': ai_meta.ai_description or '',
        'table': model.__tablename__,
        'ai_agent_exposed': ai_meta.ai_agent_exposed,
        'ai_permissions': ai_meta.ai_permissions or ['read', 'write', 'delete'],
        'fields': get_model_fields(model),
    }


def get_model_fields(
    model: type[Model],
    include_sensitive: bool = False,
    writable_only: bool = False,
) -> list[dict[str, Any]]:
    """
    Get field metadata for a model.
    
    Args:
        model: The model class
        include_sensitive: If True, include fields marked as ai_sensitive
        writable_only: If True, only include fields with ai_agent_writable=True
        
    Returns:
        List of field metadata dicts:
            - name: The field name
            - db_column: The database column name
            - type: The field type class name
            - nullable: Whether the field is nullable
            - primary_key: Whether it's a primary key
            - ai_description: AI description of the field
            - ai_sensitive: Whether the field contains sensitive data
            - ai_agent_writable: Whether AI agents can write to this field
    """
    from aksara.fields import ForeignKey  # type: ignore[attr-defined]
    
    fields_meta = []
    
    for name, field in model._fields.items():
        # Skip sensitive fields unless requested
        if getattr(field, "ai_sensitive", False) and not include_sensitive:
            continue
            
        # Skip non-writable fields if only writable requested
        if writable_only and not getattr(field, "ai_agent_writable", True):
            continue
        
        # Determine the database column name
        if isinstance(field, ForeignKey):
            db_column = field.db_column_name
        else:
            db_column = name
        
        field_meta = {
            'name': name,
            'db_column': db_column,
            'type': field.__class__.__name__,
            'nullable': field.nullable,
            'primary_key': field.primary_key,
            'ai_description': getattr(field, "ai_description", None) or '',
            'ai_sensitive': getattr(field, "ai_sensitive", False),
            'ai_agent_writable': getattr(field, "ai_agent_writable", True),
        }
        
        # Add FK-specific metadata
        if isinstance(field, ForeignKey):
            field_meta['foreign_key'] = {
                'to': field._to if isinstance(field._to, str) else field._to.__name__,
                'on_delete': field.on_delete,
            }
        
        fields_meta.append(field_meta)
    
    return fields_meta


def get_model_schema_for_ai(
    model: type[Model],
    include_sensitive: bool = False,
) -> dict[str, Any]:
    """
    Get a complete schema description suitable for AI/LLM consumption.
    
    This provides a structured representation of the model that can be
    used by AI agents to understand the data model.
    
    Args:
        model: The model class
        include_sensitive: If True, include sensitive fields
        
    Returns:
        Dictionary with complete model schema
    """
    meta = get_model_meta(model)
    
    # Only include writable fields for the AI schema
    writable_fields = get_model_fields(
        model,
        include_sensitive=include_sensitive,
        writable_only=True,
    )
    
    return {
        'model': meta['name'],
        'description': meta['description'],
        'table': meta['table'],
        'permissions': meta['ai_permissions'],
        'fields': meta['fields'],
        'writable_fields': [f['name'] for f in writable_fields],
    }


def get_all_schemas_for_ai(include_sensitive: bool = False) -> list[dict[str, Any]]:
    """
    Get schemas for all AI-exposed models.
    
    Useful for providing an AI agent with a complete overview
    of the available data models.
    
    Args:
        include_sensitive: If True, include sensitive fields
        
    Returns:
        List of model schema dicts
    """
    models = get_models(ai_exposed_only=True)
    
    return [
        get_model_schema_for_ai(m, include_sensitive=include_sensitive)
        for m in models
    ]
