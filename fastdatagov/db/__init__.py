"""PostgreSQL access with schema-qualified SQL only."""

from __future__ import annotations

import atexit
from contextlib import contextmanager
from functools import lru_cache

import psycopg
from psycopg_pool import ConnectionPool

from fastdatagov.config import settings


@lru_cache(maxsize=1)
def pool() -> ConnectionPool:
    connection_pool = ConnectionPool(
        conninfo=settings().database_url,
        min_size=settings().database_pool_min,
        max_size=settings().database_pool_max,
        open=False,
        kwargs={"autocommit": False},
    )
    connection_pool.open()
    atexit.register(connection_pool.close)
    return connection_pool


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
