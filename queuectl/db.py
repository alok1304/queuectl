from __future__ import annotations
import os
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from .constants import APP_DIRNAME, DB_FILENAME, DEFAULTS
from .util.time import utcnow_iso

_app_dir: Optional[Path] = None
_db_path: Optional[Path] = None


def app_dir() -> Path:
    global _app_dir
    if _app_dir is None:
        _app_dir = Path.home() / APP_DIRNAME
        _app_dir.mkdir(parents=True, exist_ok=True)
    return _app_dir


def db_path() -> Path:
    global _db_path
    if _db_path is None:
        _db_path = app_dir() / DB_FILENAME
    return _db_path


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """Create tables if they don't exist and seed default config."""
    conn = get_connection()
    cur = conn.cursor()

    # migrations (idempotent)
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            command TEXT NOT NULL,
            state TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            next_run_at TEXT,
            last_error TEXT,
            worker_id TEXT,
            lease_expires_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_state_next ON jobs(state, next_run_at);
        CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(lease_expires_at);

        CREATE TABLE IF NOT EXISTS workers (
            id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            last_heartbeat_at TEXT NOT NULL,
            hostname TEXT,
            pid INTEGER
        );

        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )

    # seed defaults
    for k, v in DEFAULTS.items():
        cur.execute("INSERT OR IGNORE INTO config(key, value) VALUES(?, ?)", (k, v))

    conn.commit()


def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = get_connection()
    row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    if row:
        return row[0]
    return default


def set_config(key: str, value: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO config(key, value) VALUES(?, ?)\n         ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


def all_config() -> dict:
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM config ORDER BY key").fetchall()
    return {r[0]: r[1] for r in rows}