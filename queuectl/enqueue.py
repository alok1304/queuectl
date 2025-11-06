import json
from rich.console import Console
from .db import get_connection
from .models import Job
from .util.time import utcnow_iso

console = Console()


def enqueue_job(payload: str):
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        console.print("[red]Invalid JSON passed to enqueue[/]")
        return

    if "id" not in data or "command" not in data:
        console.print("[red]Job must contain 'id' and 'command' fields[/]")
        return

    job = Job(id=data["id"], command=data["command"])

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO jobs(id, command, state, attempts, max_retries,
                created_at, updated_at, next_run_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.command,
                job.state,
                job.attempts,
                job.max_retries,
                job.created_at,
                utcnow_iso(),
                job.next_run_at,
            ),
        )
        conn.commit()
        console.print(f"[green]Job enqueued:[/] {job.id}")
    except Exception as e:
        console.print(f"[red]Failed to enqueue job:[/] {e}")