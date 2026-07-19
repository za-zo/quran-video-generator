"""Database engine and session factory.

SQLite is used for portability and zero-config operation. ``check_same_thread``
is disabled so the session can be shared across the orchestrator and worker
code paths; all writes are wrapped in explicit transactions by the repository
layer.
"""

from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import get_settings
from src.database.models import Base
from src.utils.logger import get_logger

log = get_logger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _build_engine(db_path: str) -> Engine:
    """Create a SQLAlchemy engine for a SQLite database at ``db_path``."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{path.resolve()}"
    log.debug("creating SQLAlchemy engine: %s", url)
    return create_engine(
        url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )


def get_engine() -> Engine:
    """Return the cached engine, creating it on first call."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = _build_engine(settings.db_path)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return a cached session factory bound to the current engine."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
            class_=Session,
        )
    return _SessionLocal


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(get_engine())
    log.info("database initialised at %s", get_settings().db_path)


def reset_engine() -> None:
    """Drop cached engine/session – used by tests to switch DB files."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_session() -> Session:
    """Return a new Session. Caller is responsible for closing it."""
    return get_session_factory()()


__all__ = [
    "get_engine",
    "get_session_factory",
    "get_session",
    "init_db",
    "reset_engine",
]
