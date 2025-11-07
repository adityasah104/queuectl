# 🧠 QueueCTL — CLI-Based Background Job Queue System

### 🚀 A production-grade background job management system built in **Python**  
with **CLI**, **SQLite persistence**, **multi-worker execution**, **retries with exponential backoff**, **Dead Letter Queue (DLQ)**, and a **real-time dashboard**.

---

## 🧩 Overview

`QueueCTL` is a command-line tool and lightweight background job system that manages asynchronous jobs.  
It allows you to enqueue tasks, process them using multiple workers, retry on failures, move failed jobs to a **Dead Letter Queue**, and even visualize queue health through a **web dashboard**.

---

## 🛠️ Tech Stack

| Component | Technology Used |
|------------|----------------|
| Language | Python 3.11+ |
| CLI Framework | Click |
| Database | SQLite (persistent storage) |
| Web Framework | Flask |
| Frontend | HTML + Bootstrap + Chart.js |
| Concurrency | Python `threading` |
| Logging | Python `logging` |
| Visualization | Real-time dashboard (`/dashboard`) |

---

## 🎯 Core Features

✅ **Persistent Job Queue** — All jobs are stored in SQLite (`~/.queuectl.db`)  
✅ **Multi-Worker Support** — Run one or more workers concurrently  
✅ **Retry with Exponential Backoff** — Automatic job retry mechanism  
✅ **Dead Letter Queue (DLQ)** — Handles permanently failed jobs  
✅ **Graceful Shutdown** — Stops safely without job loss  
✅ **Dynamic Configuration** — Manage `max_retries`, `base_backoff`, etc.  
✅ **Job Scheduling (`run_at`)** — Delay jobs to execute later  
✅ **Per-Job Logging** — Each job stores detailed logs in `~/.queuectl/logs`  
✅ **Timeout Handling** — Jobs auto-terminate after configured timeout  
✅ **Metrics & Dashboard** — Monitor queue state in real-time  

---

## 🧱 System Architecture

```text
                ┌───────────────────────────────┐
                │          CLI (Click)          │
                │ queuectl enqueue / worker ... │
                └──────────────┬────────────────┘
                               │
                               ▼
┌───────────────────────────────┐
│         Storage (SQLite)      │
│  jobs, config, dlq, heartbeat │
└───────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────┐
│        Worker Threads         │
│  Fetch pending → execute cmd  │
│  retry(backoff) / DLQ if fail │
└───────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────┐
│     Dead Letter Queue (DLQ)   │
│  Failed jobs for manual retry │
└───────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────┐
│     Web Dashboard (Flask)     │
│   Live metrics + DLQ retry UI │
└───────────────────────────────┘
```

---

## ⚙️ Installation

```bash
# Clone the repository
git clone https://github.com/adityasah104/queuectl.git
cd queuectl

# (Optional) Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

---

## 📦 Usage Guide

### 🧮 1. Enqueue Jobs

```bash
# Simple command
python -m queuectl.cli enqueue --command "echo Hello QueueCTL"

# From JSON string
python -m queuectl.cli enqueue '{"command": "echo JSON Job"}'

# From JSON file
python -m queuectl.cli enqueue -f job.json

# Schedule job to run later
python -m queuectl.cli enqueue --command "echo Delayed" --run-at "2025-11-07T10:00:00Z"
```

---

### ⚙️ 2. Start Worker(s)

```bash
# Start 1 worker
python -m queuectl.cli worker start

# Start multiple workers
python -m queuectl.cli worker start --count 3
```

✅ Each worker processes jobs, retries failed ones, and reports status live.

---

### 🧾 3. View Status

```bash
python -m queuectl.cli status
```

**Example Output:**

```
Workers active: 2
Job counts by state:
  pending   : 1
  processing: 0
  completed : 3
  failed    : 0
  dead      : 1
DLQ size: 1
```

---

### 📋 4. List Jobs

```bash
python -m queuectl.cli list --state pending
```

---

### 💀 5. Manage Dead Letter Queue (DLQ)

```bash
# List dead jobs
python -m queuectl.cli dlq list

# Retry a dead job
python -m queuectl.cli dlq retry <job_id>
```

---

### 🔧 6. Configuration

```bash
# View current settings
python -m queuectl.cli config show

