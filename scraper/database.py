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
    dates          TEXT    DEFAULT '[]',
    is_changed     INTEGER DEFAULT 0,
    change_details TEXT    DEFAULT NULL,
    created_at     TEXT    NOT NULL
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
    """Create tables if they do not already exist, and run pending migrations."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript(_DDL)
        # Migration: add is_changed column for DBs created before this column existed
        try:
            conn.execute("ALTER TABLE schedule ADD COLUMN is_changed INTEGER DEFAULT 0")
            logger.info("Migration: added is_changed column to schedule table.")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE schedule ADD COLUMN change_details TEXT DEFAULT NULL")
            logger.info("Migration: added change_details column to schedule table.")
        except sqlite3.OperationalError:
            pass  # Column already exists
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


def fetch_fingerprints(db_path: Path = DB_PATH) -> dict:
    """
    Return a dict mapping (group_name, subject, day) → field snapshot.
    Used before clearing the table so per-field changes can be detected after re-insert.
    """
    with _connect(db_path) as conn:
        cur = conn.execute(
            "SELECT group_name, subject, day, time_start, time_end, class_mode, room, instructor, dates FROM schedule"
        )
        result: dict = {}
        for row in cur.fetchall():
            key = (row[0], row[1], row[2])
            result[key] = {
                "time_start": row[3],
                "time_end":   row[4],
                "class_mode": row[5],
                "room":       row[6],
                "instructor": row[7],
                "dates":      row[8],
            }
        return result


def clear_changed_flags(db_path: Path = DB_PATH) -> None:
    """Reset all is_changed flags and change_details (called when PDF is unchanged)."""
    with _connect(db_path) as conn:
        conn.execute("UPDATE schedule SET is_changed = 0, change_details = NULL")
    logger.debug("Cleared all is_changed flags and change_details.")


def mark_changed_entries(prev: dict, db_path: Path = DB_PATH) -> int:
    """
    Compare newly inserted rows against *prev* snapshots field-by-field.
    Stores a JSON list of changed fields in change_details.
    Returns 0 immediately when *prev* is empty (fresh DB – nothing to compare).
    Returns the count of changed entries.
    """
    if not prev:
        logger.debug("mark_changed_entries: prev dict is empty (fresh DB) – skipping.")
        return 0
    with _connect(db_path) as conn:
        cur = conn.execute(
            "SELECT id, group_name, subject, day, time_start, time_end, class_mode, room, instructor, dates FROM schedule"
        )
        updates: list[tuple] = []
        for row in cur.fetchall():
            id_, group, subject, day = row[0], row[1], row[2], row[3]
            ts, te, cmode, room, instr, dates = row[4], row[5], row[6], row[7], row[8], row[9]
            key = (group, subject, day)
            if key not in prev:
                changes: list[dict] = [{"field": "new", "label": "Nowe zajęcia"}]
            else:
                old = prev[key]
                changes = []
                for field, label, new_val in [
                    ("time_start", "Godzina od",  ts),
                    ("time_end",   "Godzina do",  te),
                    ("room",       "Sala",         room),
                    ("class_mode", "Tryb",         cmode),
                    ("instructor", "Prowadzący",   instr),
                    ("dates",      "Terminy",      dates),
                ]:
                    if old.get(field, "") != new_val:
                        changes.append({"field": field, "label": label,
                                        "old": old.get(field, ""), "new": new_val})
            if changes:
                updates.append((json.dumps(changes, ensure_ascii=False), id_))
        if updates:
            conn.executemany(
                "UPDATE schedule SET is_changed = 1, change_details = ? WHERE id = ?",
                updates,
            )
    count = len(updates)
    if count:
        logger.info("%d entr%s marked as changed.", count, "y" if count == 1 else "ies")
    return count


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
