"""Apply SQL files in migrations/ in name order, once each."""

from __future__ import annotations

import logging
from pathlib import Path

from jobbot.adapters.db.pool import Database

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "migrations"


def apply_migrations(db: Database, directory: Path = MIGRATIONS_DIR) -> list[str]:
    conn = db.connection()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations").fetchall()}
    applied = []
    for path in sorted(directory.glob("*.sql")):
        if path.name in done:
            continue
        log.info("applying %s", path.name)
        with db.transaction() as tx:
            tx.execute(path.read_text())
            tx.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
        applied.append(path.name)
    return applied
