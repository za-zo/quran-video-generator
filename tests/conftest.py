"""Pytest config: make ``src`` importable from the tests folder.

Forces a mongomock-backed database so the entire repository / selector
test suite runs fully offline — no MongoDB Atlas cluster needed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Use mongomock for tests by default. Individual tests still call
# ``set_test_db`` to get a fresh database per test.
os.environ.setdefault("MONGODB_URI", "mongodb://localhost/test")
os.environ.setdefault("MONGODB_DB_NAME", "qvg_test")
os.environ.setdefault("CLOUDINARY_CLOUD_NAME", "test-cloud")
os.environ.setdefault("CLOUDINARY_API_KEY", "test-key")
os.environ.setdefault("CLOUDINARY_API_SECRET", "test-secret")
