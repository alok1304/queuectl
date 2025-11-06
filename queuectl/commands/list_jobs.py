from __future__ import annotations
from rich.console import Console
from rich.table import Table
from ..db import get_connection
from ..constants import JobState

console = Console()

def list_jobs(state: str):
    valid = [s.value for s in JobState]
    if state not in valid:
        console.print(f"[red]Invalid state. Must be one of: {', '.join(valid)}")
        return

    conn = get_connection()
    rows = conn.execute(
        "SELECT id, state, attempts, next_run_at, last_error FROM jobs WHERE state=? ORDER BY created_at",
        (state,),
    ).fetchall()

    table = Table(title=f"Jobs in state: {state}")
    table.add_column("id")
    table.add_column("state")
    table.add_column("attempts")
    table.add_column("next_run_at")
    table.add_column("last_error")

    for r in rows:
        table.add_row(r["id"], r["state"], str(r["attempts"]), r["next_run_at"], (r["last_error"] or ""))

    console.print(table)