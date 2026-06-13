"""
GARVIS Database Layer.

Provides asynchronous PostgreSQL connectivity via asyncpg, database migration
scripts, and parameterized SQL query definitions.

Components:
    - DatabaseConnection: async connection pool management
    - Migration scripts for initial schema and governance tables
    - Parameterized SQL queries for all runtime operations
"""

from database.connection import DatabaseConnection, close_pool, initialize_pool

__all__ = [
    "DatabaseConnection",
    "close_pool",
    "initialize_pool",
]
