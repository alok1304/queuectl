from queuectl.db import get_connection
from queuectl.enqueue import enqueue_job

def test_basic_enqueue():
    enqueue_job('{"id":"t1","command":"echo hi"}')
    conn = get_connection()
    row = conn.execute("SELECT state FROM jobs WHERE id='t1'").fetchone()
    assert row["state"] == "pending"