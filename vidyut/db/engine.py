"""
Database Engine

Async PostgreSQL database engine with connection pooling using asyncpg.
"""

from __future__ import annotations

import asyncpg
from typing import Any, Optional, Sequence
from contextlib import asynccontextmanager


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
    """
    
    _instance: Optional["Database"] = None
    
    def __init__(
        self,
        database_url: str,
        min_size: int = 5,
        max_size: int = 20,
    ):
        """
        Initialize database configuration.
        
        Args:
            database_url: PostgreSQL connection URL
            min_size: Minimum number of connections in the pool
            max_size: Maximum number of connections in the pool
        """
        self.database_url = database_url
        self.min_size = min_size
        self.max_size = max_size
        self._pool: Optional[asyncpg.Pool] = None
        
        # Set as singleton instance
        Database._instance = self
    
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
            
        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=self.min_size,
            max_size=self.max_size,
        )
    
    async def disconnect(self) -> None:
        """
        Close all connections in the pool.
        
        This should be called during application shutdown.
        """
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
    
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
        async with self.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)
    
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
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)
    
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
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)
    
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
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, column=column, timeout=timeout)
