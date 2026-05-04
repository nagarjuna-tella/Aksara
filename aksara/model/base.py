"""
Model Base Class

The foundation for all Aksara models with automatic field discovery,
table name inference, and CRUD operations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar, ClassVar
from uuid import UUID

from aksara.db import quote_identifier
from aksara.fields import Field, UUID as UUIDField, DateTime, String, Integer, Boolean, JSON, ForeignKey, ManyToMany, ManyToManyManager
from aksara.registry import ModelRegistry


T = TypeVar("T", bound="Model")


def to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def pluralize(name: str) -> str:
    """Simple pluralization for table names."""
    if name.endswith('y') and len(name) > 1 and name[-2] not in 'aeiou':
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


class ModelMetaInfo:
    """
    Rich, introspectable metadata interface for a model.
    
    Provides access to model metadata including fields, relations,
    table name, and primary key information.
    
    v0.3.14: Developer Delight Pack 2
    
    Usage:
        User.meta.name           # "User"
        User.meta.table_name     # "users"
        User.meta.fields         # List of field objects
        User.meta.pk             # Primary key field
        User.meta.relations      # Dict of FK/M2M fields
        User.meta.to_dict()      # Full serializable representation
    
    This supports:
    - Admin UI generation
    - AI schema & tool generation
    - DX tools like `aksara shell` and docs
    """
    
    def __init__(self, model: Type["Model"]):
        self._model = model
    
    @property
    def name(self) -> str:
        """Get the model class name."""
        return self._model.__name__
    
    @property
    def app_label(self) -> Optional[str]:
        """
        Get the app_label for this model.
        
        Returns the app_label from Meta class if defined, otherwise
        derives it from the model's module path.
        
        For example:
        - myapp.models.Post -> "myapp"
        - blog.models.Article -> "blog"  
        - app.models.User -> "app"
        """
        meta_class = getattr(self._model, "Meta", None)
        if meta_class:
            explicit_label = getattr(meta_class, "app_label", None)
            if explicit_label:
                return explicit_label
        
        # Auto-detect from module path
        module = getattr(self._model, "__module__", None)
        if module:
            # Split module path: "myapp.models" -> ["myapp", "models"]
            parts = module.split(".")
            # If it looks like "something.models", use "something"
            if len(parts) >= 2 and parts[-1] == "models":
                return parts[-2]
            # Otherwise use the first part
            if parts:
                return parts[0]
        
        return None
    
    @property
    def table_name(self) -> str:
        """Get the database table name."""
        return self._model.__tablename__
    
    @property
    def fields(self) -> List[Field]:
        """Get all field objects defined on this model."""
        return list(self._model._fields.values())
    
    @property
    def field_names(self) -> List[str]:
        """Get all field names defined on this model."""
        return list(self._model._fields.keys())
    
    @property
    def pk(self) -> Optional[Field]:
        """Get the primary key field."""
        for field in self.fields:
            if getattr(field, "primary_key", False):
                return field
        # Fallback: look for 'id' field
        return self._model._fields.get("id")
    
    @property
    def pk_name(self) -> Optional[str]:
        """Get the primary key field name."""
        pk = self.pk
        return pk.name if pk else None
    
    @property
    def relations(self) -> Dict[str, Field]:
        """
        Get all relation fields (ForeignKey, OneToOne, ManyToMany).
        
        Returns:
            Dict mapping field name to field object
        """
        from aksara.fields import ForeignKey, ManyToMany, OneToOne
        
        result: Dict[str, Field] = {}
        
        # FK and OneToOne fields
        for name, field in self._model._fk_fields.items():
            result[name] = field
        
        # ManyToMany fields
        for name, field in self._model._m2m_fields.items():
            result[name] = field
        
        return result
    
    @property
    def foreign_keys(self) -> Dict[str, ForeignKey]:
        """Get all ForeignKey fields."""
        return dict(self._model._fk_fields)
    
    @property
    def many_to_many(self) -> Dict[str, ManyToMany]:
        """Get all ManyToMany fields."""
        return dict(self._model._m2m_fields)
    
    def get_field(self, name: str) -> Optional[Field]:
        """Get a field by name."""
        return self._model._fields.get(name)
    
    def has_field(self, name: str) -> bool:
        """Check if model has a field with the given name."""
        return name in self._model._fields
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model metadata to a dictionary.
        
        Useful for serialization, API responses, and AI/LLM consumption.
        
        Returns:
            Dictionary with model metadata including fields and relations
        """
        return {
            "name": self.name,
            "app_label": self.app_label,
            "table_name": self.table_name,
            "fields": [self._field_to_dict(f) for f in self.fields],
            "pk": self.pk.name if self.pk else None,
            "relations": {
                name: self._field_to_dict(field)
                for name, field in self.relations.items()
            },
        }
    
    def _field_to_dict(self, field: Field) -> Dict[str, Any]:
        """Convert a field to a dictionary representation."""
        from aksara.fields import ForeignKey, ManyToMany, OneToOne
        
        result = {
            "name": field.name,
            "column_name": getattr(field, "column_name", field.name),
            "type": field.__class__.__name__,
            "null": getattr(field, "nullable", False),
            "unique": getattr(field, "unique", False),
            "primary_key": getattr(field, "primary_key", False),
            "default": self._serialize_default(field),
            "choices": getattr(field, "choices", None),
        }
        
        # Add relation-specific metadata
        if isinstance(field, ForeignKey):
            related_model = getattr(field, "to_model", None)
            result["related_model"] = (
                related_model.__name__ if related_model else None
            )
            result["related_name"] = getattr(field, "related_name", None)
            result["on_delete"] = getattr(field, "on_delete", None)
        
        elif isinstance(field, ManyToMany):
            related_model = getattr(field, "to_model", None)
            result["related_model"] = (
                related_model.__name__ if related_model else None
            )
            result["related_name"] = getattr(field, "related_name", None)
            result["through_table"] = getattr(field, "join_table_name", None)
        
        return result
    
    def _serialize_default(self, field: Field) -> Any:
        """Serialize a field's default value for JSON output."""
        default = getattr(field, "default", None)
        if default is None:
            return None
        if callable(default):
            return f"<callable: {default.__name__}>"
        # Handle common non-serializable types
        if hasattr(default, "__name__"):
            return f"<{default.__name__}>"
        return default
    
    def __repr__(self) -> str:
        return f"<ModelMetaInfo: {self.name}>"


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
        
        # Infer table name (check Meta.table_name first, then auto-generate)
        if not is_base and '__tablename__' not in namespace:
            if meta_class and hasattr(meta_class, 'table_name'):
                namespace['__tablename__'] = meta_class.table_name
            else:
                namespace['__tablename__'] = pluralize(to_snake_case(name))
        
        # Create the class
        cls = super().__new__(mcs, name, bases, namespace)
        
        # Register non-abstract models
        if not is_base:
            ModelRegistry.register(cls)
            
            # Attach the manager
            from aksara.manager import Manager
            cls.objects = Manager(cls)
            
            # v0.3.14: Attach ModelMetaInfo for introspection
            cls.meta = ModelMetaInfo(cls)
            
            # Set source model on ManyToMany fields
            for field_name, m2m_field in m2m_fields.items():
                m2m_field._source_model = cls
            
            # Register relations for reverse access (deferred until target models are loaded)
            cls._pending_relations = []
            
            # Collect FK relations
            for field_name, fk_field in fk_fields.items():
                from aksara.fields import OneToOne
                relation_type = "o2o" if isinstance(fk_field, OneToOne) else "fk"
                cls._pending_relations.append({
                    "type": relation_type,
                    "field_name": field_name,
                    "field": fk_field,
                })
            
            # Collect M2M relations
            for field_name, m2m_field in m2m_fields.items():
                cls._pending_relations.append({
                    "type": "m2m",
                    "field_name": field_name,
                    "field": m2m_field,
                })
        
        return cls


