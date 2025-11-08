# queuectl – CLI Background Job Queue (Python)

`queuectl` is a CLI-based asynchronous background job queue system. It allows you to enqueue jobs, process them using worker processes, retry failed jobs with exponential backoff, and handle permanently failed jobs using a Dead Letter Queue (DLQ).

Built as a backend engineering assignment with **production‑readable architecture**.

---
## ✨ Features
- ✅ Enqueue jobs via CLI (`echo`, `sleep`, Python scripts, etc.)
- ✅ Workers execute jobs in background
- ✅ Multiple workers in parallel — `queuectl worker start --count 3`
- ✅ Retries failed jobs using **exponential backoff**
- ✅ Moves failed jobs into **DLQ** after retry limit
- ✅ Job persistence using **SQLite**
- ✅ Graceful shutdown
- ✅ Configuration management via CLI
- ✅ README included
- ✅ Testing

---
## 🧪 Advanced Features Summary
| Feature | CLI Support | Status |
|---------|------------|--------|
| Scheduled jobs | `--run-at` / `--delay` | ✅
| Priority queue | `--priority` | ✅
| Per-job retry | `--max-retries` | ✅
| DLQ retry | `queuectl dlq retry <id>` | ✅

---
## 📁 File/folder structure
```
queuectl/
├─ README.md
├─ pyproject.toml 
├─ queuectl/
│  ├─ __init__.py
│  ├─ cli.py                 
│  ├─ config.py               
│  ├─ db.py                  
│  ├─ models.py                
│  ├─ enqueue.py            
│  ├─ worker/
│  │  ├─ __init__.py
│  │  ├─ supervisor.py        
│  │  ├─ process.py          
│  │  └─ executor.py         
│  ├─ commands/
│  │  ├─ status.py            
│  │  ├─ list_jobs.py
│  │  └─ dlq.py
│  │  
│  ├─ util/
│  │  ├─ time.py               
│  │  └─ ids.py              
│  │  
│  └─ constants.py            
└─ tests/
   ├─ demo_flow.ps1
   ├─ demo_flow.sh
   └─ test_enqueue_and_process.py

```

---
## 🏗 Architecture Diagram
```
┌──────────────┐     enqueue job      ┌──────────────┐
│ queuectl CLI │ ───────────────────▶ │ SQLite (DB)  |
└──────┬───────┘                      └──────┬───────┘
       │   worker polling (pending jobs)     │
       │                                     │
┌──────▼────────┐  executes cmd    ┌──────────▼─────────┐
│ Worker Process│──────────────▶  │ OS Shell / Command │
└───────────────┘                  └────────────────────┘
```

- Uses safe **atomic job claiming** to prevent duplicate processing.
- Workers update DB with job status.

---
## 📦 Installation

### 🔹 Clone the Repository
```sh
git clone https://github.com/alok1304/queuectl
cd queuectl
```

### 🔹 Install (Editable mode)
```sh
pip install -e .   # install in editable mode
```

---
## 🚀 Usage
### ➕ Enqueue a job
#### Option 1 → Using flags ✅
```sh
queuectl enqueue --id job1 --cmd "echo Hello"
```

#### Option 2 → Using JSON file ✅
Create `job.json`:
```json
{ "id": "job2", "command": "echo from file" }
```
Run:
```sh
queuectl enqueue --file job.json
```

---
### 🔧 Start workers
```sh
queuectl worker start --count 3
```
Press `CTRL + C` to stop gracefully or:
```sh
queuectl worker stop
```

---
### 📊 Job Status
```sh
queuectl status
```

### 📋 List jobs by state
```sh
queuectl list --state pending
```

### 🪦 Dead Letter Queue (DLQ)

List failed jobs moved to DLQ:
```sh
queuectl dlq list
```

Retry a DLQ job:
```sh
queuectl dlq retry job_id
```

---
## 🛠 Configuration

Example:
```sh
queuectl config set max-retries 3
queuectl config set backoff-base 2
```
Show current config:
```sh
queuectl config show
```

---
## ⚙ Options & Defaults

| Config Key | Purpose | Default |
|------------|----------|----------|
| `max_retries` | Max retry attempts | `3` |
| `backoff_base` | Retry delay exponent base | `2` |
| `poll_interval_ms` | Worker job check interval | `500ms` |
| `lease_seconds` | Time before job can be re‑claimed | `60 sec` |

---
## 💡 Exponential Backoff

Formula:
```
delay = base ^ attempts
```

