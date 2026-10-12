"""SQLite per stato strutturato ricostruibile (attività, agenda, promemoria, routine)."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from app.config import DB_PATH, ensure_dirs

_lock = threading.RLock()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    with _lock:
        conn = connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 2,
                due_at TEXT,
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                source TEXT DEFAULT 'user'
            );

            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                starts_at TEXT NOT NULL,
                ends_at TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                due_at TEXT NOT NULL,
                notified_at TEXT,
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS routine_runs (
                id TEXT PRIMARY KEY,
                routine_id TEXT NOT NULL,
                planned_for TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                status TEXT NOT NULL,
                detail TEXT,
                UNIQUE(routine_id, planned_for)
            );

            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT NOT NULL,
                detail TEXT
            );

            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                name TEXT NOT NULL,
                value REAL NOT NULL,
                source TEXT NOT NULL,
                UNIQUE(day, name, source)
            );

            CREATE TABLE IF NOT EXISTS note_index (
                path TEXT PRIMARY KEY,
                title TEXT,
                tags TEXT,
                mtime REAL NOT NULL,
                body TEXT NOT NULL,
                links TEXT DEFAULT ''
            );
            """
        )
        cols = {r[1] for r in conn.execute("PRAGMA table_info(note_index)").fetchall()}
        if "links" not in cols:
            conn.execute("ALTER TABLE note_index ADD COLUMN links TEXT DEFAULT ''")


def log_action(kind: str, status: str, summary: str, detail: str | None = None) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO action_log (created_at, kind, status, summary, detail) VALUES (?, ?, ?, ?, ?)",
            (utc_now(), kind, status, summary, detail),
        )


def recent_actions(limit: int = 20) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT created_at, kind, status, summary, detail FROM action_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
