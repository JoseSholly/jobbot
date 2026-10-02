"""Connection handling. One short-lived connection per process is plenty for a cron job."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row


class Database:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("DATABASE_URL is not set")
        self.dsn = dsn
        self._conn: psycopg.Connection | None = None

    def connection(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            # prepare_threshold=None keeps us compatible with Neon's pgbouncer (pooled URL).
            self._conn = psycopg.connect(
                self.dsn, row_factory=dict_row, autocommit=True, prepare_threshold=None
            )
        return self._conn

    @contextmanager
    def transaction(self) -> Iterator[psycopg.Connection]:
        conn = self.connection()
        with conn.transaction():
            yield conn

    def close(self) -> None:
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
