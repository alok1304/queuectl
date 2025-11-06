from dataclasses import dataclass
from typing import Optional
from .constants import JobState
from .util.time import utcnow_iso
from .config import get_value

@dataclass
class Job:
    id: str
    command: str
    state: str = JobState.PENDING
    attempts: int = 0
    max_retries: int = int(get_value("max_retries", "3"))
    created_at: str = utcnow_iso()
    updated_at: str = utcnow_iso()
    next_run_at: str = utcnow_iso()
    last_error: Optional[str] = None
    worker_id: Optional[str] = None
    lease_expires_at: Optional[str] = None