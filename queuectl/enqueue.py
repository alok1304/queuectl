import json
from rich.console import Console
from datetime import datetime, timedelta, timezone

from .db import get_connection
from .models import Job
from .config import get_value

console = Console()


def _ts_now():
    """Return UTC timestamp formatted for SQLite."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _ts_after_delay(seconds: int):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")


def enqueue_job(
    payload: str,
    max_retries: int | None = None,
    priority: int = 5,
    run_at: str | None = None,
    delay: int | None = None,
):
    """
    Enqueue a job into SQLite storage.

    Order of max_retries priority:
    1. CLI flag (--max-retries)
    2. JSON payload value
    3. Global config default
    """

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        console.print("[red]Invalid JSON passed to enqueue[/]")
        return

    if "id" not in data or "command" not in data:
        console.print("[red]Job must contain 'id' and 'command' fields[/]")
        return

    # Determine effective max_retries
    payload_max = data.get("max_retries")
    if max_retries is not None:      # CLI wins
        retries = int(max_retries)
    elif payload_max is not None:    # payload wins next
        retries = int(payload_max)
    else:                            # global config fallback
        retries = int(get_value("max_retries", "3"))

    # Determine scheduling
    if delay:
        next_run_at = _ts_after_delay(delay)
    elif run_at:
        next_run_at = run_at  # used as provided
    else:
        next_run_at = _ts_now()

    # Determine priority
    priority = int(priority or data.get("priority", 5))

    job = Job(
        id=data["id"],
        command=data["command"],
        max_retries=retries,
        priority=priority,
        next_run_at=next_run_at,
    )

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO jobs(id, command, state, attempts, max_retries, priority,
                             created_at, updated_at, next_run_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.command,
                "pending",
                0,
                job.max_retries,
                job.priority,
                _ts_now(),
                _ts_now(),
                job.next_run_at,
            ),
        )
        conn.commit()

        console.print(
            f"[green]Job enqueued:[/] {job.id}  "
            f"(priority={priority}, next_run_at={next_run_at}, retries={retries})"
        )

    except Exception as e:
        console.print(f"[red]Failed to enqueue job:[/] {e}")
