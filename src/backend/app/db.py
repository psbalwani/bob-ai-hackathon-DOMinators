"""Database setup -- Track D.

Real PostgreSQL (e.g. a Neon connection string) via DATABASE_URL, per
docs/04_data_schema.md. If DATABASE_URL isn't set, the app runs on an
in-memory store instead (see persistence.py) so a fresh checkout works with
zero setup -- this doubles as the "cache a fallback for the live demo"
requirement in docs/03_team_division.md's Track D task list.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")
USING_DB = bool(DATABASE_URL)


class Base(DeclarativeBase):
    pass


if USING_DB:
    # Neon (and most hosted Postgres) require sslmode=require; add it if the
    # caller's connection string didn't already specify one.
    _url = DATABASE_URL
    if "sslmode" not in _url and _url.startswith("postgresql"):
        _url += ("&" if "?" in _url else "?") + "sslmode=require"
    engine = create_engine(_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
else:
    engine = None
    SessionLocal = None


def init_db() -> None:
    """Create tables if they don't exist yet. No-op if DATABASE_URL isn't set."""
    if not USING_DB:
        return
    from . import models_db  # noqa: F401  (registers tables on Base.metadata)

    Base.metadata.create_all(bind=engine)