def finalize_relations() -> None:
    """
    Finalize all pending relations after all models are loaded.
    
    This registers relations with the RelationRegistry and attaches
    reverse descriptors to target models.
    
    Call this after all models are imported, typically at app startup.
    """
    from aksara.registry import ModelRegistry
    from aksara.relations import RelationRegistry, register_relation
    
    for model_name, model_cls in ModelRegistry.all().items():
        pending = getattr(model_cls, '_pending_relations', [])
        
        for rel_info in pending:
            try:
                field = rel_info["field"]
                target_model = field.to_model
                
                if rel_info["type"] == "m2m":
                    register_relation(
                        relation_type="m2m",
                        source_model=model_cls,
                        target_model=target_model,
                        field_name=rel_info["field_name"],
                        related_name=field.related_name,
                        through_table=field.join_table_name,
                    )
                else:
                    register_relation(
                        relation_type=rel_info["type"],
                        source_model=model_cls,
                        target_model=target_model,
                        field_name=rel_info["field_name"],
                        related_name=field.related_name,
                        on_delete=field.on_delete,
                    )
            except Exception as e:
                # Skip if target model not yet loaded (lazy reference)
                pass
    
    # Attach reverse descriptors to all target models
    RelationRegistry.attach_reverse_descriptors()


class Model(metaclass=ModelMeta):
    """
    Base class for all Aksara models.
    
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
    meta: ClassVar["ModelMetaInfo"]  # v0.3.14: Model introspection
    objects: ClassVar["Manager"]  # type: ignore
    
    def __init__(self, **kwargs):
        """
        Initialize a model instance with field values.
        
        Args:
            **kwargs: Field values (supports both 'field' and 'field_id' for ForeignKeys)
        """
        self._data: Dict[str, Any] = {}
        self._m2m_managers: Dict[str, ManyToManyManager] = {}
        self._prefetched_relations: Dict[str, Any] = {}  # Cache for select_related
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
        instance._prefetched_relations = {}  # Cache for select_related
        instance._is_new = False
        
        record_keys = set(record.keys())
        consumed_keys = set()
        
        for field_name, field in cls._fields.items():
            # Handle ForeignKey - look for the _id column
            if isinstance(field, ForeignKey):
                col_name = field.db_column_name
                if col_name in record_keys:
                    value = field.to_python(record[col_name])
                    instance._data[field_name] = value
                    consumed_keys.add(col_name)
            elif field_name in record_keys:
                value = field.to_python(record[field_name])
                instance._data[field_name] = value
                consumed_keys.add(field_name)

        for extra_key in record_keys - consumed_keys:
            setattr(instance, extra_key, record[extra_key])
        
        return instance
    
    def get_related(self, field_name: str) -> Any:
        """
        Get a prefetched related object for a FK/O2O field.
        
        This returns the related model instance if it was preloaded
        via select_related(). Returns None if not prefetched or if
        the FK value is NULL.
        
        Args:
            field_name: Name of the FK/O2O field
            
        Returns:
            Related model instance or None
            
        Raises:
            ValueError: If field is not FK/O2O or wasn't prefetched
            
        Usage:
            posts = await Post.objects.select_related("author").all()
            author = posts[0].get_related("author")
        """
        if field_name not in self._fk_fields:
            raise ValueError(f"'{field_name}' is not a ForeignKey/OneToOne field")
        
        if field_name not in self._prefetched_relations:
            raise ValueError(
                f"'{field_name}' was not prefetched. "
                f"Use select_related('{field_name}') to preload it."
            )
        
        return self._prefetched_relations.get(field_name)
    
    def get_prefetched_m2m(self, field_name: str) -> List["Model"]:
        """
        Get prefetched M2M related objects.
        
        This returns the list of related model instances if they were
        preloaded via prefetch_related().
        
        Args:
            field_name: Name of the M2M field
            
        Returns:
            List of related model instances
            
        Raises:
            ValueError: If field is not M2M or wasn't prefetched
        """
        if field_name not in self._m2m_fields:
            raise ValueError(f"'{field_name}' is not a ManyToMany field")
        
        if field_name not in self._prefetched_relations:
            raise ValueError(
                f"'{field_name}' was not prefetched. "
                f"Use prefetch_related('{field_name}') to preload it."
            )
        
        return self._prefetched_relations.get(field_name, [])
    
    def is_prefetched(self, field_name: str) -> bool:
        """Check if a relation field has been prefetched."""
        return field_name in self._prefetched_relations
    
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
    
    async def _validate_fields(self) -> None:
        """
        Validate all fields before saving.
        
        Checks:
        - Non-nullable fields have values (unless auto-generated or have defaults)
        - Field-specific validation (Email, URL, Decimal, etc.)
        
        Raises:
            ValidationError: If validation fails
        """
        from aksara.exceptions import ValidationError
        
        errors = {}
        
        for field_name, field in self._fields.items():
            value = self._data.get(field_name)
            
            # Skip auto-generated fields
            if field.primary_key and value is None:
                continue
            if isinstance(field, DateTime):
                if field.auto_now or field.auto_now_add:
                    continue
            
            # Check non-nullable constraint
            if value is None:
                has_default = field.default is not None or callable(field.default)
                if not field.nullable and not has_default:
                    errors[field_name] = f"Field '{field_name}' cannot be null"
                    continue
            
            # Run field-specific validation if value is not None
            if value is not None and hasattr(field, 'validate'):
                try:
                    field.validate(value)
                except ValueError as e:
                    errors[field_name] = str(e)
        
        if errors:
            # Raise with the first error for backwards compatibility
            first_error = next(iter(errors.values()))
            raise ValidationError(first_error, errors=errors)
    
    async def save(self) -> None:
        """
        Save the model instance to the database.
        
        If this is a new instance (not yet persisted), performs INSERT.
        If this is an existing instance, performs UPDATE.
        
        Raises:
            ValidationError: If field validation fails
        """
        from aksara.db import Database
        from aksara.exceptions import ValidationError
        from aksara.signals import pre_save, post_save
        
        # Fire pre_save signal
        await pre_save.send(sender=self.__class__, instance=self, is_new=self._is_new)
        
        # Validate all fields before saving
        await self._validate_fields()
        
        db = Database.get_instance()
        
        # Update updated_at timestamp
        if 'updated_at' in self._fields:
            self._data['updated_at'] = datetime.now(timezone.utc)
        
        if self._is_new:
            await self._insert(db)
            self._is_new = False
        else:
            await self._update(db)
            
        # Fire post_save signal
        await post_save.send(sender=self.__class__, instance=self)
    
    async def _insert(self, db: "Database") -> None:
        """Insert a new record."""
        from aksara.db.expressions import is_expression

        fields_to_insert = []
        values = []
        placeholders = []
        
        for field_name, field in self._fields.items():
            # Skip auto-generated fields without values
            if field_name == 'id' and self._data.get('id') is None:
                continue
            # Skip auto_now_add fields unless the user explicitly set a value
            if isinstance(field, DateTime) and field.auto_now_add and self._data.get(field_name) is None:
                continue
            
            value = self._data.get(field_name)
            if value is not None or field.nullable:
                if is_expression(value):
                    raise ValueError("Expressions are only supported in update operations")
                # For ForeignKey, use the column name (e.g., author_id)
                if isinstance(field, ForeignKey):
                    col_name = field.db_column_name
                else:
                    col_name = field_name
                
                fields_to_insert.append(quote_identifier(col_name))
                values.append(field.to_db(value))
                placeholders.append(f"${len(values)}")
        
        columns = ", ".join(fields_to_insert)
        params = ", ".join(placeholders)
        table = quote_identifier(self.__tablename__)
        
        query = f"""
            INSERT INTO {table} ({columns})
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
        from aksara.db.expressions import compile_expression, is_expression

        set_clauses = []
        values = []
        
        for field_name, field in self._fields.items():
            # Skip primary key and created_at
            if field.primary_key or field_name == 'created_at':
                continue
            
            value = self._data.get(field_name)
            
            # For ForeignKey, use the column name (e.g., author_id)
            if isinstance(field, ForeignKey):
                col_name = field.db_column_name
            else:
                col_name = field_name

            if is_expression(value):
                set_clauses.append(
                    f"{quote_identifier(col_name)} = {compile_expression(self.__class__, value, values)}"
                )
            else:
                values.append(field.to_db(value))
                set_clauses.append(f"{quote_identifier(col_name)} = ${len(values)}")
        
        # Add the id for the WHERE clause
        values.append(self._data['id'])
        
        set_sql = ", ".join(set_clauses)
        table = quote_identifier(self.__tablename__)
        query = f"""
            UPDATE {table}
            SET {set_sql}
            WHERE "id" = ${len(values)}
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
        """
        Delete this model instance from the database.
        
        Handles on_delete policies for reverse relations:
        - RESTRICT: Raises RestrictedError if dependent objects exist
        - SET_NULL: Sets FK to NULL on dependent objects before delete
        - CASCADE: Lets database handle cascading deletes
        
        Raises:
            ValueError: If model hasn't been saved yet
            RestrictedError: If RESTRICT policy prevents deletion
        """
        from aksara.db import Database
        from aksara.fields import ForeignKey
        from aksara.relations import RelationRegistry, OnDelete
        from aksara.exceptions import RestrictedError
        from aksara.signals import pre_delete, post_delete
        
        if self._is_new:
            raise ValueError("Cannot delete a model that hasn't been saved yet")
            
        # Fire pre_delete signal
        await pre_delete.send(sender=self.__class__, instance=self)
        
        db = Database.get_instance()
        
        # Get relations pointing to this model
        relations = RelationRegistry.get_relations_to(self.__class__)
        
        for relation in relations:
            if relation.relation_type not in ("fk", "o2o"):
                continue  # M2M handled by join table CASCADE
            
            # Get the FK column name
            source_model = relation.source_model
            field = source_model._fields.get(relation.field_name)
            if isinstance(field, ForeignKey):
                fk_column = field.db_column_name
            else:
                fk_column = f"{relation.field_name}_id"
            
            on_delete = relation.on_delete or OnDelete.CASCADE.value
            
            if on_delete == OnDelete.RESTRICT.value:
                # Check if dependent objects exist
                source_table = quote_identifier(source_model.__tablename__)
                count_query = f"""
                    SELECT COUNT(*) FROM {source_table}
                    WHERE {fk_column} = $1
                """
                count = await db.fetchval(count_query, self._data['id'])
                
                if count > 0:
                    raise RestrictedError(
                        model_name=self.__class__.__name__,
                        related_model=source_model.__name__,
                        related_count=count,
                    )
            
            elif on_delete == OnDelete.SET_NULL.value:
                # Set FK to NULL on dependent objects
                source_table = quote_identifier(source_model.__tablename__)
                update_query = f"""
                    UPDATE {source_table}
                    SET {fk_column} = NULL
                    WHERE {fk_column} = $1
                """
                await db.execute(update_query, self._data['id'])
            
            # CASCADE is handled by database constraint
        table = quote_identifier(self.__tablename__)
        query = f"DELETE FROM {table} WHERE id = $1"
        await db.execute(query, self._data['id'])
        
        # Fire post_delete signal
        await post_delete.send(sender=self.__class__, instance=self)
    
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
        table = quote_identifier(cls.__tablename__)
        
        return f"""CREATE TABLE IF NOT EXISTS {table} (
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
