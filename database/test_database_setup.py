import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import init_db, get_readonly_connection

init_db()

with get_readonly_connection() as conn:
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()

    print("Tables:", [row["name"] for row in tables])

print("Database setup successful!")
