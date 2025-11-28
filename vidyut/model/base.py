"""
Model Base Class

The foundation for all Vidyut models with automatic field discovery,
table name inference, and CRUD operations.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar, ClassVar
from uuid import UUID

from vidyut.fields import Field, UUID as UUIDField, DateTime, String, Integer, Boolean, JSON
from vidyut.registry import ModelRegistry


T = TypeVar("T", bound="Model")


def to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def pluralize(name: str) -> str:
    """Simple pluralization for table names."""
    if name.endswith('y'):
        return name[:-1] + 'ies'
    if name.endswith(('s', 'x', 'z', 'ch', 'sh')):
        return name + 'es'
    return name + 's'


class ModelMeta(type):
    """
    Metaclass for Model that handles:
    - Field discovery and registration
    - Automatic table name inference
    - Manager attachment
    """
    
    def __new__(mcs, name: str, bases: tuple, namespace: dict, **kwargs):
        # Don't process the base Model class itself
        is_base = namespace.get('__abstract__', False) or name == 'Model'
        
        # Collect fields from the class
        fields: Dict[str, Field] = {}
        
        # Inherit fields from parent classes
        for base in bases:
            if hasattr(base, '_fields'):
                fields.update(base._fields)
        
        # Collect new fields defined in this class and REMOVE them from namespace
        # This is crucial so __getattr__ gets called for field access
        field_keys_to_remove = []
        for key, value in list(namespace.items()):
            if isinstance(value, Field):
                value.name = key
                fields[key] = value
                field_keys_to_remove.append(key)
        
        # Remove field definitions from namespace so __getattr__ works
        for key in field_keys_to_remove:
            del namespace[key]
        
        # Add default fields if not a base class
        if not is_base:
            # Add UUID primary key if not defined
            if 'id' not in fields:
                id_field = UUIDField(primary_key=True)
                id_field.name = 'id'
                fields['id'] = id_field
            
            # Add created_at if not defined
            if 'created_at' not in fields:
                created_field = DateTime(auto_now_add=True)
                created_field.name = 'created_at'
                fields['created_at'] = created_field
            
            # Add updated_at if not defined
            if 'updated_at' not in fields:
                updated_field = DateTime(auto_now=True)
                updated_field.name = 'updated_at'
                fields['updated_at'] = updated_field
        
        namespace['_fields'] = fields
        
        # Infer table name
        if not is_base and '__tablename__' not in namespace:
            namespace['__tablename__'] = pluralize(to_snake_case(name))
        
        # Create the class
        cls = super().__new__(mcs, name, bases, namespace)
        
        # Register non-abstract models
        if not is_base:
            ModelRegistry.register(cls)
            
            # Attach the manager
            from vidyut.manager import Manager
            cls.objects = Manager(cls)
        
        return cls


class Model(metaclass=ModelMeta):
    """
    Base class for all Vidyut models.
    
    Every model automatically gets:
    - id: UUID primary key
    - created_at: Timestamp of creation
    - updated_at: Timestamp of last update
    
    Usage:
        class User(Model):
            email = fields.String(unique=True)
            name = fields.String(max_length=100)
            is_active = fields.Boolean(default=True)
    """
    
    __abstract__ = True
    __tablename__: ClassVar[str]
    _fields: ClassVar[Dict[str, Field]]
    objects: ClassVar["Manager"]  # type: ignore
    
    def __init__(self, **kwargs):
        """
        Initialize a model instance with field values.
        
        Args:
            **kwargs: Field values
        """
        self._data: Dict[str, Any] = {}
        self._is_new = True
        
        # Set field values from kwargs or defaults
        for field_name, field in self._fields.items():
            if field_name in kwargs:
                value = kwargs[field_name]
            else:
                value = field.get_default_value()
            
            self._data[field_name] = value
    
    def __getattr__(self, name: str) -> Any:
        """Get field value."""
        if name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")
        
        if name in self._fields:
            return self._data.get(name)
        
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")
    
    def __setattr__(self, name: str, value: Any) -> None:
        """Set field value."""
        if name.startswith('_'):
            super().__setattr__(name, value)
            return
        
        if name in self._fields:
            self._data[name] = value
            return
        
        super().__setattr__(name, value)
    
    def __repr__(self) -> str:
        """String representation."""
        pk = self._data.get('id', 'new')
        return f"<{self.__class__.__name__} {pk}>"
    
    @classmethod
    def _from_record(cls: Type[T], record: Any) -> T:
        """
        Create a model instance from a database record.
        
        Args:
            record: Database record (asyncpg.Record)
            
        Returns:
            Model instance
        """
        instance = cls.__new__(cls)
        instance._data = {}
        instance._is_new = False
        
        for field_name, field in cls._fields.items():
            if field_name in record.keys():
                value = field.to_python(record[field_name])
                instance._data[field_name] = value
        
        return instance
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary.
        
        Returns:
            Dictionary of field values
        """
        result = {}
        for field_name, field in self._fields.items():
            value = self._data.get(field_name)
            # Convert UUID to string for JSON serialization
            if isinstance(value, UUID):
                value = str(value)
            result[field_name] = value
        return result
    
    async def save(self) -> None:
        """
        Save the model instance to the database.
        
        If this is a new instance (not yet persisted), performs INSERT.
        If this is an existing instance, performs UPDATE.
        """
        from vidyut.db import Database
        
        db = Database.get_instance()
        
        # Update updated_at timestamp
        if 'updated_at' in self._fields:
            self._data['updated_at'] = datetime.now(timezone.utc)
        
        if self._is_new:
            await self._insert(db)
            self._is_new = False
        else:
            await self._update(db)
    
    async def _insert(self, db: "Database") -> None:
        """Insert a new record."""
        fields_to_insert = []
        values = []
        placeholders = []
        
        for i, (field_name, field) in enumerate(self._fields.items(), 1):
            # Skip auto-generated fields without values
            if field_name == 'id' and self._data.get('id') is None:
                continue
            # Skip auto_now_add fields (created_at) - SQL DEFAULT handles them
            if isinstance(field, DateTime) and field.auto_now_add:
                continue
            
            value = self._data.get(field_name)
            if value is not None or field.nullable:
                fields_to_insert.append(field_name)
                values.append(field.to_db(value))
                placeholders.append(f"${len(values)}")
        
        columns = ", ".join(fields_to_insert)
        params = ", ".join(placeholders)
        
        query = f"""
            INSERT INTO {self.__tablename__} ({columns})
            VALUES ({params})
            RETURNING *
        """
        
        record = await db.fetchrow(query, *values)
        
        # Update instance with returned values (includes generated id, timestamps)
        for field_name, field in self._fields.items():
            if field_name in record.keys():
                self._data[field_name] = field.to_python(record[field_name])
    
    async def _update(self, db: "Database") -> None:
        """Update an existing record."""
        set_clauses = []
        values = []
        
        for field_name, field in self._fields.items():
            # Skip primary key and created_at
            if field.primary_key or field_name == 'created_at':
                continue
            
            value = self._data.get(field_name)
            values.append(field.to_db(value))
            set_clauses.append(f"{field_name} = ${len(values)}")
        
        # Add the id for the WHERE clause
        values.append(self._data['id'])
        
        set_sql = ", ".join(set_clauses)
        query = f"""
            UPDATE {self.__tablename__}
            SET {set_sql}
            WHERE id = ${len(values)}
            RETURNING *
        """
        
        record = await db.fetchrow(query, *values)
        
        # Update instance with returned values
        for field_name, field in self._fields.items():
            if field_name in record.keys():
                self._data[field_name] = field.to_python(record[field_name])
    
    async def delete(self) -> None:
        """Delete this model instance from the database."""
        from vidyut.db import Database
        
        if self._is_new:
            raise ValueError("Cannot delete a model that hasn't been saved yet")
        
        db = Database.get_instance()
        
        query = f"DELETE FROM {self.__tablename__} WHERE id = $1"
        await db.execute(query, self._data['id'])
    
    @classmethod
    def get_create_table_sql(cls) -> str:
        """
        Generate CREATE TABLE SQL for this model.
        
        Returns:
            SQL statement to create the table
        """
        # Sort fields by creation order
        sorted_fields = sorted(
            cls._fields.values(),
            key=lambda f: (not f.primary_key, f._creation_order)
        )
        
        columns = []
        for field in sorted_fields:
            columns.append(f"    {field.get_column_definition()}")
        
        columns_sql = ",\n".join(columns)
        
        return f"""CREATE TABLE IF NOT EXISTS {cls.__tablename__} (
{columns_sql}
);"""
