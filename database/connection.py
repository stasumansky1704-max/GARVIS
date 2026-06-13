"""
PostgreSQL async connection pool for GARVIS.

Manages the lifecycle of an asyncpg connection pool, providing a thin
wrapper around asyncpg that handles connection acquisition, release,
and health monitoring. All database operations in GARVIS flow through
this module.
"""

from __future__ import annotations

import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Module-level connection pool singleton
_pool: asyncpg.Pool | None = None


class DatabaseConnection:
    """Async PostgreSQL database connection manager.

    Provides CRUD operations and health checks via an asyncpg connection pool.
    This class is designed to be used as a singleton via the module-level
    pool, but can also be instantiated directly for testing or custom setups.

    Example:
        await initialize_pool("postgresql://user:pass@localhost/db")
        db = DatabaseConnection()
        rows = await db.fetch("SELECT * FROM episodic_memories WHERE session_id = $1", session_id)
        await close_pool()
    """

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """Execute a SELECT query returning multiple rows.

        Args:
            query: Parameterized SQL query using $1, $2, ... placeholders.
            *args: Query parameters.

        Returns:
            List of asyncpg.Record objects.

        Raises:
            RuntimeError: If the connection pool has not been initialized.
            asyncpg.PostgresError: On database errors.
        """
        if _pool is None:
            raise RuntimeError(
                "Database pool not initialized. Call initialize_pool() first."
            )
        async with _pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        """Execute a SELECT query returning at most one row.

        Args:
            query: Parameterized SQL query using $1, $2, ... placeholders.
            *args: Query parameters.

        Returns:
            A single asyncpg.Record, or None if no row matches.

        Raises:
            RuntimeError: If the connection pool has not been initialized.
            asyncpg.PostgresError: On database errors.
        """
        if _pool is None:
            raise RuntimeError(
                "Database pool not initialized. Call initialize_pool() first."
            )
        async with _pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        """Execute an INSERT, UPDATE, or DELETE query.

        Args:
            query: Parameterized SQL query using $1, $2, ... placeholders.
            *args: Query parameters.

        Returns:
            The PostgreSQL command status string, e.g. 'INSERT 0 1'.

        Raises:
            RuntimeError: If the connection pool has not been initialized.
            asyncpg.PostgresError: On database errors.
        """
        if _pool is None:
            raise RuntimeError(
                "Database pool not initialized. Call initialize_pool() first."
            )
        async with _pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Execute a query returning a single scalar value.

        Args:
            query: Parameterized SQL query using $1, $2, ... placeholders.
            *args: Query parameters.

        Returns:
            A single scalar value, or None if no result.

        Raises:
            RuntimeError: If the connection pool has not been initialized.
            asyncpg.PostgresError: On database errors.
        """
        if _pool is None:
            raise RuntimeError(
                "Database pool not initialized. Call initialize_pool() first."
            )
        async with _pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def health_check(self) -> bool:
        """Check whether the database is reachable and responsive.

        Returns:
            True if the database responds to a simple query, False otherwise.
        """
        if _pool is None:
            return False
        try:
            async with _pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as exc:
            logger.warning("Database health check failed: %s", exc)
            return False

    @property
    def is_initialized(self) -> bool:
        """Whether the connection pool has been initialized."""
        return _pool is not None


async def initialize_pool(
    dsn: str,
    *,
    min_size: int = 2,
    max_size: int = 10,
    command_timeout: float = 60.0,
) -> None:
    """Create the asyncpg connection pool.

    Must be called before any database operations. The pool is stored as a
    module-level singleton and used by all DatabaseConnection instances.

    Args:
        dsn: PostgreSQL connection string (asyncpg format).
        min_size: Minimum number of connections to maintain.
        max_size: Maximum number of connections allowed.
        command_timeout: Timeout for SQL commands in seconds.

    Raises:
        asyncpg.PostgresError: If the pool cannot be created.
    """
    global _pool  # noqa: PLW0603
    if _pool is not None:
        logger.warning("Database pool already initialized; skipping re-initialization")
        return

    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=command_timeout,
    )
    logger.info(
        "Database pool initialized (min=%d, max=%d)", min_size, max_size
    )


async def close_pool() -> None:
    """Close the asyncpg connection pool.

    Should be called during graceful shutdown to release all connections.
    Safe to call even if the pool was never initialized.
    """
    global _pool  # noqa: PLW0603
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")
