from __future__ import annotations
from rich.console import Console
from rich.table import Table
from ..db import get_connection
from ..constants import JobState
from ..util.time import utcnow_iso

console = Console()


def dlq_list():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, attempts, last_error FROM jobs WHERE state=? ORDER BY updated_at DESC",
        (JobState.DEAD,),
    ).fetchall()

    table = Table(title="Dead Letter Queue (DLQ)")
    table.add_column("id")
    table.add_column("attempts")
    table.add_column("last_error")

    for r in rows:
        table.add_row(r["id"], str(r["attempts"]), r["last_error"] or "")

    console.print(table)


def dlq_retry(job_id: str):
    conn = get_connection()

    # Reset values
    conn.execute(
        "UPDATE jobs SET state=?, attempts=0, next_run_at=?, last_error=NULL WHERE id=? AND state=?",
        (JobState.PENDING, utcnow_iso(), job_id, JobState.DEAD),
    )
    conn.commit()
    console.print(f"[green] Job {job_id} moved back to queue[/]")