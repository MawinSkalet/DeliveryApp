import os
from contextlib import contextmanager
from threading import Lock
from typing import Generator

import psycopg
from psycopg.rows import dict_row

try:
    from psycopg_pool import ConnectionPool
except ImportError:
    ConnectionPool = None

_pool: "ConnectionPool | None" = None
_pool_lock = Lock()


def get_db_url() -> str:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://deliveryapp:change-me-local-postgres@localhost:5432/deliveryapp",
    )
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def get_pool() -> "ConnectionPool | None":
    global _pool
    if _pool is not None or ConnectionPool is None:
        return _pool

    with _pool_lock:
        if _pool is None:
            try:
                min_size = int(os.getenv("DB_POOL_MIN_SIZE", "2"))
                max_size = int(os.getenv("DB_POOL_MAX_SIZE", "50"))
                _pool = ConnectionPool(
                    get_db_url(),
                    min_size=min_size,
                    max_size=max_size,
                    timeout=10.0,
                    open=True,
                    kwargs={"row_factory": dict_row},
                )
            except Exception:
                _pool = None
    return _pool


@contextmanager
def get_connection() -> Generator[psycopg.Connection, None, None]:
    pool = get_pool()
    if pool is not None:
        with pool.connection() as conn:
            yield conn
    else:
        with psycopg.connect(get_db_url(), row_factory=dict_row) as conn:
            yield conn


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.close()
            finally:
                _pool = None
