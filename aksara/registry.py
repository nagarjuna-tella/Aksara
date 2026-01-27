"""
Model Registry

Stores all discovered model classes for migrations and introspection.
Provides AI metadata helper functions for model/field introspection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

if TYPE_CHECKING:
    from aksara.model.base import Model
    from aksara.fields import Field


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


# =============================================================================
# AI Metadata Helper Functions
# =============================================================================

def get_models(ai_exposed_only: bool = False) -> List[Type["Model"]]:
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


def get_model_meta(model: Type["Model"]) -> Dict[str, Any]:
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
    model: Type["Model"],
    include_sensitive: bool = False,
    writable_only: bool = False,
) -> List[Dict[str, Any]]:
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
    from aksara.fields import ForeignKey
    
    fields_meta = []
    
    for name, field in model._fields.items():
        # Skip sensitive fields unless requested
        if field.ai_sensitive and not include_sensitive:
            continue
            
        # Skip non-writable fields if only writable requested
        if writable_only and not field.ai_agent_writable:
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
            'ai_description': field.ai_description or '',
            'ai_sensitive': field.ai_sensitive,
            'ai_agent_writable': field.ai_agent_writable,
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
    model: Type["Model"],
    include_sensitive: bool = False,
) -> Dict[str, Any]:
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


def get_all_schemas_for_ai(include_sensitive: bool = False) -> List[Dict[str, Any]]:
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
