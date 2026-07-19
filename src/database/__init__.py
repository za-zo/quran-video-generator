"""Database sub-package.

MongoDB-backed persistence layer (migrated from SQLAlchemy/SQLite).

Public API:
  * :func:`get_db`   – cached Database handle for the configured cluster.
  * :func:`ping`     – quick connectivity probe.
  * :func:`set_test_db` – inject a mongomock Database for offline tests.
  * Repositories: :class:`AudioRepo`, :class:`CategoryRepo`,
    :class:`VideoRepo`, :class:`ExecutionRepo` (aliased as ``JobRepo``).
  * :func:`ensure_indexes` – idempotent index creation.
"""

from src.database.mongo_client import (
    get_client,
    get_db,
    ping,
    reset_client,
    set_test_db,
)
from src.database.repository import (
    AudioRepo,
    CategoryRepo,
    ExecutionRepo,
    JobRepo,
    VideoRepo,
    ensure_indexes,
)

__all__ = [
    "get_client",
    "get_db",
    "ping",
    "reset_client",
    "set_test_db",
    "AudioRepo",
    "CategoryRepo",
    "VideoRepo",
    "ExecutionRepo",
    "JobRepo",
    "ensure_indexes",
]
