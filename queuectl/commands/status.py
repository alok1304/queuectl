from __future__ import annotations
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table
from ..db import get_connection

console = Console()

def status():
    conn = get_connection()

    # job counts
    counts = conn.execute(
        "SELECT state, COUNT(*) as c FROM jobs GROUP BY state"
    ).fetchall()

    # workers
    workers = conn.execute(
        "SELECT id, last_heartbeat_at FROM workers ORDER BY last_heartbeat_at DESC"
    ).fetchall()

    # display jobs summary
    job_table = Table(title="Job Summary")
    job_table.add_column("state")
    job_table.add_column("count")
    for row in counts:
        job_table.add_row(row["state"], str(row["c"]))
    console.print(job_table)

    # display worker summary
    worker_table = Table(title="Workers (active heartbeat)")
    worker_table.add_column("id")
    worker_table.add_column("last seen (sec ago)")

    now = datetime.now(timezone.utc)
    for w in workers:
        last = datetime.fromisoformat(w["last_heartbeat_at"])

        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)

        age = int((now - last).total_seconds())
        worker_table.add_row(w["id"], str(age))

    console.print(worker_table)