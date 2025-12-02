"""
Vidyut Reverse Relations

Provides reverse relation access for FK, OneToOne, and ManyToMany fields.

Classes:
    - OnDelete: Enum for delete behavior policies
    - RelationRegistry: Tracks all model relations for reverse lookups
    - ReverseFKManager: Manager for accessing FK reverse relations (user.posts.all())
    - ReverseM2MManager: Manager for accessing M2M reverse relations (tag.posts.all())
    - ReverseFKDescriptor: Descriptor that returns ReverseFKManager for FK reverse
    - ReverseM2MDescriptor: Descriptor that returns ReverseM2MManager for M2M reverse
    - ReverseO2ODescriptor: Descriptor for OneToOne reverse (user.profile())

Usage:
    # Forward relations (already supported)
    post.author_id  # FK value
    await post.tags.all()  # M2M forward
    
    # Reverse relations (new in v0.3.8)
    await user.posts.all()  # FK reverse
    await tag.posts.all()  # M2M reverse
    await user.profile()  # O2O reverse
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, Union

if TYPE_CHECKING:
    from vidyut.model.base import Model


class OnDelete(str, Enum):
    """
    Delete behavior policies for FK and OneToOne relations.
    
    Values:
        CASCADE: Delete related objects when parent is deleted
        SET_NULL: Set FK to NULL when parent is deleted (requires nullable=True)
        RESTRICT: Prevent deletion if related objects exist
        PROTECT: Alias for RESTRICT
    """
    CASCADE = "CASCADE"
    SET_NULL = "SET NULL"
    RESTRICT = "RESTRICT"
    PROTECT = "RESTRICT"  # Alias
    
    def __str__(self) -> str:
        return self.value


class RelationMeta:
    """
    Metadata about a relation between two models.
    
    Attributes:
        relation_type: "fk", "o2o", or "m2m"
        source_model: The model where the field is defined
        target_model: The model being referenced
        field_name: Name of the field on source model
        related_name: Name for reverse access on target model
        source_table: Database table name of source model
        target_table: Database table name of target model
        through_table: Join table name (for M2M only)
        on_delete: Delete behavior policy (for FK/O2O)
    """
    
    def __init__(
        self,
        relation_type: str,
        source_model: Type["Model"],
        target_model: Type["Model"],
        field_name: str,
        related_name: str,
        on_delete: Optional[str] = None,
        through_table: Optional[str] = None,
    ):
        self.relation_type = relation_type
        self.source_model = source_model
        self.target_model = target_model
        self.field_name = field_name
        self.related_name = related_name
        self.on_delete = on_delete
        self.through_table = through_table
    
    @property
    def source_table(self) -> str:
        return self.source_model.__tablename__
    
    @property
    def target_table(self) -> str:
        return self.target_model.__tablename__
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.relation_type,
            "source_model": self.source_model.__name__,
            "target_model": self.target_model.__name__,
            "field_name": self.field_name,
            "related_name": self.related_name,
            "source_table": self.source_table,
            "target_table": self.target_table,
            "through_table": self.through_table,
            "on_delete": self.on_delete,
        }


class RelationRegistry:
    """
    Registry to track all model relations for reverse lookups.
    
    Relations are registered when models are created, and used
    to attach reverse descriptors to target models.
    """
    
    _relations: List[RelationMeta] = []
    _reverse_attrs_attached: bool = False
    
    @classmethod
    def register(cls, relation: RelationMeta) -> None:
        """Register a relation."""
        cls._relations.append(relation)
    
    @classmethod
    def get_relations_to(cls, target_model: Type["Model"]) -> List[RelationMeta]:
        """Get all relations pointing to a target model."""
        return [
            r for r in cls._relations 
            if r.target_model == target_model
        ]
    
    @classmethod
    def get_relations_from(cls, source_model: Type["Model"]) -> List[RelationMeta]:
        """Get all relations from a source model."""
        return [
            r for r in cls._relations 
            if r.source_model == source_model
        ]
    
    @classmethod
    def all(cls) -> List[RelationMeta]:
        """Get all registered relations."""
        return cls._relations.copy()
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered relations (for testing)."""
        cls._relations.clear()
        cls._reverse_attrs_attached = False
    
    @classmethod
    def attach_reverse_descriptors(cls) -> None:
        """
        Attach reverse descriptors to all target models.
        
        Called after all models are defined to set up reverse access.
        """
        if cls._reverse_attrs_attached:
            return
        
        for relation in cls._relations:
            target_model = relation.target_model
            related_name = relation.related_name
            
            # Check for attribute collision
            if hasattr(target_model, related_name):
                existing = getattr(target_model, related_name)
                # Allow if it's already a reverse descriptor
                if isinstance(existing, (ReverseFKDescriptor, ReverseM2MDescriptor, ReverseO2ODescriptor)):
                    continue
                raise AttributeError(
                    f"Cannot attach reverse relation '{related_name}' on {target_model.__name__}: "
                    f"attribute already exists. Use a different related_name."
                )
            
            # Attach appropriate descriptor
            if relation.relation_type == "fk":
                setattr(
                    target_model,
                    related_name,
                    ReverseFKDescriptor(relation),
                )
            elif relation.relation_type == "o2o":
                setattr(
                    target_model,
                    related_name,
                    ReverseO2ODescriptor(relation),
                )
            elif relation.relation_type == "m2m":
                setattr(
                    target_model,
                    related_name,
                    ReverseM2MDescriptor(relation),
                )
        
        cls._reverse_attrs_attached = True


