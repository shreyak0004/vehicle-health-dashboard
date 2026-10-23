"""Small helper functions for opening the SQLite database."""
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_db_path():
    # The VEHICLE_DB environment variable lets tests use a temporary database.
    return Path(os.environ.get("VEHICLE_DB", BASE_DIR / "vehicle.db"))


def get_connection():
    """Read/write connection. Only the simulator should use this."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row   # lets us read rows like dictionaries
    return conn


def get_readonly_connection():
    """Read-only connection. The AI assistant uses this one, so it is
    physically unable to change vehicle data (a simple safety isolation)."""
    uri = f"{get_db_path().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(reset=False):
    """Create the tables. reset=True deletes the old database first."""
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if reset and path.exists():
        path.unlink()

    with get_connection() as conn:
        conn.executescript(
            SCHEMA_PATH.read_text(encoding="utf-8")
        )
