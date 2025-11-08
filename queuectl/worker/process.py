from __future__ import annotations
import os
import time
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from rich.console import Console

from ..db import get_connection
from ..constants import JobState
from ..config import get_value
from ..util.ids import make_worker_id
from .executor import run_command

console = Console()


# -----------------------
# Time helpers (store UTC, SQLite-friendly)
# -----------------------
def _utcnow() -> datetime:
    # naive UTC (no tzinfo) for consistent strftime below
    return datetime.utcnow()

def _iso(dt: datetime) -> str:
    # Store as UTC "YYYY-MM-DD HH:MM:SS" so SQLite text compare works
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def _parse_db_ts(ts: str) -> datetime:
    """Parse timestamps we may encounter in DB:
    - 'YYYY-MM-DD HH:MM:SS'  (our current storage, treated as UTC)
    - 'YYYY-MM-DDTHH:MM:SS+00:00' (older rows)
    - '...Z' (rare older rows)
    Returns an aware datetime in UTC.
    """
    if ts is None:
        return None  # caller should handle
    try:
        if "T" in ts:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc)
        # plain format (UTC)
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        # Fallback: treat as now to avoid stalling
        return _utcnow().replace(tzinfo=timezone.utc)

def _to_ist(ts: str) -> str:
    """Convert DB timestamp string (UTC) to IST string for display only."""
    if ts is None:
        return "—"
    dt_utc = _parse_db_ts(ts)
    ist = dt_utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
    return ist.strftime("%Y-%m-%d %H:%M:%S IST")


def _intcfg(key: str, default: int) -> int:
    v = get_value(key, str(default))
    try:
        return int(v) if v is not None else default
    except ValueError:
        return default


# -----------------------
# Claim next job
# -----------------------
def _claim_next_job(conn: sqlite3.Connection, worker_id: str, lease_seconds: int) -> Optional[sqlite3.Row]:
    """Atomically claim the next eligible job.
    Eligible if:
      - state IN (pending, failed) AND (next_run_at IS NULL OR next_run_at <= now)
      - OR state = processing AND (lease_expires_at IS NULL OR lease_expires_at <= now)  (stale lease)
    """
    now_iso = _iso(_utcnow())
    cur = conn.cursor()
    conn.execute("BEGIN IMMEDIATE")

    row = cur.execute(
        """
        SELECT id
        FROM jobs
        WHERE
            (state IN (?, ?) AND (next_run_at IS NULL OR next_run_at <= ?))
            OR
            (state = ? AND (lease_expires_at IS NULL OR lease_expires_at <= ?))
        ORDER BY priority ASC, created_at ASC
        LIMIT 1
        """,
        (JobState.PENDING, JobState.FAILED, now_iso, JobState.PROCESSING, now_iso),
    ).fetchone()

    if not row:
        conn.commit()
        return None

    job_id = row[0]
    lease_expires = _iso(_utcnow() + timedelta(seconds=lease_seconds))

    updated = cur.execute(
        """
        UPDATE jobs
        SET state = ?, worker_id = ?, lease_expires_at = ?, updated_at = ?
        WHERE id = ?
          AND (
                (state IN (?, ?) AND (next_run_at IS NULL OR next_run_at <= ?))
                OR
                (state = ? AND (lease_expires_at IS NULL OR lease_expires_at <= ?))
              )
        """,
        (
            JobState.PROCESSING, worker_id, lease_expires, now_iso, job_id,
            JobState.PENDING, JobState.FAILED, now_iso,
            JobState.PROCESSING, now_iso,
        ),
    )

    if updated.rowcount != 1:
        conn.commit()
        return None

    job = cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.commit()
    return job


# -----------------------
# Job state updates
# -----------------------
def _complete_job(conn: sqlite3.Connection, job_id: str):
    now_iso = _iso(_utcnow())
    conn.execute(
        "UPDATE jobs SET state=?, updated_at=?, worker_id=NULL, lease_expires_at=NULL WHERE id=?",
        (JobState.COMPLETED, now_iso, job_id),
    )
    conn.commit()