class ReverseFKManager:
    """
    Manager for accessing reverse FK relations.
    
    Example:
        posts = await user.posts.all()
        # Executes: SELECT * FROM posts WHERE author_id = <user.id>
    """
    
    def __init__(
        self,
        relation: RelationMeta,
        instance: "Model",
    ):
        self._relation = relation
        self._instance = instance
        self._source_model = relation.source_model
        self._field_name = relation.field_name
    
    async def all(self) -> List["Model"]:
        """Get all related objects."""
        from vidyut.db import Database
        from vidyut.fields import ForeignKey
        
        db = Database.get_instance()
        
        # Get the FK column name
        field = self._source_model._fields.get(self._field_name)
        if isinstance(field, ForeignKey):
            fk_column = field.db_column_name
        else:
            fk_column = f"{self._field_name}_id"
        
        query = f"""
            SELECT * FROM {self._source_model.__tablename__}
            WHERE {fk_column} = $1
            ORDER BY created_at DESC
        """
        
        records = await db.fetch(query, self._instance.id)
        return [self._source_model._from_record(r) for r in records]
    
    async def count(self) -> int:
        """Count related objects."""
        from vidyut.db import Database
        from vidyut.fields import ForeignKey
        
        db = Database.get_instance()
        
        field = self._source_model._fields.get(self._field_name)
        if isinstance(field, ForeignKey):
            fk_column = field.db_column_name
        else:
            fk_column = f"{self._field_name}_id"
        
        query = f"""
            SELECT COUNT(*) FROM {self._source_model.__tablename__}
            WHERE {fk_column} = $1
        """
        
        return await db.fetchval(query, self._instance.id)
    
    async def filter(self, **kwargs) -> List["Model"]:
        """Filter related objects."""
        # Basic filter implementation
        all_objects = await self.all()
        result = []
        
        for obj in all_objects:
            match = True
            for key, value in kwargs.items():
                if getattr(obj, key, None) != value:
                    match = False
                    break
            if match:
                result.append(obj)
        
        return result


class ReverseM2MManager:
    """
    Manager for accessing reverse M2M relations.
    
    Example:
        posts = await tag.posts.all()
        # Executes: SELECT posts.* FROM posts 
        #           JOIN post_tags ON posts.id = post_tags.post_id 
        #           WHERE post_tags.tag_id = <tag.id>
    """
    
    def __init__(
        self,
        relation: RelationMeta,
        instance: "Model",
    ):
        self._relation = relation
        self._instance = instance
        self._source_model = relation.source_model
        self._through_table = relation.through_table
    
    def _get_column_names(self) -> tuple:
        """Get the join table column names."""
        source_table = self._relation.source_table
        target_table = self._relation.target_table
        
        # Convert table names to column names (posts -> post_id)
        def singularize(name: str) -> str:
            if name.endswith('ies'):
                return name[:-3] + 'y'
            return name.rstrip('s')
        
        source_col = f"{singularize(source_table)}_id"
        target_col = f"{singularize(target_table)}_id"
        
        return source_col, target_col
    
    async def all(self) -> List["Model"]:
        """Get all related objects."""
        from vidyut.db import Database
        
        db = Database.get_instance()
        
        source_col, target_col = self._get_column_names()
        source_table = self._relation.source_table
        
        query = f"""
            SELECT s.* FROM {source_table} s
            INNER JOIN {self._through_table} j ON s.id = j.{source_col}
            WHERE j.{target_col} = $1
            ORDER BY s.created_at DESC
        """
        
        records = await db.fetch(query, self._instance.id)
        return [self._source_model._from_record(r) for r in records]
    
    async def count(self) -> int:
        """Count related objects."""
        from vidyut.db import Database
        
        db = Database.get_instance()
        
        _, target_col = self._get_column_names()
        
        query = f"""
            SELECT COUNT(*) FROM {self._through_table}
            WHERE {target_col} = $1
        """
        
        return await db.fetchval(query, self._instance.id)


class ReverseFKDescriptor:
    """
    Descriptor for accessing reverse FK relations.
    
    When accessed on an instance, returns a ReverseFKManager.
    When accessed on the class, returns the descriptor itself.
    """
    
    def __init__(self, relation: RelationMeta):
        self._relation = relation
    
    def __get__(self, instance: Optional["Model"], owner: Type["Model"]) -> Union["ReverseFKDescriptor", ReverseFKManager]:
        if instance is None:
            return self
        return ReverseFKManager(self._relation, instance)
    
    def __repr__(self) -> str:
        return f"<ReverseFKDescriptor: {self._relation.target_model.__name__}.{self._relation.related_name}>"


