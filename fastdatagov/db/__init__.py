"""PostgreSQL access with schema-qualified SQL only."""

from __future__ import annotations

import atexit
import threading
from contextlib import contextmanager

import psycopg
from psycopg_pool import ConnectionPool

from fastdatagov.config import settings

_connection_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()

def pool() -> ConnectionPool:
    """Return the process-wide bounded PostgreSQL pool."""
    global _connection_pool
    if _connection_pool is not None:
        return _connection_pool
    with _pool_lock:
        if _connection_pool is None:
            configured = settings()
            connection_pool = ConnectionPool(
                conninfo=configured.database_url,
                min_size=configured.database_pool_min,
                max_size=configured.database_pool_max,
                timeout=configured.database_pool_timeout,
                max_lifetime=configured.database_pool_recycle,
                max_idle=configured.database_pool_max_idle,
                open=False,
                kwargs={
                    "autocommit": False,
                    "application_name": configured.database_application_name,
                },
                check=ConnectionPool.check_connection,
            )
            connection_pool.open()
            _connection_pool = connection_pool
    return _connection_pool


def close_database_pool() -> None:
    """Close and forget the process pool during shutdown or test reset."""
    global _connection_pool
    with _pool_lock:
        connection_pool = _connection_pool
        _connection_pool = None
    if connection_pool is not None:
        connection_pool.close()


atexit.register(close_database_pool)


@contextmanager
def connect():
    with pool().connection() as connection:
        yield connection


def fetch_all(sql: str, params: tuple | dict | None = None) -> list[dict]:
    with connect() as connection, connection.cursor(row_factory=psycopg.rows.dict_row) as cursor:
        cursor.execute(sql, params or ())
        return list(cursor.fetchall())


def fetch_one(sql: str, params: tuple | dict | None = None) -> dict | None:
    with connect() as connection, connection.cursor(row_factory=psycopg.rows.dict_row) as cursor:
        cursor.execute(sql, params or ())
        return cursor.fetchone()


def execute(sql: str, params: tuple | dict | None = None) -> None:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(sql, params or ())
        connection.commit()
