"""
Database Engine

Async PostgreSQL database engine with connection pooling using asyncpg.
"""

from __future__ import annotations

import asyncpg
from typing import Any, Optional, Sequence
from contextlib import asynccontextmanager

from vidyut.logging import QueryLogger, logger
from vidyut.exceptions import map_database_error, ConnectionError as VidyutConnectionError


class Database:
    """
    Async PostgreSQL database engine with connection pooling.
    
    Usage:
        db = Database("postgresql://user:pass@localhost/dbname")
        await db.connect()
        
        # Execute queries
        await db.execute("INSERT INTO users (name) VALUES ($1)", "John")
        rows = await db.fetch("SELECT * FROM users")
        
        await db.disconnect()
    
    Or use settings:
        from vidyut.conf import settings
        db = Database.from_settings()
    """
    
    _instance: Optional["Database"] = None
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
    ):
        """
        Initialize database configuration.
        
        Args:
            database_url: PostgreSQL connection URL (or uses settings.DATABASE_URL)
            min_size: Minimum number of connections in the pool
            max_size: Maximum number of connections in the pool
        """
        from vidyut.conf import settings
        
        self.database_url = database_url or settings.DATABASE_URL
        if not self.database_url:
            raise VidyutConnectionError(
                "No database URL provided. Set VIDYUT_DATABASE_URL or DATABASE_URL, "
                "or pass database_url to Database()."
            )
        
        self.min_size = min_size if min_size is not None else settings.pool_min_size
        self.max_size = max_size if max_size is not None else settings.pool_max_size
        self._pool: Optional[asyncpg.Pool] = None
        
        # Set as singleton instance
        Database._instance = self
    
    @classmethod
    def from_settings(cls) -> "Database":
        """Create a Database instance from settings."""
        from vidyut.conf import settings
        return cls(
            database_url=settings.DATABASE_URL,
            min_size=settings.pool_min_size,
            max_size=settings.pool_max_size,
        )
    
    @classmethod
    def get_instance(cls) -> "Database":
        """Get the singleton database instance."""
        if cls._instance is None:
            raise RuntimeError(
                "Database not initialized. Call Database(...) first or use init_vidyut()."
            )
        return cls._instance
    
    @property
    def pool(self) -> asyncpg.Pool:
        """Get the connection pool, raising if not connected."""
        if self._pool is None:
            raise RuntimeError(
                "Database not connected. Call await db.connect() first."
            )
        return self._pool
    
    async def connect(self) -> None:
        """
        Establish connection pool to the database.
        
        This should be called during application startup.
        """
        if self._pool is not None:
            return
        
        try:
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.min_size,
                max_size=self.max_size,
            )
            logger.debug(f"Database pool created (min={self.min_size}, max={self.max_size})")
        except Exception as e:
            raise VidyutConnectionError(
                f"Failed to connect to database: {e}",
                original_exception=e,
            )
    
    async def disconnect(self) -> None:
        """
        Close all connections in the pool.
        
        This should be called during application shutdown.
        """
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.debug("Database pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool.
        
        Usage:
            async with db.acquire() as conn:
                await conn.execute(...)
        """
        async with self.pool.acquire() as connection:
            yield connection
    
    async def execute(
        self,
        query: str,
        *args: Any,
        timeout: Optional[float] = None,
    ) -> str:
        """
        Execute a query without returning results.
        
        Args:
            query: SQL query with $1, $2, ... placeholders
            *args: Query parameters
            timeout: Optional timeout in seconds
            
        Returns:
            Status string (e.g., "INSERT 0 1")
        """
        with QueryLogger(query, args):
            try:
                async with self.acquire() as conn:
                    return await conn.execute(query, *args, timeout=timeout)
            except Exception as e:
                raise map_database_error(e, query=query, params=args)
    
    async def fetch(
        self,
        query: str,
        *args: Any,
        timeout: Optional[float] = None,
    ) -> list[asyncpg.Record]:
        """
        Execute a query and fetch all results.
        
        Args:
            query: SQL query with $1, $2, ... placeholders
            *args: Query parameters
            timeout: Optional timeout in seconds
            
        Returns:
            List of records
        """
        with QueryLogger(query, args):
            try:
                async with self.acquire() as conn:
                    return await conn.fetch(query, *args, timeout=timeout)
            except Exception as e:
                raise map_database_error(e, query=query, params=args)
    
    async def fetchrow(
        self,
        query: str,
        *args: Any,
        timeout: Optional[float] = None,
    ) -> Optional[asyncpg.Record]:
        """
        Execute a query and fetch a single row.
        
        Args:
            query: SQL query with $1, $2, ... placeholders
            *args: Query parameters
            timeout: Optional timeout in seconds
            
        Returns:
            Single record or None
        """
        with QueryLogger(query, args):
            try:
                async with self.acquire() as conn:
                    return await conn.fetchrow(query, *args, timeout=timeout)
            except Exception as e:
                raise map_database_error(e, query=query, params=args)
    
    async def fetchval(
        self,
        query: str,
        *args: Any,
        column: int = 0,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        Execute a query and fetch a single value.
        
        Args:
            query: SQL query with $1, $2, ... placeholders
            *args: Query parameters
            column: Column index to return
            timeout: Optional timeout in seconds
            
        Returns:
            Single value
        """
        with QueryLogger(query, args):
            try:
                async with self.acquire() as conn:
                    return await conn.fetchval(query, *args, column=column, timeout=timeout)
            except Exception as e:
                raise map_database_error(e, query=query, params=args)
