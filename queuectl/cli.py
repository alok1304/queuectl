from __future__ import annotations
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .config import get_value, set_value, get_all, ensure_bootstrapped

app = typer.Typer(add_completion=False, help="queuectl — background job queue (Milestone 1)")
console = Console()


@app.callback()
def _bootstrap() -> None:
    """Ensure DB is initialized before any command."""
    ensure_bootstrapped()


# ---------------------------
# config group
# ---------------------------
config_app = typer.Typer(help="Manage queuectl configuration")
app.add_typer(config_app, name="config")


@config_app.command("get")
def config_get(key: str = typer.Argument(..., help="Config key (e.g., max_retries)")):
    value = get_value(key)
    if value is None:
        console.print(f"[yellow]{key}[/] is not set")
        raise typer.Exit(code=1)
    console.print(value)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key (e.g., max_retries)"),
    value: str = typer.Argument(..., help="Value as string (e.g., 3)"),
):
    set_value(key, value)
    console.print(f"[green]OK[/] {key}={value}")


@config_app.command("show")
def config_show():
    cfg = get_all()
    table = Table(title="queuectl config")
    table.add_column("key")
    table.add_column("value")
    for k, v in cfg.items():
        table.add_row(k, v)
    console.print(table)

@app.command("enqueue")
def enqueue(
    job_id: str = typer.Option(None, "--id", "-i"),
    command: str = typer.Option(None, "--cmd", "-c"),
    file: str = typer.Option(None, "--file", "-f"),
    max_retries: int | None = typer.Option(None, "--max-retries", "-r"),
    priority: int = typer.Option(5, "--priority", "-p", help="Lower number = higher priority (default = 5)"),
    run_at: str = typer.Option(None, "--run-at", help="Schedule timestamp (YYYY-MM-DD HH:MM:SS)"),
    delay: int = typer.Option(None, "--delay", help="Delay execution in seconds"),
):
    from .enqueue import enqueue_job
    import json, os
    if file:
        if not os.path.exists(file):
            console.print(f"[red]File not found[/]: {file}")
            raise typer.Exit(1)
        with open(file, "r") as f:
            enqueue_job(f.read())
        return
    if not job_id or not command:
        console.print("[red]Either --file OR (--id AND --cmd) must be provided.[/]")
        raise typer.Exit(1)
    enqueue_job(json.dumps({"id": job_id, "command": command}), max_retries=max_retries, priority=priority, run_at=run_at, delay=delay)


# ---------------------------
# worker group
# ---------------------------
worker_app = typer.Typer(help="Manage workers")
app.add_typer(worker_app, name="worker")


@worker_app.command("start")
def worker_start(
    count: int = typer.Option(1, "--count", "-n", help="Number of worker processes"),
):
    from .worker.supervisor import start_workers
    start_workers(count)


@worker_app.command("stop")
def worker_stop():
    from .worker.supervisor import request_stop
    request_stop()


# ---------------------------
# status
# ---------------------------
@app.command("status")
def _status():
    from .commands.status import status
    status()

# ---------------------------
# list
# ---------------------------
@app.command("list")
def _list(state: str = typer.Option(..., "--state", help="Job state to filter")):
    from .commands.list_jobs import list_jobs
    list_jobs(state)

# ---------------------------
# dlq
# ---------------------------
dlq_app = typer.Typer(help="Dead Letter Queue commands")
app.add_typer(dlq_app, name="dlq")

@dlq_app.command("list")
def _dlq_list():
    from .commands.dlq import dlq_list
    dlq_list()

@dlq_app.command("retry")
def _dlq_retry(job_id: str = typer.Argument(...)):
    from .commands.dlq import dlq_retry
    dlq_retry(job_id)
    
if __name__ == "__main__":
    app()