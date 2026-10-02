"""`uv run jobbot-migrate`: create/upgrade the database schema (idempotent)."""

from __future__ import annotations

import sys

from jobbot.adapters.db.migrate import apply_migrations
from jobbot.adapters.db.pool import Database
from jobbot.config import load_settings
from jobbot.logging_setup import setup_logging


def main() -> None:
    setup_logging()
    settings = load_settings()
    if not settings.secrets.database_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        sys.exit(2)
    db = Database(settings.secrets.database_url)
    try:
        applied = apply_migrations(db)
    finally:
        db.close()
    print("applied: " + (", ".join(applied) if applied else "nothing (up to date)"))


if __name__ == "__main__":
    main()