def _fail_or_retry_job(conn: sqlite3.Connection, job: sqlite3.Row, stderr: str):
    now = _utcnow()
    now_iso = _iso(now)
    attempts = int(job["attempts"]) + 1
    max_retries = int(job["max_retries"])

    backoff_base = _intcfg("backoff_base", 2)
    max_backoff_seconds = _intcfg("max_backoff_seconds", 300)

    delay = min(backoff_base ** attempts, max_backoff_seconds)
    next_run_at = _iso(now + timedelta(seconds=delay))

    # Decide new state and next_run_at
    if attempts >= max_retries:
        state = JobState.DEAD
        next_run_at_val = None  # allow NULL in schema
    else:
        state = JobState.FAILED
        next_run_at_val = next_run_at

    # Default message if command produced no output
    msg = (stderr or "").strip()
    if not msg:
        msg = "Command failed (no output)"

    conn.execute(
        """
        UPDATE jobs
        SET state=?, attempts=?, next_run_at=?, last_error=?, updated_at=?, worker_id=NULL, lease_expires_at=NULL
        WHERE id=?
        """,
        (state, attempts, next_run_at_val, msg[:4000], now_iso, job["id"]),
    )
    conn.commit()
    return state, attempts, next_run_at_val


def _heartbeat(conn: sqlite3.Connection, worker_id: str, hostname: str, pid: int):
    now_iso = _iso(_utcnow())
    conn.execute(
        """
        INSERT INTO workers(id, started_at, last_heartbeat_at, hostname, pid)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET last_heartbeat_at=excluded.last_heartbeat_at
        """,
        (worker_id, now_iso, now_iso, hostname, pid),
    )
    conn.commit()


# -----------------------
# Main worker loop
# -----------------------
def worker_loop(stop_flag_path: str):
    worker_id = make_worker_id()
    hostname = os.uname().nodename if hasattr(os, "uname") else "win"
    pid = os.getpid()

    poll_interval_ms = _intcfg("poll_interval_ms", 500)
    lease_seconds = _intcfg("lease_seconds", 60)

    console.log(f"[bold cyan][{worker_id}] started[/]")

    conn = get_connection()

    try:
        while True:
            # graceful stop
            if os.path.exists(stop_flag_path):
                console.log(f"[{worker_id}] stop flag detected → exiting when idle")
                break

            _heartbeat(conn, worker_id, hostname, pid)

            job = _claim_next_job(conn, worker_id, lease_seconds)
            if not job:
                time.sleep(poll_interval_ms / 1000.0)
                continue

            job_id = job["id"]
            command = job["command"]
            console.log(f"[{worker_id}] Picked job: {job_id} | cmd: {command}")

            try:
                result = run_command(command)
                if result.returncode == 0:
                    _complete_job(conn, job_id)
                    console.log(f"[{worker_id}]  completed: {job_id}")
                else:
                    state, attempts, next_run_at = _fail_or_retry_job(conn, job, result.stderr or result.stdout)
                    if state == JobState.DEAD:
                        console.log(f"[{worker_id}]  DLQ: {job_id} (attempts {attempts})")
                    else:
                        # show UTC stored ts + IST display
                        ist_display = _to_ist(next_run_at)
                        console.log(f"[{worker_id}]  failed attempt {attempts}; retry at {next_run_at} ({ist_display})")
            except Exception as e:
                state, attempts, next_run_at = _fail_or_retry_job(conn, job, str(e))
                if state == JobState.DEAD:
                    console.log(f"[{worker_id}]  DLQ (exception): {job_id} (attempts {attempts})")
                else:
                    ist_display = _to_ist(next_run_at)
                    console.log(f"[{worker_id}]  exception; retry at {next_run_at} ({ist_display})")

    finally:
        # Best-effort final heartbeat
        try:
            _heartbeat(conn, worker_id, hostname, pid)
        except Exception:
            pass
        console.log(f"[{worker_id}] exiting")
