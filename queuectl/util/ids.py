import os, socket, random

def make_worker_id(prefix: str = "worker") -> str:
    host = socket.gethostname()
    pid = os.getpid()
    rand = random.randint(1000, 9999)
    return f"{prefix}-{host}-{pid}-{rand}"