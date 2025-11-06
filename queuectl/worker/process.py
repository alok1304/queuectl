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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _intcfg(key: str, default: int) -> int:
    v = get_value(key, str(default))
    try:
        return int(v) if v is not None else default
    except ValueError:
        return default


def _claim_next_job(conn: sqlite3.Connection, worker_id: str, lease_seconds: int) -> Optional[sqlite3.Row]:
    """Atomically claim the next eligible pending job.
    Strategy: pick one id then conditional-update. Return the row if claimed.
    """
    now_iso = _iso(_utcnow())
    cur = conn.cursor()
    conn.execute("BEGIN IMMEDIATE")
    row = cur.execute(
        """
        SELECT id FROM jobs
        WHERE
            (state = ? AND next_run_at <= ?) OR
            (state = ? AND lease_expires_at <= ?)
        ORDER BY created_at ASC
        LIMIT 1
        """,
        (JobState.PENDING, now_iso, JobState.PROCESSING, now_iso),
    ).fetchone()
    if not row:
        conn.commit()
        return None

    job_id = row[0]
    lease_expires = _iso(_utcnow() + timedelta(seconds=lease_seconds))
    updated = cur.execute(
        """
        UPDATE jobs
        SET state=?, worker_id=?, lease_expires_at=?, updated_at=?
        WHERE id=? AND state=? AND next_run_at<=?
        """,
        (JobState.PROCESSING, worker_id, lease_expires, now_iso, job_id, JobState.PENDING, now_iso),
    )
    if updated.rowcount != 1:
        conn.commit()
        return None

    # Fetch the full job row
    job = cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.commit()
    return job


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

    if attempts > max_retries:
        # Move to DLQ (dead)
        state = JobState.DEAD
        next_run_at_val = job["next_run_at"]  # irrelevant
    else:
        state = JobState.FAILED
        next_run_at_val = next_run_at

    conn.execute(
        """
        UPDATE jobs
        SET state=?, attempts=?, next_run_at=?, last_error=?, updated_at=?, worker_id=NULL, lease_expires_at=NULL
        WHERE id=?
        """,
        (state, attempts, next_run_at_val, (stderr or "").strip()[:4000], now_iso, job["id"]),
    )
    conn.commit()
    return state, attempts, next_run_at


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
            # external graceful stop
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
                        console.log(f"[{worker_id}]  failed attempt {attempts}; retry at {next_run_at}")
            except Exception as e:
                # Treat unexpected exceptions as failures, record message
                state, attempts, next_run_at = _fail_or_retry_job(conn, job, str(e))
                if state == JobState.DEAD:
                    console.log(f"[{worker_id}]  DLQ (exception): {job_id} (attempts {attempts})")
                else:
                    console.log(f"[{worker_id}]  exception; retry at {next_run_at}")

    finally:
        # Best-effort final heartbeat so status can show recent activity
        try:
            _heartbeat(conn, worker_id, hostname, pid)
        except Exception:
            pass
        console.log(f"[{worker_id}] exiting")