class ReverseM2MDescriptor:
    """
    Descriptor for accessing reverse M2M relations.
    
    When accessed on an instance, returns a ReverseM2MManager.
    When accessed on the class, returns the descriptor itself.
    """
    
    def __init__(self, relation: RelationMeta):
        self._relation = relation
    
    def __get__(self, instance: Optional["Model"], owner: Type["Model"]) -> Union["ReverseM2MDescriptor", ReverseM2MManager]:
        if instance is None:
            return self
        return ReverseM2MManager(self._relation, instance)
    
    def __repr__(self) -> str:
        return f"<ReverseM2MDescriptor: {self._relation.target_model.__name__}.{self._relation.related_name}>"


class ReverseO2ODescriptor:
    """
    Descriptor for accessing reverse OneToOne relations.
    
    Returns an async callable that fetches the related object.
    
    Usage:
        profile = await user.profile()
    """
    
    def __init__(self, relation: RelationMeta):
        self._relation = relation
    
    def __get__(self, instance: Optional["Model"], owner: Type["Model"]) -> Union["ReverseO2ODescriptor", "ReverseO2OAccessor"]:
        if instance is None:
            return self
        return ReverseO2OAccessor(self._relation, instance)
    
    def __repr__(self) -> str:
        return f"<ReverseO2ODescriptor: {self._relation.target_model.__name__}.{self._relation.related_name}>"


class ReverseO2OAccessor:
    """
    Async callable for fetching OneToOne reverse relation.
    
    Can be called directly: profile = await user.profile()
    Or accessed: accessor = user.profile; profile = await accessor()
    """
    
    def __init__(self, relation: RelationMeta, instance: "Model"):
        self._relation = relation
        self._instance = instance
        self._source_model = relation.source_model
        self._field_name = relation.field_name
    
    async def __call__(self) -> Optional["Model"]:
        """Fetch the related OneToOne object."""
        from vidyut.db import Database
        from vidyut.fields import ForeignKey
        from vidyut.manager import DoesNotExist
        
        db = Database.get_instance()
        
        # Get the FK column name
        field = self._source_model._fields.get(self._field_name)
        if isinstance(field, ForeignKey):
            fk_column = field.db_column_name
        else:
            fk_column = f"{self._field_name}_id"
        
        query = f"""
            SELECT * FROM {self._source_model.__tablename__}
            WHERE {fk_column} = $1
            LIMIT 1
        """
        
        record = await db.fetchrow(query, self._instance.id)
        
        if record is None:
            return None
        
        return self._source_model._from_record(record)
    
    async def get(self) -> "Model":
        """
        Fetch the related object, raising DoesNotExist if not found.
        """
        from vidyut.manager import DoesNotExist
        
        result = await self()
        if result is None:
            raise DoesNotExist(
                f"{self._source_model.__name__} matching query does not exist."
            )
        return result
    
    def __repr__(self) -> str:
        return f"<ReverseO2OAccessor: {self._relation.source_model.__name__} via {self._field_name}>"


def get_default_related_name(source_model: Type["Model"], relation_type: str) -> str:
    """
    Generate default related_name for a relation.
    
    Pattern:
        - FK/M2M: "{source_model_name_lower}_set" (e.g., "post_set")
        - O2O: "{source_model_name_lower}" (e.g., "profile")
    """
    model_name = source_model.__name__.lower()
    
    if relation_type == "o2o":
        return model_name
    else:
        return f"{model_name}_set"


def register_relation(
    relation_type: str,
    source_model: Type["Model"],
    target_model: Type["Model"],
    field_name: str,
    related_name: Optional[str] = None,
    on_delete: Optional[str] = None,
    through_table: Optional[str] = None,
) -> RelationMeta:
    """
    Register a relation and return its metadata.
    
    Args:
        relation_type: "fk", "o2o", or "m2m"
        source_model: The model where the field is defined
        target_model: The model being referenced
        field_name: Name of the field on source model
        related_name: Name for reverse access (auto-generated if None)
        on_delete: Delete behavior (for FK/O2O)
        through_table: Join table name (for M2M)
    """
    if related_name is None:
        related_name = get_default_related_name(source_model, relation_type)
    
    relation = RelationMeta(
        relation_type=relation_type,
        source_model=source_model,
        target_model=target_model,
        field_name=field_name,
        related_name=related_name,
        on_delete=on_delete,
        through_table=through_table,
    )
    
    RelationRegistry.register(relation)
    return relation


__all__ = [
    "OnDelete",
    "RelationMeta",
    "RelationRegistry",
    "ReverseFKManager",
    "ReverseM2MManager",
    "ReverseFKDescriptor",
    "ReverseM2MDescriptor",
    "ReverseO2ODescriptor",
    "ReverseO2OAccessor",
    "get_default_related_name",
    "register_relation",
]