Retry example (`base = 2`):
| Attempt | Delay |
|--------|--------|
| 1      | 2s     |
| 2      | 4s     |
| 3      | 8s     |



---
## 📜 Logging Example

```
[worker-10293] Picked job: job1 | cmd: echo Hello
[worker-10293] ✅ completed: job1
[worker-20383] failed attempt 1; retry at 2025‑01‑10T10:35:00Z
[worker-20383] 🔥 DLQ: job2
```

---
## 🚀 Advanced / Bonus Features

### ✅ Scheduled / Delayed Jobs (`--run-at`, `--delay`)
You can schedule a job to run at a **future timestamp**:
```sh
queuectl enqueue --id futureJob --cmd "echo running later" --run-at "2025-11-10 09:30:00"
```
Or delay execution by seconds:
```sh
queuectl enqueue --id delayed --cmd "echo after delay" --delay 10
```
Workers automatically pick the job only when the scheduled time arrives.

---
### ✅ Priority Queue Support (`--priority`)
Jobs can be enqueued with priority (`1 = highest priority`, `5 = default`):
```sh
queuectl enqueue --id urgent --cmd "echo urgent task" --priority 1
queuectl enqueue --id normal --cmd "echo normal task" --priority 5
```
The worker always picks **higher‑priority jobs first**.

---
### ✅ Per‑Job Retry Control (`--max-retries`)
```sh
queuectl enqueue --id failOnce --cmd "cmd /c exit 1" --max-retries 1
```
This overrides global config.

---
### 🧪 Advanced Features Summary
| Feature | CLI Support | Status |
|---------|------------|--------|
| Scheduled jobs | `--run-at` / `--delay` | ✅
| Priority queue | `--priority` | ✅
| Per-job retry | `--max-retries` | ✅
| DLQ retry | `queuectl dlq retry <id>` | ✅

---
## 🧪 Test Scenarios (all passed)

- ✅ Working CLI application (`queuectl`)
- ✅ Persistent job storage (SQLite)
- ✅ Multiple worker support (parallel worker processes)
- ✅ Retry mechanism with exponential backoff
- ✅ Dead Letter Queue (DLQ)
- ✅ Configuration management (config set/get)
- ✅ Clean CLI interface (commands & help texts)
- ✅ Comprehensive README.md
- ✅ Code structured with clear separation of concerns
- ✅ At least minimal testing or script to validate core flows

---
## 🧪 Testing / Validation Instructions / Validation Instructions

### ✅ Automated Demo Test (end‑to‑end flow)

Run the script that validates all core behaviors:

#### **Windows (PowerShell)**
```powershell
./tests/demo_flow.ps1
```

#### **Linux / macOS**
```bash
./tests/demo_flow.sh
```

This verifies:
| Step | Expected Behavior |
|------|------------------|
| Enqueue `succeed1` & `fail1` | Jobs appear in DB (`pending`) |
| Worker picks `succeed1` | Job logs show ✅ `completed` |
| Worker picks `fail1` | Shows ❌ `failed attempt n` and schedules retry with exponential backoff |
| Job moves to DLQ | `queuectl dlq list` shows job after retries exhausted |
| Retry DLQ job | `queuectl dlq retry <id>` moves job back to queue |
| Stop workers | Workers finish current job and exit `gracefully` |

Example output:
```
=== QueueCTL Demo Flow ===

1) Enqueue jobs
Job enqueued: succeed1  (priority=5, next_run_at=2025-11-08 06:14:21, retries=3)
Job enqueued: fail1     (priority=5, next_run_at=2025-11-08 06:14:22, retries=3)

2) Start workers
Picked job: succeed1 | cmd: echo JobSuccess
✅ completed: succeed1

Picked job: fail1 | cmd: cmd /c exit 1
❌ failed attempt 1; retry at 2025-11-08 06:14:25 (2025-11-08 11:44:25 IST)

Picked job: fail1 | cmd: cmd /c exit 1
❌ failed attempt 2; retry at 2025-11-08 06:14:29 (2025-11-08 11:44:29 IST)

Picked job: fail1 | cmd: cmd /c exit 1
🟥 DLQ: fail1 (attempts 3)

3) Status
completed: 1
dead: 1

4) DLQ
fail1 (1 attempt, error saved)

5) Retry DLQ jobs
✅ Job fail1 moved back to queue

6) Stop workers
stop flag detected → exiting when idle

```

This script meets the requirement: **“At least minimal testing or script to validate core flows.”**

---

### Author
**Alok Kumar** 


