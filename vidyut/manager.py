"""
Query Manager and QuerySet

Django-like query interface for Vidyut models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, TYPE_CHECKING

if TYPE_CHECKING:
    from vidyut.model.base import Model

T = TypeVar("T", bound="Model")


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
    """
    
    def __init__(self, model: Type[T], filters: Optional[Dict[str, Any]] = None):
        """
        Initialize a QuerySet.
        
        Args:
            model: The model class to query
            filters: Dictionary of field=value filters
        """
        self._model = model
        self._filters = filters or {}
    
    def filter(self, **kwargs) -> "QuerySet[T]":
        """
        Add filter conditions to the query.
        
        Args:
            **kwargs: Field=value conditions (combined with AND)
            
        Returns:
            New QuerySet with additional filters
        """
        new_filters = {**self._filters, **kwargs}
        return QuerySet(self._model, new_filters)
    
    def _build_where_clause(self) -> tuple[str, list]:
        """
        Build WHERE clause from filters.
        
        Returns:
            Tuple of (WHERE clause string, parameter values list)
        """
        if not self._filters:
            return "", []
        
        conditions = []
        values = []
        
        for i, (field_name, value) in enumerate(self._filters.items(), 1):
            # Validate field exists
            if field_name not in self._model._fields:
                raise ValueError(f"Unknown field: {field_name}")
            
            field = self._model._fields[field_name]
            conditions.append(f"{field_name} = ${i}")
            values.append(field.to_db(value))
        
        return f"WHERE {' AND '.join(conditions)}", values
    
    async def all(self) -> List[T]:
        """
        Execute the query and return all matching records.
        
        Returns:
            List of model instances
        """
        from vidyut.db import Database
        
        db = Database.get_instance()
        
        where_clause, values = self._build_where_clause()
        query = f"SELECT * FROM {self._model.__tablename__} {where_clause}"
        
        records = await db.fetch(query, *values)
        
        return [self._model._from_record(record) for record in records]
    
    async def first(self) -> Optional[T]:
        """
        Execute the query and return the first matching record.
        
        Returns:
            First matching model instance or None
        """
        from vidyut.db import Database
        
        db = Database.get_instance()
        
        where_clause, values = self._build_where_clause()
        query = f"SELECT * FROM {self._model.__tablename__} {where_clause} LIMIT 1"
        
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
        query = f"SELECT COUNT(*) FROM {self._model.__tablename__} {where_clause}"
        
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
        query = f"DELETE FROM {self._model.__tablename__} {where_clause}"
        
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
