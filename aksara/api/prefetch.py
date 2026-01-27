"""
Aksara Prefetch Utilities for API Layer

Helpers for batched relation loading to avoid N+1 queries
in serializers and ViewSets.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from aksara.model.base import Model
    from aksara.api.serializers import ModelSerializer


async def prefetch_many_to_many(
    instances: List["Model"],
    field_name: str,
) -> None:
    """
    Batch load M2M related objects for a list of model instances.
    
    Performs a single query to load all related objects and attaches
    them to instance._prefetched_relations[field_name].
    
    Args:
        instances: List of model instances to prefetch for
        field_name: Name of the ManyToMany field
        
    Usage:
        posts = await Post.objects.all()
        await prefetch_many_to_many(posts, "tags")
        
        for post in posts:
            tags = post.get_prefetched_m2m("tags")  # No query!
    """
    if not instances:
        return
    
    from aksara.db import Database
    
    model_class = type(instances[0])
    
    # Validate field exists and is M2M
    if field_name not in model_class._m2m_fields:
        raise ValueError(
            f"'{field_name}' is not a ManyToMany field on {model_class.__name__}"
        )
    
    m2m_field = model_class._m2m_fields[field_name]
    related_model = m2m_field.to_model
    join_table = m2m_field.join_table_name
    
    # Get column names for join table
    source_table = model_class.__tablename__
    target_table = related_model.__tablename__
    
    def singularize(name: str) -> str:
        if name.endswith('ies'):
            return name[:-3] + 'y'
        return name.rstrip('s')
    
    source_col = f"{singularize(source_table)}_id"
    target_col = f"{singularize(target_table)}_id"
    
    # Collect all source IDs
    source_ids = [instance.id for instance in instances]
    
    if not source_ids:
        return
    
    db = Database.get_instance()
    
    # Batch query - join through table with target table
    placeholders = ", ".join(f"${i+1}" for i in range(len(source_ids)))
    m2m_query = f"""
        SELECT j.{source_col}, t.*
        FROM {join_table} j
        INNER JOIN {target_table} t ON t.id = j.{target_col}
        WHERE j.{source_col} IN ({placeholders})
    """
    
    records = await db.fetch(m2m_query, *source_ids)
    
    # Build mapping {source_id: [related_instances]}
    related_map: Dict[Any, List] = {sid: [] for sid in source_ids}
    for record in records:
        source_id = record[source_col]
        related_instance = related_model._from_record(record)
        related_map[source_id].append(related_instance)
    
    # Attach to each instance
    for instance in instances:
        instance._prefetched_relations[field_name] = related_map.get(instance.id, [])


async def prefetch_foreign_keys(
    instances: List["Model"],
    field_names: List[str],
) -> None:
    """
    Batch load FK/O2O related objects for a list of model instances.
    
    Args:
        instances: List of model instances to prefetch for
        field_names: Names of FK/O2O fields to prefetch
    """
    if not instances:
        return
    
    from aksara.db import Database
    
    model_class = type(instances[0])
    db = Database.get_instance()
    
    for field_name in field_names:
        # Validate field exists and is FK/O2O
        if field_name not in model_class._fk_fields:
            raise ValueError(
                f"'{field_name}' is not a ForeignKey/OneToOne field "
                f"on {model_class.__name__}"
            )
        
        field = model_class._fk_fields[field_name]
        related_model = field.to_model
        
        # Collect all FK IDs (filter out None)
        fk_ids = set()
        for instance in instances:
            fk_id = instance._data.get(field_name)
            if fk_id is not None:
                fk_ids.add(fk_id)
        
        if not fk_ids:
            # No FKs to load, set all to None
            for instance in instances:
                instance._prefetched_relations[field_name] = None
            continue
        
        # Batch query for all related objects
        placeholders = ", ".join(f"${i+1}" for i in range(len(fk_ids)))
        related_query = f"""
            SELECT * FROM {related_model.__tablename__}
            WHERE id IN ({placeholders})
        """
        
        related_records = await db.fetch(related_query, *list(fk_ids))
        
        # Build mapping {id: related_instance}
        related_map = {}
        for record in related_records:
            related_instance = related_model._from_record(record)
            related_map[related_instance.id] = related_instance
        
        # Attach to each instance
        for instance in instances:
            fk_id = instance._data.get(field_name)
            instance._prefetched_relations[field_name] = related_map.get(fk_id)


async def prefetch_for_serializer(
    instances: List["Model"],
    serializer_class: Type["ModelSerializer"],
) -> None:
    """
    Prefetch all expanded relations for a serializer.
    
    Analyzes the serializer's Meta.expand dict to determine which
    FK/O2O and M2M fields need to be prefetched, then performs
    batched queries for each.
    
    Args:
        instances: List of model instances to prefetch for
        serializer_class: The serializer class with expand config
        
    Usage:
        posts = await Post.objects.all()
        await prefetch_for_serializer(posts, PostSerializer)
        
        # Now serialization won't trigger N+1 queries
        data = [PostSerializer(instance=p).to_representation(p) for p in posts]
    """
    if not instances:
        return
    
    model_class = type(instances[0])
    
    # Get expand configuration from serializer
    expand_config = getattr(serializer_class.Meta, 'expand', {}) if hasattr(serializer_class, 'Meta') else {}
    
    if not expand_config:
        return
    
    fk_fields = []
    m2m_fields = []
    
    for field_name in expand_config.keys():
        if field_name in model_class._fk_fields:
            fk_fields.append(field_name)
        elif field_name in model_class._m2m_fields:
            m2m_fields.append(field_name)
    
    # Prefetch FK/O2O fields
    if fk_fields:
        await prefetch_foreign_keys(instances, fk_fields)
    
    # Prefetch M2M fields
    for m2m_field in m2m_fields:
        await prefetch_many_to_many(instances, m2m_field)


__all__ = [
    "prefetch_many_to_many",
    "prefetch_foreign_keys",
    "prefetch_for_serializer",
]
