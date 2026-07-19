"""Repository pattern – thin data-access layer on top of MongoDB.

Each repository owns one collection and exposes only the operations the rest
of the application needs. Selectors and the orchestrator depend on these
abstractions, never on raw Mongo documents leaking outside this module.

Document shape is defined in section 3.2 of the migration brief. Field
names here MUST stay in sync with the Next.js webapp's data access layer.

ID convention
-------------
Documents use ObjectId ``_id``. Repository methods accept/return ``str``
IDs at the boundary (``str(ObjectId(...))``) so the rest of the codebase
stays decoupled from pymongo specifics.

Transactions
------------
Multi-step writes (mark audio + category + N videos used after a successful
job) are issued as sequential ``update_one`` calls without an explicit
Mongo session/transaction. Rationale:
  * On a free Atlas tier, transactions work but add latency and require a
    replica set (which Atlas provides by default).
  * The worst-case failure mode here is a partial usage-count bump, which
    only slightly skews future weighted selection – not a data-integrity
    disaster. The execution document itself is marked success/failed in
    its own write, so the truth of "did this clip ship?" is never
    ambiguous.
If we later need stronger consistency we can wrap ``_mark_used`` in a
``client.start_session()`` + ``with session.start_transaction()`` block
without changing any caller.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from bson import ObjectId
from pymongo.database import Database

from src.exceptions import DatabaseIntegrityError
from src.models import (
    AudioRecord,
    CategoryRecord,
    GenerationJobResult,
    VideoRecord,
)
from src.utils.logger import get_logger

log = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _oid(id_: str | ObjectId) -> ObjectId:
    """Coerce a str id to ObjectId, raising a clear error on bad input."""
    if isinstance(id_, ObjectId):
        return id_
    try:
        return ObjectId(id_)
    except Exception as exc:
        raise DatabaseIntegrityError(f"invalid ObjectId: {id_!r}") from exc


def _audio_from_doc(d: dict[str, Any]) -> AudioRecord:
    return AudioRecord(
        id=str(d["_id"]),
        name=d.get("name", ""),
        source_url=d.get("source_url", ""),
        duration_seconds=float(d.get("duration_seconds") or 0.0),
        usage_count=int(d.get("usage_count") or 0),
        last_used_at=d.get("last_used_at"),
    )


def _category_from_doc(d: dict[str, Any]) -> CategoryRecord:
    return CategoryRecord(
        id=str(d["_id"]),
        name=d.get("name", ""),
        usage_count=int(d.get("usage_count") or 0),
        last_used_at=d.get("last_used_at"),
    )


def _video_from_doc(d: dict[str, Any]) -> VideoRecord:
    return VideoRecord(
        id=str(d["_id"]),
        category_id=str(d.get("category_id")) if d.get("category_id") else "",
        name=d.get("name", ""),
        source_url=d.get("source_url", ""),
        duration_seconds=float(d.get("duration_seconds") or 0.0),
        usage_count=int(d.get("usage_count") or 0),
        last_used_at=d.get("last_used_at"),
    )


# --- AudioRepo --------------------------------------------------------------

class AudioRepo:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.col = db["audios"]

    def create(self, name: str, source_url: str, duration_seconds: float = 0.0) -> AudioRecord:
        """Insert a new audio document. Raises if name already exists."""
        existing = self.col.find_one({"name": name})
        if existing is not None:
            raise DatabaseIntegrityError(f"audio with name {name!r} already exists")
        doc = {
            "name": name,
            "source_url": source_url,
            "duration_seconds": float(duration_seconds),
            "usage_count": 0,
            "last_used_at": None,
            "created_at": _utcnow(),
        }
        res = self.col.insert_one(doc)
        return _audio_from_doc({**doc, "_id": res.inserted_id})

    def get_or_create(self, name: str, source_url: str, duration_seconds: float = 0.0) -> AudioRecord:
        """Lookup by name; create if missing. Updates source_url/duration if changed."""
        existing = self.col.find_one({"name": name})
        if existing is not None:
            updates: dict[str, Any] = {}
            if existing.get("source_url") != source_url:
                updates["source_url"] = source_url
            if float(existing.get("duration_seconds") or 0) != float(duration_seconds):
                updates["duration_seconds"] = float(duration_seconds)
            if updates:
                self.col.update_one({"_id": existing["_id"]}, {"$set": updates})
                existing.update(updates)
            return _audio_from_doc(existing)
        return self.create(name, source_url, duration_seconds)

    def get(self, audio_id: str) -> AudioRecord | None:
        doc = self.col.find_one({"_id": _oid(audio_id)})
        return _audio_from_doc(doc) if doc else None

    def list_all(self) -> list[AudioRecord]:
        # Sort by insertion order (ObjectId generation time).
        return [_audio_from_doc(d) for d in self.col.find().sort("_id", 1)]

    def mark_used(self, audio_id: str) -> None:
        res = self.col.update_one(
            {"_id": _oid(audio_id)},
            {"$inc": {"usage_count": 1}, "$set": {"last_used_at": _utcnow()}},
        )
        if res.matched_count == 0:
            raise DatabaseIntegrityError(f"Audio id={audio_id} not found")

    def update_duration(self, audio_id: str, duration_seconds: float) -> None:
        self.col.update_one(
            {"_id": _oid(audio_id)},
            {"$set": {"duration_seconds": float(duration_seconds)}},
        )

    def delete(self, audio_id: str) -> bool:
        res = self.col.delete_one({"_id": _oid(audio_id)})
        return res.deleted_count > 0

    def stats(self) -> list[tuple[str, int, datetime | None, str]]:
        rows = self.list_all()
        return [(a.name, a.usage_count, a.last_used_at, a.source_url) for a in rows]


# --- CategoryRepo -----------------------------------------------------------

class CategoryRepo:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.col = db["categories"]

    def create(self, name: str) -> CategoryRecord:
        existing = self.col.find_one({"name": name})
        if existing is not None:
            raise DatabaseIntegrityError(f"category with name {name!r} already exists")
        doc = {
            "name": name,
            "usage_count": 0,
            "last_used_at": None,
            "created_at": _utcnow(),
        }
        res = self.col.insert_one(doc)
        return _category_from_doc({**doc, "_id": res.inserted_id})

    def get_or_create(self, name: str) -> CategoryRecord:
        existing = self.col.find_one({"name": name})
        if existing is not None:
            return _category_from_doc(existing)
        return self.create(name)

    def get(self, category_id: str) -> CategoryRecord | None:
        doc = self.col.find_one({"_id": _oid(category_id)})
        return _category_from_doc(doc) if doc else None

    def list_all(self) -> list[CategoryRecord]:
        return [_category_from_doc(d) for d in self.col.find().sort("_id", 1)]

    def mark_used(self, category_id: str) -> None:
        res = self.col.update_one(
            {"_id": _oid(category_id)},
            {"$inc": {"usage_count": 1}, "$set": {"last_used_at": _utcnow()}},
        )
        if res.matched_count == 0:
            raise DatabaseIntegrityError(f"Category id={category_id} not found")

    def delete(self, category_id: str) -> bool:
        res = self.col.delete_one({"_id": _oid(category_id)})
        return res.deleted_count > 0

    def count_videos(self, category_id: str) -> int:
        return self.db["videos"].count_documents({"category_id": _oid(category_id)})


# --- VideoRepo --------------------------------------------------------------

class VideoRepo:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.col = db["videos"]

    def create(
        self,
        category_id: str,
        name: str,
        source_url: str,
        duration_seconds: float = 0.0,
    ) -> VideoRecord:
        existing = self.col.find_one({
            "category_id": _oid(category_id),
            "name": name,
        })
        if existing is not None:
            raise DatabaseIntegrityError(
                f"video with name {name!r} already exists in category {category_id}"
            )
        doc = {
            "category_id": _oid(category_id),
            "name": name,
            "source_url": source_url,
            "duration_seconds": float(duration_seconds),
            "usage_count": 0,
            "last_used_at": None,
            "created_at": _utcnow(),
        }
        res = self.col.insert_one(doc)
        return _video_from_doc({**doc, "_id": res.inserted_id})

    def get_or_create(
        self,
        category_id: str,
        name: str,
        source_url: str,
        duration_seconds: float = 0.0,
    ) -> VideoRecord:
        existing = self.col.find_one({
            "category_id": _oid(category_id),
            "name": name,
        })
        if existing is not None:
            updates: dict[str, Any] = {}
            if existing.get("source_url") != source_url:
                updates["source_url"] = source_url
            if float(existing.get("duration_seconds") or 0) != float(duration_seconds):
                updates["duration_seconds"] = float(duration_seconds)
            if updates:
                self.col.update_one({"_id": existing["_id"]}, {"$set": updates})
                existing.update(updates)
            return _video_from_doc(existing)
        return self.create(category_id, name, source_url, duration_seconds)

    def get(self, video_id: str) -> VideoRecord | None:
        doc = self.col.find_one({"_id": _oid(video_id)})
        return _video_from_doc(doc) if doc else None

    def list_for_category(self, category_id: str) -> list[VideoRecord]:
        return [
            _video_from_doc(d)
            for d in self.col.find({"category_id": _oid(category_id)}).sort("_id", 1)
        ]

    def mark_used(self, video_id: str) -> None:
        res = self.col.update_one(
            {"_id": _oid(video_id)},
            {"$inc": {"usage_count": 1}, "$set": {"last_used_at": _utcnow()}},
        )
        if res.matched_count == 0:
            raise DatabaseIntegrityError(f"Video id={video_id} not found")

    def mark_used_many(self, video_ids: Iterable[str]) -> None:
        for vid in video_ids:
            self.mark_used(vid)

    def update_duration(self, video_id: str, duration_seconds: float) -> None:
        self.col.update_one(
            {"_id": _oid(video_id)},
            {"$set": {"duration_seconds": float(duration_seconds)}},
        )

    def delete(self, video_id: str) -> bool:
        res = self.col.delete_one({"_id": _oid(video_id)})
        return res.deleted_count > 0

    def reassign_category(self, video_id: str, new_category_id: str) -> bool:
        res = self.col.update_one(
            {"_id": _oid(video_id)},
            {"$set": {"category_id": _oid(new_category_id)}},
        )
        return res.matched_count > 0

    def delete_for_category(self, category_id: str) -> int:
        res = self.col.delete_many({"category_id": _oid(category_id)})
        return res.deleted_count


# --- ExecutionRunRepo (Le run global) ---------------------------------------

class ExecutionRunRepo:
    """Owns the `executions` collection (one document per GitHub Actions run)."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.col = db["executions"]

    def create(self, github_run_id: str) -> dict[str, Any]:
        doc = {
            "status": "running",
            "github_run_id": github_run_id,
            "created_at": _utcnow(),
            "completed_at": None,
            "success_count": 0,
            "failed_count": 0,
            "total_slices": 0,
        }
        res = self.col.insert_one(doc)
        return {**doc, "_id": res.inserted_id}

    def increment_counters(self, run_id: str, success: bool) -> None:
        field = "success_count" if success else "failed_count"
        self.col.update_one(
            {"_id": _oid(run_id)},
            {"$inc": {"total_slices": 1, field: 1}},
        )

    def mark_completed(self, run_id: str, status: str) -> None:
        self.col.update_one(
            {"_id": _oid(run_id)},
            {"$set": {"status": status, "completed_at": _utcnow()}},
        )

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        cur = self.col.find({}).sort("created_at", -1).limit(limit)
        return [_normalize_execution(d) for d in cur]

    def get(self, run_id: str) -> dict[str, Any] | None:
        doc = self.col.find_one({"_id": _oid(run_id)})
        return _normalize_execution(doc) if doc else None