# Update retry or backoff
python -m queuectl.cli config set max_retries 5
python -m queuectl.cli config set base_backoff 3
```

---

### 📜 7. View Job Logs

```bash
python -m queuectl.cli logs show <job_id>
```

Logs stored in:

```
~/.queuectl/logs/<job_id>.log
```

---

### 🌐 8. Launch Monitoring Dashboard

```bash
python -m queuectl.api
```

Then open:

👉 **[http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)**

**Dashboard Features:**

* Real-time refresh every 5 seconds
* Donut chart of job states
* DLQ table with retry button
* Auto-colored worker/job cards
* Timestamp of last update

---

## 🧮 Metrics Endpoint

`/metrics` — returns average execution time by state:

```json
{
  "completed": { "jobs": 4, "avg_time_sec": 0.23 },
  "failed": { "jobs": 1, "avg_time_sec": null }
}
```

---

## 🧰 Configuration File (SQLite Config Table)

| Key               | Default | Description                             |
| ----------------- | ------- | --------------------------------------- |
| `max_retries`     | 3       | Maximum retry attempts before DLQ       |
| `base_backoff`    | 2       | Base multiplier for exponential backoff |
| `job_timeout_sec` | 60      | Job timeout duration                    |

---

## 🧪 Test Scenarios

| Scenario                   | Expected Result                        |
| -------------------------- | -------------------------------------- |
| Valid command (`echo`)     | Completes successfully                 |
| Invalid command            | Retries 3 times → moves to DLQ         |
| Multiple workers           | Process jobs concurrently              |
| Scheduled job (`--run-at`) | Executes after given time              |
| Restart app                | Jobs persist in DB                     |
| DLQ retry                  | Job requeued to pending and runs again |
| Dashboard                  | Live update every 5 seconds            |

---

## 🧩 Directory Structure

```
queuectl/
├── core/
│   ├── job.py
│   ├── worker.py
│   ├── storage.py
│   ├── dlq_manager.py
│   ├── config.py
├── utils/
│   └── logger.py
├── cli.py
├── api.py
├── requirements.txt
└── README.md
```

---

## 🌟 Bonus Features Implemented

| Feature                             | Status |
| ----------------------------------- | ------ |
| Job timeout                         | ✅      |
| Scheduled / delayed jobs (`run_at`) | ✅      |
| Job priority placeholder            | ✅      |
| Job output logging                  | ✅      |
| Metrics collection                  | ✅      |
| Web dashboard                       | ✅      |
| DLQ retry from dashboard            | ✅      |
| Configurable parameters             | ✅      |

---

## 🧠 Assumptions & Design Choices

* SQLite chosen for simplicity and persistence.
* Workers are Python threads (lightweight and fast).
* Exponential backoff implemented via `base_backoff^attempts`.
* Job execution done via `subprocess.run()` (captures stdout/stderr).
* Dashboard designed for local monitoring (Flask lightweight server).
* Logs stored per-job in `.queuectl/logs` for easy inspection.

---

## 🧾 Demo Video

🎥 **Watch the full demo here:**
👉 [**QueueCTL Demo (Google Drive)**](https://drive.google.com/your-demo-link-here)

---

## ✅ Checklist

| Requirement                                       | Status |
| ------------------------------------------------- | :----: |
| CLI Commands (enqueue, list, worker, dlq, config) |    ✅   |
| Multi-worker execution                            |    ✅   |
| Retry with exponential backoff                    |    ✅   |
| Dead Letter Queue                                 |    ✅   |
| Persistent job storage                            |    ✅   |
| Job timeout handling                              |    ✅   |
| Scheduled jobs                                    |    ✅   |
| Job logging                                       |    ✅   |
| Metrics tracking                                  |    ✅   |
| Web dashboard                                     |    ✅   |
| Graceful shutdown                                 |    ✅   |
| README + Demo                                     |    ✅   |

---

## 👨‍💻 Author

**Aditya Sah**  
📧 [adityasah712@gmail.com](mailto:adityasah712@gmail.com)  
🌐 [GitHub](https://github.com/adityasah104) | [LinkedIn](https://linkedin.com/in/aditya-sah-574550257)

---

## ⚙️ License

MIT License © 2025 Aditya Sah