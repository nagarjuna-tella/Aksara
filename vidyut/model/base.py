"""
Model Base Class

The foundation for all Vidyut models with automatic field discovery,
table name inference, and CRUD operations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar, ClassVar
from uuid import UUID

from vidyut.fields import Field, UUID as UUIDField, DateTime, String, Integer, Boolean, JSON, ForeignKey, ManyToMany, ManyToManyManager
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


@dataclass
class ModelAIMeta:
    """
    AI metadata for a model.
    
    Stored in Model.Meta and accessible via registry functions.
    """
    ai_name: Optional[str] = None
    ai_description: Optional[str] = None
    ai_agent_exposed: bool = True
    ai_permissions: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.ai_name,
            "description": self.ai_description,
            "agent_exposed": self.ai_agent_exposed,
            "permissions": self.ai_permissions or [],
        }


class ModelMeta(type):
    """
    Metaclass for Model that handles:
    - Field discovery and registration
    - Automatic table name inference
    - Manager attachment
    - AI metadata extraction
    - ManyToMany field setup
    """
    
    def __new__(mcs, name: str, bases: tuple, namespace: dict, **kwargs):
        # Don't process the base Model class itself
        is_base = namespace.get('__abstract__', False) or name == 'Model'
        
        # Collect fields from the class
        fields: Dict[str, Field] = {}
        fk_fields: Dict[str, ForeignKey] = {}
        m2m_fields: Dict[str, ManyToMany] = {}
        
        # Inherit fields from parent classes
        for base in bases:
            if hasattr(base, '_fields'):
                fields.update(base._fields)
            if hasattr(base, '_fk_fields'):
                fk_fields.update(base._fk_fields)
            if hasattr(base, '_m2m_fields'):
                m2m_fields.update(base._m2m_fields)
        
        # Collect new fields defined in this class and REMOVE them from namespace
        # This is crucial so __getattr__ gets called for field access
        field_keys_to_remove = []
        for key, value in list(namespace.items()):
            if isinstance(value, Field):
                value.name = key
                
                # Handle ManyToMany separately (virtual field)
                if isinstance(value, ManyToMany):
                    m2m_fields[key] = value
                    field_keys_to_remove.append(key)
                    continue
                
                fields[key] = value
                
                # Track ForeignKey fields separately
                if isinstance(value, ForeignKey):
                    fk_fields[key] = value
                    # Also create the _id field mapping
                    fk_col_name = value.db_column_name
                    value._actual_column_name = fk_col_name
                
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
        namespace['_fk_fields'] = fk_fields
        namespace['_m2m_fields'] = m2m_fields
        
        # Extract AI metadata from nested Meta class
        meta_class = namespace.get('Meta')
        ai_meta = ModelAIMeta()
        if meta_class:
            ai_meta = ModelAIMeta(
                ai_name=getattr(meta_class, 'ai_name', None) or name,
                ai_description=getattr(meta_class, 'ai_description', None),
                ai_agent_exposed=getattr(meta_class, 'ai_agent_exposed', True),
                ai_permissions=getattr(meta_class, 'ai_permissions', None),
            )
        else:
            ai_meta.ai_name = name
        namespace['_ai_meta'] = ai_meta
        
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
            
            # Set source model on ManyToMany fields
            for field_name, m2m_field in m2m_fields.items():
                m2m_field._source_model = cls
        
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
            
            class Meta:
                ai_name = "User"
                ai_description = "Application user"
                ai_agent_exposed = True
                ai_permissions = ["read", "search"]
    """
    
    __abstract__ = True
    __tablename__: ClassVar[str]
    _fields: ClassVar[Dict[str, Field]]
    _fk_fields: ClassVar[Dict[str, ForeignKey]]
    _m2m_fields: ClassVar[Dict[str, ManyToMany]]
    _ai_meta: ClassVar[ModelAIMeta]
    objects: ClassVar["Manager"]  # type: ignore
    
    def __init__(self, **kwargs):
        """
        Initialize a model instance with field values.
        
        Args:
            **kwargs: Field values (supports both 'field' and 'field_id' for ForeignKeys)
        """
        self._data: Dict[str, Any] = {}
        self._m2m_managers: Dict[str, ManyToManyManager] = {}
        self._is_new = True
        
        # Set field values from kwargs or defaults
        for field_name, field in self._fields.items():
            # Handle ForeignKey fields - accept both 'author' and 'author_id'
            if isinstance(field, ForeignKey):
                fk_col = field.db_column_name  # e.g., 'author_id'
                if fk_col in kwargs:
                    value = kwargs[fk_col]
                elif field_name in kwargs:
                    value = kwargs[field_name]
                else:
                    value = field.get_default_value()
            elif field_name in kwargs:
                value = kwargs[field_name]
            else:
                value = field.get_default_value()
            
            self._data[field_name] = value
    
    def __getattr__(self, name: str) -> Any:
        """Get field value or ManyToMany manager."""
        if name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")
        
        # Check regular fields
        if name in self._fields:
            return self._data.get(name)
        
        # Check ManyToMany fields - return manager
        if name in self._m2m_fields:
            if name not in self._m2m_managers:
                self._m2m_managers[name] = ManyToManyManager(
                    self._m2m_fields[name],
                    self
                )
            return self._m2m_managers[name]
        
        # Handle ForeignKey column access (e.g., author_id)
        for field_name, field in self._fk_fields.items():
            if name == field.db_column_name:
                return self._data.get(field_name)
        
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")
    
    def __setattr__(self, name: str, value: Any) -> None:
        """Set field value."""
        if name.startswith('_'):
            super().__setattr__(name, value)
            return
        
        if name in self._fields:
            self._data[name] = value
            return
        
        # Handle ForeignKey column access (e.g., author_id)
        for field_name, field in self._fk_fields.items():
            if name == field.db_column_name:
                self._data[field_name] = value
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
        instance._m2m_managers = {}
        instance._is_new = False
        
        record_keys = set(record.keys())
        
        for field_name, field in cls._fields.items():
            # Handle ForeignKey - look for the _id column
            if isinstance(field, ForeignKey):
                col_name = field.db_column_name
                if col_name in record_keys:
                    value = field.to_python(record[col_name])
                    instance._data[field_name] = value
            elif field_name in record_keys:
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
        
        for field_name, field in self._fields.items():
            # Skip auto-generated fields without values
            if field_name == 'id' and self._data.get('id') is None:
                continue
            # Skip auto_now_add fields (created_at) - SQL DEFAULT handles them
            if isinstance(field, DateTime) and field.auto_now_add:
                continue
            
            value = self._data.get(field_name)
            if value is not None or field.nullable:
                # For ForeignKey, use the column name (e.g., author_id)
                if isinstance(field, ForeignKey):
                    col_name = field.db_column_name
                else:
                    col_name = field_name
                
                fields_to_insert.append(col_name)
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
        record_keys = set(record.keys())
        for field_name, field in self._fields.items():
            if isinstance(field, ForeignKey):
                col_name = field.db_column_name
                if col_name in record_keys:
                    self._data[field_name] = field.to_python(record[col_name])
            elif field_name in record_keys:
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
            
            # For ForeignKey, use the column name (e.g., author_id)
            if isinstance(field, ForeignKey):
                col_name = field.db_column_name
            else:
                col_name = field_name
            
            set_clauses.append(f"{col_name} = ${len(values)}")
        
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
        record_keys = set(record.keys())
        for field_name, field in self._fields.items():
            if isinstance(field, ForeignKey):
                col_name = field.db_column_name
                if col_name in record_keys:
                    self._data[field_name] = field.to_python(record[col_name])
            elif field_name in record_keys:
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
        constraints = []
        
        for field in sorted_fields:
            columns.append(f"    {field.get_column_definition()}")
            
            # Collect FK constraints
            if isinstance(field, ForeignKey):
                constraints.append(f"    {field.get_constraint_definition()}")
        
        all_parts = columns + constraints
        columns_sql = ",\n".join(all_parts)
        
        return f"""CREATE TABLE IF NOT EXISTS {cls.__tablename__} (
{columns_sql}
);"""
    
    @classmethod
    def get_ai_metadata(cls) -> Dict[str, Any]:
        """
        Get AI metadata for this model.
        
        Returns:
            Dictionary with model and field AI metadata
        """
        return {
            "model": cls._ai_meta.to_dict(),
            "table_name": cls.__tablename__,
            "fields": {
                name: field.get_ai_metadata()
                for name, field in cls._fields.items()
            },
        }
