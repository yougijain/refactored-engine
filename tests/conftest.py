"""Shared fixtures. The warehouse is built once per session and queried read-only."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
MARTS_DIR = ROOT / "data" / "marts"


@pytest.fixture(scope="session")
def warehouse() -> duckdb.DuckDBPyConnection:
    """Rebuild from the committed raw extracts, then hand tests a read-only connection.

    Building rather than reusing a stale file means the suite is testing the SQL in the
    repo, not whatever happened to be on disk.
    """
    subprocess.run(
        [sys.executable, str(ROOT / "src" / "build_marts.py")],
        check=True, cwd=ROOT, capture_output=True,
    )
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    yield con
    con.close()


@pytest.fixture(scope="session")
def marts_dir() -> Path:
    return MARTS_DIR
