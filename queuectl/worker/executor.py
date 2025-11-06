from __future__ import annotations
import subprocess
from dataclasses import dataclass
import os

@dataclass
class ExecResult:
    returncode: int
    stdout: str
    stderr: str


def run_command(cmd: str, timeout: int | None = None) -> ExecResult:
    # shell=True to allow simple commands like `echo hi` or `sleep 2`
    completed = subprocess.run(
        cmd,
        shell=True,
         executable="/bin/bash" if os.name != "nt" else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return ExecResult(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )