"""MongoDB Atlas client – singleton, lazy, env-driven.

Builds and caches a :class:`pymongo.MongoClient` from the ``MONGODB_URI``
setting. The cluster/database is chosen at construction time but the
connection itself is lazy – pymongo opens the socket on first command.

For tests we support injecting an alternative client (e.g. ``mongomock``)
via :func:`set_test_client`, so the entire repository layer can run
fully offline without monkey-patching pymongo.
"""

from __future__ import annotations

from typing import Any

from pymongo import MongoClient
from pymongo.database import Database

from src.config.settings import get_settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_client: MongoClient | None = None
_db: Database | None = None
# When non-None, ``get_db`` returns this instead of building a real client.
# Used by tests to inject mongomock or an in-memory substitute.
_test_db: Database | None = None


def _build_client(uri: str) -> MongoClient:
    """Create a MongoClient with sensible defaults for the cloud pipeline."""
    log.debug("creating pymongo client")
    # ``serverSelectionTimeoutMS=5000`` surfaces mis-configured URIs quickly,
    # which matters in GitHub Actions where every second of wait is logged.
    return MongoClient(
        uri,
        serverSelectionTimeoutMS=5000,
        retryWrites=True,
    )


def get_client() -> MongoClient:
    """Return the cached MongoClient, creating it on first call."""
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.mongodb_uri:
            raise RuntimeError(
                "MONGODB_URI is not set. Configure it via env var, .env, or"
                " config.yaml (see README.md)."
            )
        _client = _build_client(settings.mongodb_uri)
    return _client


def get_db() -> Database:
    """Return the cached Database handle, creating it on first call.

    Tests can override this entirely via :func:`set_test_db`.
    """
    global _db
    if _test_db is not None:
        return _test_db
    if _db is None:
        settings = get_settings()
        _db = get_client()[settings.mongodb_db_name]
    return _db


def set_test_db(db: Any | None) -> None:
    """Inject (or clear) a test-only Database handle.

    Pass a ``mongomock.MongoClient().get_database("test")`` to run the
    repository layer fully offline. Pass ``None`` to restore real behaviour.
    """
    global _test_db, _db, _client
    _test_db = db
    # Reset the cached real handles too, so the next ``get_db`` after the
    # test resolves to whatever is now appropriate.
    _db = None
    _client = None


def reset_client() -> None:
    """Drop cached client/db (used between tests)."""
    global _client, _db
    if _client is not None:
        try:
            _client.close()
        except Exception:  # pragma: no cover
            pass
    _client = None
    _db = None


def ping() -> bool:
    """Quick connectivity probe – returns True if the cluster responds."""
    try:
        get_client().admin.command("ping")
        return True
    except Exception as exc:  # pragma: no cover - depends on network
        log.error("mongo ping failed: %s", exc)
        return False


__all__ = [
    "get_client",
    "get_db",
    "set_test_db",
    "reset_client",
    "ping",
]
