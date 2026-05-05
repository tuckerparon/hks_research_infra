# ── HUMAN REVIEW ──────────────────────────────────────────
# Reviewer: Tucker Paron
# Date: 2026-05-05
# Changes from AI draft:
#   - Lazy pool initialization so importing this module during tests doesn't attempt a real DB connection
# Notes:
#   - Connects to DB (PostgreSQL) with psycopg2
#   - minconn=1 and maxconn=10 are standard conventions
# ──────────────────────────────────────────────────────────

import os
from contextlib import contextmanager
from psycopg2.pool import ThreadedConnectionPool

_pool = None


def _get_pool():
    # Only create the pool on first real use — keeps tests importable without a live DB.
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=os.getenv('POSTGRES_HOST', 'db'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            dbname=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
        )
    return _pool


@contextmanager
def get_conn():
    """Yield a psycopg2 connection from the pool, returning it when done.

    Usage:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
    """
    conn = _get_pool().getconn()
    try:
        yield conn
    finally:
        _get_pool().putconn(conn)
