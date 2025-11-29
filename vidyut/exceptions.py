"""
Vidyut Exceptions

Custom exception hierarchy for Vidyut ORM.
Maps database errors to semantic Vidyut exceptions.
"""

from __future__ import annotations

from typing import Any, Optional


class VidyutError(Exception):
    """Base exception for all Vidyut errors."""
    
    def __init__(self, message: str = "", *args: Any, **kwargs: Any):
        self.message = message
        super().__init__(message, *args)


class ConfigurationError(VidyutError):
    """Raised when Vidyut is misconfigured."""
    pass


class DatabaseError(VidyutError):
    """
    Base exception for database-related errors.
    
    Wraps underlying asyncpg exceptions with more context.
    """
    
    def __init__(
        self,
        message: str = "",
        *,
        original_exception: Optional[Exception] = None,
        query: Optional[str] = None,
        params: Optional[tuple] = None,
    ):
        self.original_exception = original_exception
        self.query = query
        self.params = params
        super().__init__(message)
    
    def __str__(self) -> str:
        parts = [self.message]
        if self.query:
            parts.append(f"Query: {self.query[:200]}...")
        return " | ".join(parts)


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""
    pass


class UniqueConstraintError(DatabaseError):
    """
    Raised when a unique constraint is violated.
    
    Attributes:
        field_name: The field that caused the violation (if detectable)
        value: The value that caused the violation (if available)
    """
    
    def __init__(
        self,
        message: str = "Unique constraint violated",
        *,
        field_name: Optional[str] = None,
        value: Any = None,
        **kwargs: Any,
    ):
        self.field_name = field_name
        self.value = value
        super().__init__(message, **kwargs)
    
    def __str__(self) -> str:
        if self.field_name:
            return f"Unique constraint violated on field '{self.field_name}'"
        return self.message


class ForeignKeyConstraintError(DatabaseError):
    """
    Raised when a foreign key constraint is violated.
    
    Attributes:
        field_name: The FK field that caused the violation
        referenced_table: The table being referenced
    """
    
    def __init__(
        self,
        message: str = "Foreign key constraint violated",
        *,
        field_name: Optional[str] = None,
        referenced_table: Optional[str] = None,
        **kwargs: Any,
    ):
        self.field_name = field_name
        self.referenced_table = referenced_table
        super().__init__(message, **kwargs)
    
    def __str__(self) -> str:
        if self.field_name and self.referenced_table:
            return f"Foreign key constraint violated: '{self.field_name}' references '{self.referenced_table}'"
        return self.message


class NotNullConstraintError(DatabaseError):
    """Raised when a NOT NULL constraint is violated."""
    
    def __init__(
        self,
        message: str = "NOT NULL constraint violated",
        *,
        field_name: Optional[str] = None,
        **kwargs: Any,
    ):
        self.field_name = field_name
        super().__init__(message, **kwargs)


class CheckConstraintError(DatabaseError):
    """Raised when a CHECK constraint is violated."""
    
    def __init__(
        self,
        message: str = "CHECK constraint violated",
        *,
        constraint_name: Optional[str] = None,
        **kwargs: Any,
    ):
        self.constraint_name = constraint_name
        super().__init__(message, **kwargs)


class QueryError(DatabaseError):
    """Raised when a query fails for reasons other than constraints."""
    pass


def map_database_error(
    exc: Exception,
    *,
    query: Optional[str] = None,
    params: Optional[tuple] = None,
) -> DatabaseError:
    """
    Map an asyncpg exception to a Vidyut exception.
    
    Args:
        exc: The original asyncpg exception
        query: The SQL query that caused the error
        params: The query parameters
        
    Returns:
        An appropriate Vidyut exception
    """
    import asyncpg
    
    exc_str = str(exc).lower()
    exc_class_name = exc.__class__.__name__
    
    # Check for specific asyncpg exception types
    if isinstance(exc, asyncpg.UniqueViolationError):
        # Try to extract field name from error message
        field_name = _extract_field_from_unique_error(str(exc))
        return UniqueConstraintError(
            message=str(exc),
            field_name=field_name,
            original_exception=exc,
            query=query,
            params=params,
        )
    
    if isinstance(exc, asyncpg.ForeignKeyViolationError):
        field_name, ref_table = _extract_fk_info(str(exc))
        return ForeignKeyConstraintError(
            message=str(exc),
            field_name=field_name,
            referenced_table=ref_table,
            original_exception=exc,
            query=query,
            params=params,
        )
    
    if isinstance(exc, asyncpg.NotNullViolationError):
        field_name = _extract_field_from_notnull_error(str(exc))
        return NotNullConstraintError(
            message=str(exc),
            field_name=field_name,
            original_exception=exc,
            query=query,
            params=params,
        )
    
    if isinstance(exc, asyncpg.PostgresConnectionError):
        return ConnectionError(
            message=str(exc),
            original_exception=exc,
            query=query,
            params=params,
        )
    
    # Check by error message patterns
    if "unique" in exc_str and ("violation" in exc_str or "constraint" in exc_str):
        field_name = _extract_field_from_unique_error(str(exc))
        return UniqueConstraintError(
            message=str(exc),
            field_name=field_name,
            original_exception=exc,
            query=query,
            params=params,
        )
    
    if "foreign key" in exc_str and "violation" in exc_str:
        field_name, ref_table = _extract_fk_info(str(exc))
        return ForeignKeyConstraintError(
            message=str(exc),
            field_name=field_name,
            referenced_table=ref_table,
            original_exception=exc,
            query=query,
            params=params,
        )
    
    # Generic database error
    return DatabaseError(
        message=str(exc),
        original_exception=exc,
        query=query,
        params=params,
    )


def _extract_field_from_unique_error(error_msg: str) -> Optional[str]:
    """Extract field name from unique constraint error message."""
    import re
    
    # Pattern: Key (field_name)=(value) already exists
    match = re.search(r'Key \(([^)]+)\)', error_msg)
    if match:
        return match.group(1)
    
    # Pattern: constraint "tablename_fieldname_key"
    match = re.search(r'constraint "([^"]+)_([^"]+)_key"', error_msg)
    if match:
        return match.group(2)
    
    return None


def _extract_fk_info(error_msg: str) -> tuple[Optional[str], Optional[str]]:
    """Extract field name and referenced table from FK error."""
    import re
    
    field_name = None
    ref_table = None
    
    # Pattern: Key (field_name)=(value) is not present in table "ref_table"
    match = re.search(r'Key \(([^)]+)\)', error_msg)
    if match:
        field_name = match.group(1)
    
    match = re.search(r'table "([^"]+)"', error_msg)
    if match:
        ref_table = match.group(1)
    
    return field_name, ref_table


def _extract_field_from_notnull_error(error_msg: str) -> Optional[str]:
    """Extract field name from NOT NULL error message."""
    import re
    
    # Pattern: null value in column "field_name"
    match = re.search(r'column "([^"]+)"', error_msg)
    if match:
        return match.group(1)
    
    return None


__all__ = [
    "VidyutError",
    "ConfigurationError",
    "DatabaseError",
    "ConnectionError",
    "UniqueConstraintError",
    "ForeignKeyConstraintError",
    "NotNullConstraintError",
    "CheckConstraintError",
    "QueryError",
    "map_database_error",
]
