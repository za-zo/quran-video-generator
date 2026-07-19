"""Pytest config: make ``src`` importable from the tests folder."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force a temp DB / output / logs location for tests that don't override.
os.environ.setdefault("QVG_DB_PATH", "/tmp/qvg_test.db")
