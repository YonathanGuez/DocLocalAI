from contextlib import contextmanager
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector
import psycopg
from app.config import settings


class Database:
    _pool: ConnectionPool | None = None

    @classmethod
    def initialize(cls):
        """Initialize the connection pool"""
        if cls._pool is None:
            cls._pool = ConnectionPool(
                conninfo=settings.database_url,
                min_size=settings.db_pool_min_size,
                max_size=settings.db_pool_max_size,
                open=True,
            )

    @classmethod
    def close(cls):
        """Close the connection pool"""
        if cls._pool:
            cls._pool.close()
            cls._pool = None

    @classmethod
    @contextmanager
    def get_connection(cls):
        """Get a connection from the pool with automatic cleanup"""
        if cls._pool is None:
            cls.initialize()

        conn = cls._pool.getconn()
        try:
            register_vector(conn)
            yield conn
        finally:
            cls._pool.putconn(conn)

    @classmethod
    @contextmanager
    def get_cursor(cls):
        """Get a cursor with automatic connection and cleanup"""
        with cls.get_connection() as conn:
            with conn.cursor() as cur:
                yield cur
