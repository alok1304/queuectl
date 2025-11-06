#!/bin/bash
echo "=== QueueCTL Demo Flow ==="

rm ~/.queuectl/queue.db 2>/dev/null

echo "1) Enqueue jobs"
queuectl enqueue --id succeed1 --cmd "echo JobSuccess"
queuectl enqueue --id fail1 --cmd "bash -c 'exit 1'"

echo "2) Start workers"
queuectl worker start --count 2 &
WORKER_PID=$!

sleep 8

echo "3) Show status"
queuectl status

echo "4) Show DLQ"
queuectl dlq list

echo "5) Retry DLQ jobs"
queuectl dlq retry fail1

echo "6) Status after retry"
queuectl status

echo "7) Stop workers"
queuectl worker stop
wait $WORKER_PID
