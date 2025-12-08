"""
Query Manager and QuerySet

Django-like query interface for Vidyut models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, Tuple, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from vidyut.model.base import Model

from vidyut.db import quote_identifier
from vidyut.exceptions import ConfigurationError

T = TypeVar("T", bound="Model")


# Supported lookup types
LOOKUP_OPERATORS = {
    "exact": "=",          # field__exact=value (same as field=value)
    "gt": ">",             # field__gt=value
    "gte": ">=",           # field__gte=value
    "lt": "<",             # field__lt=value
    "lte": "<=",           # field__lte=value
    "in": "IN",            # field__in=[v1, v2]
    "isnull": "IS NULL",   # field__isnull=True/False
    "icontains": "ILIKE",  # field__icontains="substring"
    "contains": "LIKE",    # field__contains="substring"
}


def parse_lookup(key: str) -> Tuple[str, str]:
    """
    Parse a filter key into field name and lookup type.
    
    Args:
        key: Filter key like "email" or "age__gte"
        
    Returns:
        Tuple of (field_name, lookup_type)
    """
    if "__" in key:
        parts = key.rsplit("__", 1)
        field_name, lookup = parts[0], parts[1]
        if lookup in LOOKUP_OPERATORS:
            return field_name, lookup
        # If lookup not recognized, treat entire key as field name (exact match)
        return key, "exact"
    return key, "exact"


class QuerySet(Generic[T]):
    """
    Lazy query builder for filtering and fetching model instances.
    
    QuerySets are lazy - they don't execute until you call a terminal
    method like .all(), .first(), or .count().
    
    Usage:
        # Get all active users
        users = await User.objects.filter(is_active=True).all()
        
        # Get first matching user
        user = await User.objects.filter(email="test@example.com").first()
        
        # Count matching records
        count = await User.objects.filter(is_active=True).count()
        
        # Advanced lookups
        users = await User.objects.filter(
            age__gte=18,
            email__icontains="@gmail.com",
            status__in=["active", "pending"],
        ).all()
        
        # Ordering
        users = await User.objects.order_by("email").all()           # Ascending
        users = await User.objects.order_by("-created_at").all()     # Descending
        users = await User.objects.order_by("is_active", "-email").all()  # Multiple
        
        # Chained with filter
        users = await User.objects.filter(is_active=True).order_by("email").all()
        
        # Preload FK/O2O relations (avoids N+1)
        posts = await Post.objects.select_related("author").all()
        for p in posts:
            _ = p.author  # No additional query!
    """
    
    def __init__(
        self,
        model: Type[T],
        filters: Optional[Dict[str, Any]] = None,
        select_related_fields: Optional[Set[str]] = None,
        prefetch_related_fields: Optional[Set[str]] = None,
        order_by_fields: Optional[List[str]] = None,
    ):
        """
        Initialize a QuerySet.
        
        Args:
            model: The model class to query
            filters: Dictionary of field=value or field__lookup=value filters
            select_related_fields: Set of FK/O2O fields to eagerly load
            prefetch_related_fields: Set of M2M fields to eagerly load
            order_by_fields: List of field names for ordering (prefix with - for descending)
        """
        self._model = model
        self._filters = filters or {}
        self._select_related: Set[str] = select_related_fields or set()
        self._prefetch_related: Set[str] = prefetch_related_fields or set()
        self._order_by: Optional[List[str]] = order_by_fields
    
    def filter(self, **kwargs) -> "QuerySet[T]":
        """
        Add filter conditions to the query.
        
        Supports lookups:
            - field=value (exact match)
            - field__gt=value (greater than)
            - field__gte=value (greater than or equal)
            - field__lt=value (less than)
            - field__lte=value (less than or equal)
            - field__in=[v1, v2, ...] (membership)
            - field__isnull=True/False (null check)
            - field__icontains="substring" (case-insensitive contains)
            - field__contains="substring" (case-sensitive contains)
        
        Args:
            **kwargs: Field=value or field__lookup=value conditions (combined with AND)
            
        Returns:
            New QuerySet with additional filters
        """
        new_filters = {**self._filters, **kwargs}
        return QuerySet(
            self._model,
            new_filters,
            self._select_related.copy(),
            self._prefetch_related.copy(),
            self._order_by.copy() if self._order_by else None,
        )
    
    def order_by(self, *fields: str) -> "QuerySet[T]":
        """
        Specify ordering for the query results.
        
        Fields can be specified as:
            - "field_name" for ascending order
            - "-field_name" for descending order
        
        Multiple fields can be specified; ordering is applied in order.
        Calling order_by() again replaces previous ordering.
        
        Args:
            *fields: Field names to order by (prefix with - for descending)
            
        Returns:
            New QuerySet with ordering applied
            
        Raises:
            ConfigurationError: If no fields provided or field doesn't exist
            
        Usage:
            # Ascending
            User.objects.order_by("email")
            
            # Descending
            User.objects.order_by("-created_at")
            
            # Multiple fields
            User.objects.order_by("is_active", "-created_at")
            
            # Chained (later call replaces earlier)
            User.objects.order_by("email").order_by("-created_at")  # final: created_at DESC
        """
        if not fields:
            raise ConfigurationError(
                "order_by() requires at least one field. "
                "Usage: .order_by('field') or .order_by('-field')"
            )
        
        # Validate each field
        validated_fields = []
        for field in fields:
            if not isinstance(field, str):
                raise ConfigurationError(
                    f"order_by() fields must be strings, got {type(field).__name__}"
                )
            
            # Parse descending prefix
            if field.startswith("-"):
                field_name = field[1:]
                if field_name.startswith("-"):
                    # Double minus like "--email" is invalid
                    raise ConfigurationError(
                        f"Invalid order_by field '{field}'. "
                        f"Use '-{field_name[1:]}' for descending order."
                    )
            else:
                field_name = field
            
            if not field_name:
                raise ConfigurationError(
                    "order_by() field name cannot be empty"
                )
            
            # Check if field exists on model
            # Allow 'id' as it's always present
            field_valid = False
            
            if field_name == "id":
                field_valid = True
            elif field_name in self._model._fields:
                field_valid = True
            elif field_name.endswith("_id"):
                # Check if it's a FK column name (e.g., author_id for FK field 'author')
                base_field_name = field_name[:-3]  # Remove _id suffix
                if base_field_name in self._model._fields:
                    # Verify it's actually a FK field with this column name
                    base_field = self._model._fields[base_field_name]
                    if hasattr(base_field, 'column_name') and base_field.column_name == field_name:
                        field_valid = True
            
            if not field_valid:
                available_fields = sorted(self._model._fields.keys())
                # Also add _id variants for FK fields
                fk_columns = []
                for fname, fobj in self._model._fields.items():
                    if hasattr(fobj, 'column_name') and fobj.column_name != fname:
                        fk_columns.append(fobj.column_name)
                all_orderable = sorted(set(available_fields + fk_columns))
                raise ConfigurationError(
                    f"Cannot order by '{field_name}' - field does not exist on {self._model.__name__}. "
                    f"Available fields: {', '.join(all_orderable)}"
                )
            
            validated_fields.append(field)
        
        return QuerySet(
            self._model,
            self._filters.copy(),
            self._select_related.copy(),
            self._prefetch_related.copy(),
            validated_fields,
        )
    
    def select_related(self, *fields: str) -> "QuerySet[T]":
        """
        Mark ForeignKey / OneToOne fields to be eagerly loaded.
        
        Uses batched queries to avoid N+1 problems. After the main query,
        a single additional query fetches all related objects.
        
        Args:
            *fields: Names of FK/O2O fields to preload
            
        Returns:
            New QuerySet with select_related fields added
            
        Usage:
            # Single field
            posts = await Post.objects.select_related("author").all()
            
            # Multiple fields
            posts = await Post.objects.select_related("author", "category").all()
            
            # Chained
            posts = await Post.objects.select_related("author").select_related("category").all()
        """
        new_select_related = self._select_related | set(fields)
        return QuerySet(
            self._model,
            self._filters.copy(),
            new_select_related,
            self._prefetch_related.copy(),
            self._order_by.copy() if self._order_by else None,
        )
    
    def prefetch_related(self, *fields: str) -> "QuerySet[T]":
        """
        Mark ManyToMany fields to be eagerly loaded.
        
        Uses batched queries to avoid N+1 problems.
        
        Args:
            *fields: Names of M2M fields to preload
            
        Returns:
            New QuerySet with prefetch_related fields added
        """
        new_prefetch_related = self._prefetch_related | set(fields)
        return QuerySet(
            self._model,
            self._filters.copy(),
            self._select_related.copy(),
            new_prefetch_related,
            self._order_by.copy() if self._order_by else None,
        )
    
    def _build_where_clause(self) -> Tuple[str, List]:
        """
        Build WHERE clause from filters.
        
        Returns:
            Tuple of (WHERE clause string, parameter values list)
        """
        if not self._filters:
            return "", []
        
        conditions = []
        values = []
        param_idx = 1
        
        for key, value in self._filters.items():
            field_name, lookup = parse_lookup(key)
            
            # Validate field exists
            if field_name not in self._model._fields:
                raise ValueError(f"Unknown field: {field_name}")
            
            field = self._model._fields[field_name]
            # Use the actual database column name (e.g., author_id for ForeignKey)
            col_name = field.column_name
            
            # Build condition based on lookup type
            if lookup == "exact":
                conditions.append(f"{col_name} = ${param_idx}")
                values.append(field.to_db(value))
                param_idx += 1
            
            elif lookup == "gt":
                conditions.append(f"{col_name} > ${param_idx}")
                values.append(field.to_db(value))
                param_idx += 1
            
            elif lookup == "gte":
                conditions.append(f"{col_name} >= ${param_idx}")
                values.append(field.to_db(value))
                param_idx += 1
            
            elif lookup == "lt":
                conditions.append(f"{col_name} < ${param_idx}")
                values.append(field.to_db(value))
                param_idx += 1
            
            elif lookup == "lte":
                conditions.append(f"{col_name} <= ${param_idx}")
                values.append(field.to_db(value))
                param_idx += 1
            
            elif lookup == "in":
                if not isinstance(value, (list, tuple, set)):
                    raise ValueError(f"__in lookup requires a list, got {type(value)}")
                if not value:
                    # Empty list - nothing can match
                    conditions.append("FALSE")
                else:
                    placeholders = []
                    for item in value:
                        placeholders.append(f"${param_idx}")
                        values.append(field.to_db(item))
                        param_idx += 1
                    conditions.append(f"{col_name} IN ({', '.join(placeholders)})")
            
            elif lookup == "isnull":
                if value:
                    conditions.append(f"{col_name} IS NULL")
                else:
                    conditions.append(f"{col_name} IS NOT NULL")
            
            elif lookup == "icontains":
                conditions.append(f"{col_name} ILIKE ${param_idx}")
                values.append(f"%{value}%")
                param_idx += 1
            
            elif lookup == "contains":
                conditions.append(f"{col_name} LIKE ${param_idx}")
                values.append(f"%{value}%")
                param_idx += 1
            
            else:
                raise ValueError(f"Unknown lookup type: {lookup}")
        
        return f"WHERE {' AND '.join(conditions)}", values
    
    def _build_order_by_clause(self) -> str:
        """
        Build ORDER BY clause from ordering fields.
        
        Returns:
            ORDER BY clause string (empty if no ordering)
        """
        if not self._order_by:
            return ""
        
        order_parts = []
        for field in self._order_by:
            # Parse descending prefix
            if field.startswith("-"):
                field_name = field[1:]
                direction = "DESC"
            else:
                field_name = field
                direction = "ASC"
            
            # Get column name
            if field_name == "id":
                col_name = "id"
            elif field_name in self._model._fields:
                col_name = self._model._fields[field_name].column_name
            elif field_name.endswith("_id"):
                # Check if it's a FK column name (e.g., author_id for FK field 'author')
                base_field_name = field_name[:-3]
                if base_field_name in self._model._fields:
                    # Use the field's column_name (which should be field_name)
                    col_name = self._model._fields[base_field_name].column_name
                else:
                    col_name = field_name  # Fallback
            else:
                col_name = field_name  # Fallback (should have been validated)
            
            order_parts.append(f"{col_name} {direction}")
        
        return f"ORDER BY {', '.join(order_parts)}"
    
    async def all(self) -> List[T]:
        """
        Execute the query and return all matching records.
        
        Returns:
            List of model instances
        """
        from vidyut.db import Database
        
        db = Database.get_instance()
        
        where_clause, values = self._build_where_clause()
        order_by_clause = self._build_order_by_clause()
        table = quote_identifier(self._model.__tablename__)
        query = f"SELECT * FROM {table} {where_clause} {order_by_clause}".strip()
        
        records = await db.fetch(query, *values)
        
        instances = [self._model._from_record(record) for record in records]
        
        # Handle select_related - batch load FK/O2O relations
        if self._select_related and instances:
            await self._load_select_related(instances, db)
        
        # Handle prefetch_related - batch load M2M relations
        if self._prefetch_related and instances:
            await self._load_prefetch_related(instances, db)
        
        return instances
    
    async def _load_select_related(self, instances: List[T], db) -> None:
        """
        Batch load FK/O2O related objects for all instances.
        
        For each select_related field:
        1. Collect all FK IDs from instances
        2. Run a single query to fetch all related objects
        3. Build a mapping {id: related_instance}
        4. Attach to each instance._prefetched_relations
        """
        from vidyut.fields import ForeignKey, OneToOne
        
        for field_name in self._select_related:
            # Validate field exists and is FK/O2O
            if field_name not in self._model._fk_fields:
                raise ValueError(
                    f"select_related: '{field_name}' is not a ForeignKey/OneToOne field "
                    f"on {self._model.__name__}"
                )
            
            field = self._model._fk_fields[field_name]
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
            related_table = quote_identifier(related_model.__tablename__)
            related_query = f"""
                SELECT * FROM {related_table}
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
    
    async def _load_prefetch_related(self, instances: List[T], db) -> None:
        """
        Batch load M2M related objects for all instances.
        
        For each prefetch_related field:
        1. Collect all source IDs
        2. Query through table with JOIN
        3. Build a mapping {source_id: [related_instances]}
        4. Attach to each instance._prefetched_relations
        """
        for field_name in self._prefetch_related:
            # Validate field exists and is M2M
            if field_name not in self._model._m2m_fields:
                raise ValueError(
                    f"prefetch_related: '{field_name}' is not a ManyToMany field "
                    f"on {self._model.__name__}"
                )
            
            m2m_field = self._model._m2m_fields[field_name]
            related_model = m2m_field.to_model
            join_table = m2m_field.join_table_name
            
            # Get column names for join table
            source_table = self._model.__tablename__
            target_table = related_model.__tablename__
            
            # Singularize table names for column names
            def singularize(name: str) -> str:
                if name.endswith('ies'):
                    return name[:-3] + 'y'
                return name.rstrip('s')
            
            source_col = f"{singularize(source_table)}_id"
            target_col = f"{singularize(target_table)}_id"
            
            # Collect all source IDs
            source_ids = [instance.id for instance in instances]
            
            if not source_ids:
                continue
            
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
                # Create instance from record (excluding the source_col)
                related_instance = related_model._from_record(record)
                related_map[source_id].append(related_instance)
            
            # Attach to each instance
            for instance in instances:
                instance._prefetched_relations[field_name] = related_map.get(instance.id, [])
    
    async def first(self) -> Optional[T]:
        """
        Execute the query and return the first matching record.
        
        Returns:
            First matching model instance or None
        """
        from vidyut.db import Database
        
        db = Database.get_instance()
        
        where_clause, values = self._build_where_clause()
        order_by_clause = self._build_order_by_clause()
        table = quote_identifier(self._model.__tablename__)
        query = f"SELECT * FROM {table} {where_clause} {order_by_clause} LIMIT 1".strip()
        # Clean up any double spaces
        query = " ".join(query.split())
        
        record = await db.fetchrow(query, *values)
        
        if record is None:
            return None
        
        return self._model._from_record(record)
    
    async def count(self) -> int:
        """
        Execute the query and return the count of matching records.
        
        Returns:
            Number of matching records
        """
        from vidyut.db import Database
        
        db = Database.get_instance()
        
        where_clause, values = self._build_where_clause()
        table = quote_identifier(self._model.__tablename__)
        query = f"SELECT COUNT(*) FROM {table} {where_clause}"
        
        count = await db.fetchval(query, *values)
        
        return count or 0
    
    async def exists(self) -> bool:
        """
        Check if any matching records exist.
        
        Returns:
            True if at least one record matches, False otherwise
        """
        return await self.count() > 0
    
    async def delete(self) -> int:
        """
        Delete all matching records.
        
        Returns:
            Number of deleted records
        """
        from vidyut.db import Database
        
        db = Database.get_instance()
        
        where_clause, values = self._build_where_clause()
        table = quote_identifier(self._model.__tablename__)
        query = f"DELETE FROM {table} {where_clause}"
        
        result = await db.execute(query, *values)
        
        # Parse "DELETE X" to get count
        try:
            return int(result.split()[-1])
        except (IndexError, ValueError):
            return 0


