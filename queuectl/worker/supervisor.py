from __future__ import annotations
import os
import signal
import time
from multiprocessing import Process
from pathlib import Path
from typing import List

from rich.console import Console

from ..db import init_db
from ..constants import APP_DIRNAME
from .process import worker_loop

console = Console()


def _app_dir() -> Path:
    p = Path.home() / APP_DIRNAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def stop_flag_path() -> Path:
    return _app_dir() / "stop.flag"


def start_workers(count: int) -> None:
    init_db()
    # clear any previous stop flag
    try:
        stop_flag_path().unlink()
    except FileNotFoundError:
        pass

    procs: List[Process] = []

    def _spawn() -> Process:
        p = Process(target=worker_loop, args=(str(stop_flag_path()),), daemon=False)
        p.start()
        return p

    for _ in range(count):
        procs.append(_spawn())

    console.log(f"Supervisor started {count} workers. Press CTRL+C to stop.")

    try:
        # Keep the supervisor alive while children run
        while any(p.is_alive() for p in procs):
            time.sleep(0.5)
    except KeyboardInterrupt:
        console.log("Supervisor: CTRL+C received → graceful stop")
        request_stop()
        for p in procs:
            p.join()
    finally:
        # Cleanup stop flag
        try:
            stop_flag_path().unlink()
        except FileNotFoundError:
            pass


def request_stop() -> None:
    # Signal workers by creating the stop flag file
    stop_flag_path().write_text("stop")
    console.log("Requested workers to stop (flag written)")