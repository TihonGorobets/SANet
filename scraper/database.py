"""
database.py
SQLite persistence layer for schedule entries.

Schema
------
schedule
    id          INTEGER PRIMARY KEY AUTOINCREMENT
    group_name  TEXT NOT NULL
    subject     TEXT NOT NULL
    class_type  TEXT    class_mode  TEXT    instructor  TEXT
    room        TEXT
    day         TEXT
    time_start  TEXT
    time_end    TEXT
    dates       TEXT   -- JSON-encoded list of date strings
    created_at  TEXT   -- ISO-8601 timestamp

meta
    key    TEXT PRIMARY KEY
    value  TEXT
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from .config import DB_PATH

logger = logging.getLogger(__name__)

# ── schema ────────────────────────────────────────────────────────────────────
_DDL = """
CREATE TABLE IF NOT EXISTS schedule (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name  TEXT    NOT NULL,
    subject     TEXT    NOT NULL,
    class_type  TEXT    DEFAULT '',
    class_mode  TEXT    DEFAULT '',
    instructor  TEXT    DEFAULT '',
    room        TEXT    DEFAULT '',
    day         TEXT    DEFAULT '',
    time_start  TEXT    DEFAULT '',
    time_end    TEXT    DEFAULT '',
    dates       TEXT    DEFAULT '[]',
    is_changed  INTEGER DEFAULT 0,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
"""


# ── connection helper ─────────────────────────────────────────────────────────

@contextmanager
def _connect(db_path: Path = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """Yield an open, auto-committing :class:`sqlite3.Connection`."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── public API ────────────────────────────────────────────────────────────────

def init_db(db_path: Path = DB_PATH) -> None:
    """Create tables if they do not already exist."""
    with _connect(db_path) as conn:
        conn.executescript(_DDL)
    logger.info("Database initialised at %s", db_path)


def clear_schedule(db_path: Path = DB_PATH) -> int:
    """Delete all rows from the *schedule* table and return the count deleted."""
    with _connect(db_path) as conn:
        cur    = conn.execute("SELECT COUNT(*) FROM schedule")
        before = cur.fetchone()[0]
        conn.execute("DELETE FROM schedule")
    logger.info("Cleared %d stale schedule row(s).", before)
    return before


def insert_entries(entries: list[dict], db_path: Path = DB_PATH) -> int:
    """
    Bulk-insert *entries* into the *schedule* table.
    Returns the number of rows inserted.
    """
    if not entries:
        logger.warning("insert_entries called with empty list – nothing written.")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    rows = [
        (
            e["group_name"],
            e["subject"],
            e.get("class_type", ""),
            e.get("class_mode", ""),
            e.get("instructor", ""),
            e.get("room", ""),
            e.get("day", ""),
            e.get("time_start", ""),
            e.get("time_end", ""),
            e.get("dates", "[]"),
            now,
        )
        for e in entries
    ]

    with _connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO schedule
                (group_name, subject, class_type, class_mode, instructor, room,
                 day, time_start, time_end, dates, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    logger.info("Inserted %d schedule row(s).", len(rows))
    return len(rows)


def fetch_fingerprints(db_path: Path = DB_PATH) -> set[tuple]:
    """
    Return a set of fingerprint tuples for the current entries.
    Used before clearing the table so changes can be detected after re-insert.
    A fingerprint captures: group, subject, day, start time, end time, mode, room.
    """
    with _connect(db_path) as conn:
        cur = conn.execute(
            "SELECT group_name, subject, day, time_start, time_end, class_mode, room FROM schedule"
        )
        return {tuple(row) for row in cur.fetchall()}


def mark_changed_entries(prev: set[tuple], db_path: Path = DB_PATH) -> int:
    """
    Mark newly inserted rows whose fingerprint was absent in *prev* as changed.
    Returns the count of changed entries.
    """
    with _connect(db_path) as conn:
        cur = conn.execute(
            "SELECT id, group_name, subject, day, time_start, time_end, class_mode, room FROM schedule"
        )
        changed_ids = [
            row[0] for row in cur.fetchall()
            if tuple(row[1:]) not in prev
        ]
        if changed_ids:
            conn.executemany(
                "UPDATE schedule SET is_changed = 1 WHERE id = ?",
                [(i,) for i in changed_ids],
            )
    if changed_ids:
        logger.info("%d entr%s marked as changed.", len(changed_ids), "y" if len(changed_ids) == 1 else "ies")
    return len(changed_ids)


def fetch_all(db_path: Path = DB_PATH) -> list[dict]:
    """Return all schedule rows as a list of plain dicts."""
    with _connect(db_path) as conn:
        cur  = conn.execute(
            "SELECT * FROM schedule ORDER BY day, time_start, group_name"
        )
        rows = [dict(row) for row in cur.fetchall()]

    for row in rows:
        # Deserialise the JSON dates field
        try:
            row["dates"] = json.loads(row["dates"])
        except (json.JSONDecodeError, TypeError):
            row["dates"] = []

    logger.debug("Fetched %d row(s) from schedule.", len(rows))
    return rows


def set_meta(key: str, value: str, db_path: Path = DB_PATH) -> None:
    """Upsert a key/value pair in the *meta* table."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_meta(key: str, db_path: Path = DB_PATH) -> str | None:
    """Return the value for *key* from *meta*, or ``None`` if absent."""
    with _connect(db_path) as conn:
        cur = conn.execute("SELECT value FROM meta WHERE key = ?", (key,))
        row = cur.fetchone()
    return row[0] if row else None
