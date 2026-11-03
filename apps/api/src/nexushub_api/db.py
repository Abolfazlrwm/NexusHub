"""Database engine and session management.

Engines are cached per URL so repeated dependency calls reuse one pool.
SQLite gets thread-friendly connect args because TestClient and uvicorn
touch the database from different threads; everything else is passed to
SQLAlchemy untouched, so a Postgres URL works by only changing settings.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from .models import load_models  # noqa: F401  (imported so metadata is populated)
from .settings import Settings


@cache
def get_engine(database_url: str) -> Engine:
    """Build (once) and return the engine for a database URL."""
    kwargs: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if database_url.endswith(":memory:"):
            kwargs["poolclass"] = StaticPool
    return create_engine(database_url, **kwargs)


def engine_from_settings(settings: Settings) -> Engine:
    """Resolve the engine for a settings object."""
    return get_engine(settings.database_url)


def init_db(engine: Engine) -> None:
    """Create all tables that do not exist yet."""
    SQLModel.metadata.create_all(engine)


def open_session(engine: Engine) -> Session:
    """Open a session against ``engine``; caller closes it."""
    return Session(engine)
