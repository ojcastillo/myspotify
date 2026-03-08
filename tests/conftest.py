import os
import sqlite3
import sys
import tempfile

import pytest

# Make src importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def db():
    """Provide a fresh in-memory SQLite DB with schema applied."""
    from common.db_helpers import create_schema

    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def db_path(tmp_path):
    """Provide a path to a temp file-based DB (for functions that take a path)."""
    from common.db_helpers import create_schema

    path = str(tmp_path / "test.db")
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    conn.close()
    return path
