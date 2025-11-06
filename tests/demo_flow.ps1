Write-Host "=== QueueCTL Demo Flow ===" -ForegroundColor Cyan

# 0. Clean old db (optional)
Remove-Item "$env:USERPROFILE\.queuectl\queue.db" -ErrorAction SilentlyContinue

Write-Host "`n1) Enqueue jobs"
queuectl enqueue --id succeed1 --cmd "echo JobSuccess"

# failing command
queuectl enqueue --id fail1 --cmd "cmd /c exit 1"

Write-Host "`n2) Start workers"
Start-Process powershell -ArgumentList "queuectl worker start --count 2" -NoNewWindow

Start-Sleep -Seconds 8

Write-Host "`n3) Show status"
queuectl status

Write-Host "`n4) Show DLQ"
queuectl dlq list

Write-Host "`n5) Retry DLQ jobs"
queuectl dlq retry fail1

Write-Host "`n6) Status after retry"
queuectl status

Write-Host "`n7) Stop workers"
queuectl worker stop