# --- ExecutionSliceRepo (Les clips individuels) -----------------------------

class ExecutionSliceRepo:
    """Owns the `execution_slices` collection (one document per generated clip)."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"

    def __init__(self, db: Database) -> None:
        self.db = db
        self.col = db["execution_slices"]

    def create(self, execution_id: str, audio_id: str, slice_index: int,
               clip_start: float, clip_end: float, clip_duration: float, github_run_id: str) -> dict[str, Any]:
        doc = {
            "execution_id": _oid(execution_id),
            "audio_id": _oid(audio_id),
            "status": self.PENDING,
            "error_message": None,
            "slice": {
                "index": int(slice_index),
                "start_seconds": float(clip_start),
                "end_seconds": float(clip_end),
                "duration_seconds": float(clip_duration),
            },
            "selected_category_id": None,
            "selected_video_ids": [],
            "output": None,
            "github_run_id": github_run_id,
            "created_at": _utcnow(),
            "completed_at": None,
        }
        res = self.col.insert_one(doc)
        out = {**doc, "_id": res.inserted_id}
        return out

    def mark_selection(self, slice_id: str, category_id: str, video_ids: list[str]) -> None:
        self.col.update_one(
            {"_id": _oid(slice_id)},
            {"$set": {
                "selected_category_id": _oid(category_id),
                "selected_video_ids": [_oid(v) for v in video_ids],
            }},
        )

    def mark_success(self, slice_id: str, cloudinary_url: str, cloudinary_public_id: str,
                     duration_seconds: float, width: int, height: int) -> None:
        self.col.update_one(
            {"_id": _oid(slice_id)},
            {"$set": {
                "status": self.SUCCESS,
                "output": {
                    "cloudinary_url": cloudinary_url,
                    "cloudinary_public_id": cloudinary_public_id,
                    "duration_seconds": float(duration_seconds),
                    "width": int(width),
                    "height": int(height),
                },
                "completed_at": _utcnow(),
            }},
        )

    def mark_failed(self, slice_id: str, error_message: str) -> None:
        self.col.update_one(
            {"_id": _oid(slice_id)},
            {"$set": {
                "status": self.FAILED,
                "error_message": (error_message or "")[:4000],
                "completed_at": _utcnow(),
            }},
        )

    def list_by_execution(self, execution_id: str, status: str | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"execution_id": _oid(execution_id)}
        if status and ["pending", "success", "failed", "canceled"].count(status) > 0:
            query["status"] = status
        cur = self.col.find(query).sort("created_at", 1)
        return [_normalize_execution(d) for d in cur]

    def get(self, slice_id: str) -> dict[str, Any] | None:
        doc = self.col.find_one({"_id": _oid(slice_id)})
        if doc is None:
            return None
        return _normalize_execution(doc)

    def recent_category_ids(self, k: int) -> list[str]:
        if k <= 0: return []
        cur = self.db["categories"].find(
            {"last_used_at": {"$ne": None}}
        ).sort("last_used_at", -1).limit(k)
        return [str(d["_id"]) for d in cur]


# --- Backwards compatibility alias ------------------------------------------
JobRepo = ExecutionRunRepo


def _normalize_execution(d: dict[str, Any]) -> dict[str, Any]:
    """Stringify all ObjectIds in an execution doc for external consumers."""
    out = dict(d)
    out["_id"] = str(d["_id"])
    if d.get("execution_id"):
        out["execution_id"] = str(d["execution_id"])
    if d.get("audio_id"):
        out["audio_id"] = str(d["audio_id"])
    if d.get("selected_category_id"):
        out["selected_category_id"] = str(d["selected_category_id"])
    if d.get("selected_video_ids"):
        out["selected_video_ids"] = [str(v) for v in d["selected_video_ids"]]
    return out


# --- Index management -------------------------------------------------------

def ensure_indexes(db: Database) -> None:
    """Create the indexes documented in section 3.3.

    Idempotent – safe to call from ``init-db`` on every run. pymongo's
    ``create_index`` is a no-op if the index already exists with the same
    spec.
    """
    db["audios"].create_index("usage_count")
    db["categories"].create_index("usage_count")
    db["categories"].create_index("last_used_at")
    db["videos"].create_index([("category_id", 1), ("usage_count", 1)])
    db["executions"].create_index([("created_at", -1)])
    db["executions"].create_index("status")
    db["execution_slices"].create_index([("created_at", -1)])
    db["execution_slices"].create_index("status")
    db["execution_slices"].create_index("execution_id")
    # Unique-name guards so duplicate registration fails fast.
    db["audios"].create_index("name", unique=True)
    db["categories"].create_index("name", unique=True)
    db["videos"].create_index([("category_id", 1), ("name", 1)], unique=True)
    log.info("mongo indexes ensured")


__all__ = [
    "AudioRepo",
    "CategoryRepo",
    "VideoRepo",
    "ExecutionRunRepo",
    "ExecutionSliceRepo",
    "JobRepo",        # backwards-compat alias
    "ensure_indexes",
]
