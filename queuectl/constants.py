from enum import Enum

class JobState(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"


DEFAULTS = {
"max_retries": "3",
"backoff_base": "2",
"poll_interval_ms": "500",
"lease_seconds": "60",
"max_backoff_seconds": "300",
}


APP_DIRNAME = ".queuectl"
DB_FILENAME = "queue.db"