class Manager(Generic[T]):
    """
    Manager class attached to each Model for querying.
    
    Accessed via Model.objects, provides the entry point for all queries.
    
    Usage:
        # Create a new record
        user = await User.objects.create(email="test@example.com")
        
        # Get a specific record
        user = await User.objects.get(id=user_id)
        
        # Filter records
        users = await User.objects.filter(is_active=True).all()
    """
    
    def __init__(self, model: Type[T]):
        """
        Initialize the manager.
        
        Args:
            model: The model class this manager is attached to
        """
        self._model = model
    
    def filter(self, **kwargs) -> QuerySet[T]:
        """
        Create a QuerySet with the given filters.
        
        Args:
            **kwargs: Field=value conditions
            
        Returns:
            QuerySet for chaining
        """
        return QuerySet(self._model, kwargs)
    
    def order_by(self, *fields: str) -> QuerySet[T]:
        """
        Create a QuerySet with ordering.
        
        Args:
            *fields: Field names to order by (prefix with - for descending)
            
        Returns:
            QuerySet for chaining
            
        Usage:
            User.objects.order_by("email")           # Ascending
            User.objects.order_by("-created_at")     # Descending
            User.objects.order_by("is_active", "-email")  # Multiple
        """
        return QuerySet(self._model).order_by(*fields)
    
    def select_related(self, *fields: str) -> QuerySet[T]:
        """
        Create a QuerySet with select_related fields.
        
        Args:
            *fields: FK/O2O field names to preload
            
        Returns:
            QuerySet for chaining
        """
        return QuerySet(self._model).select_related(*fields)
    
    def prefetch_related(self, *fields: str) -> QuerySet[T]:
        """
        Create a QuerySet with prefetch_related fields.
        
        Args:
            *fields: M2M field names to preload
            
        Returns:
            QuerySet for chaining
        """
        return QuerySet(self._model).prefetch_related(*fields)
    
    async def all(self) -> List[T]:
        """
        Get all records.
        
        Returns:
            List of all model instances
        """
        return await QuerySet(self._model).all()
    
    async def create(self, **kwargs) -> T:
        """
        Create and save a new model instance.
        
        Args:
            **kwargs: Field values for the new instance
            
        Returns:
            The created model instance
        """
        instance = self._model(**kwargs)
        await instance.save()
        return instance
    
    async def get(self, **kwargs) -> T:
        """
        Get a single record matching the given conditions.
        
        Args:
            **kwargs: Field=value conditions
            
        Returns:
            The matching model instance
            
        Raises:
            DoesNotExist: If no matching record is found
            MultipleObjectsReturned: If multiple records match
        """
        queryset = QuerySet(self._model, kwargs)
        results = await queryset.all()
        
        if len(results) == 0:
            raise DoesNotExist(f"{self._model.__name__} matching query does not exist")
        
        if len(results) > 1:
            raise MultipleObjectsReturned(
                f"get() returned {len(results)} {self._model.__name__} instances, expected 1"
            )
        
        return results[0]
    
    async def get_or_none(self, **kwargs) -> Optional[T]:
        """
        Get a single record or None if not found.
        
        Args:
            **kwargs: Field=value conditions
            
        Returns:
            The matching model instance or None
        """
        try:
            return await self.get(**kwargs)
        except DoesNotExist:
            return None
    
    async def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple[T, bool]:
        """
        Get an existing record or create a new one.
        
        Args:
            defaults: Field values to use when creating
            **kwargs: Field=value conditions for lookup
            
        Returns:
            Tuple of (instance, created) where created is True if new
        """
        try:
            instance = await self.get(**kwargs)
            return instance, False
        except DoesNotExist:
            create_kwargs = {**kwargs, **(defaults or {})}
            instance = await self.create(**create_kwargs)
            return instance, True
    
    async def count(self) -> int:
        """
        Count all records.
        
        Returns:
            Total number of records
        """
        return await QuerySet(self._model).count()


class DoesNotExist(Exception):
    """Raised when a query returns no results."""
    pass


class MultipleObjectsReturned(Exception):
    """Raised when get() returns multiple results."""
    pass
