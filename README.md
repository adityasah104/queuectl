# 🧠 QueueCTL — CLI-Based Background Job Queue System

### 🚀 A production-grade, CLI-driven background job orchestration system built in **Python**

featuring **multi-worker concurrency**, **SQLite persistence**, **automatic retries with exponential backoff**, **Dead Letter Queue (DLQ)** handling, and a **real-time web dashboard** with metrics visualization.

---

## 🧩 Overview

`QueueCTL` is a command-line background job processing system that provides reliable asynchronous task execution.
It enables you to enqueue shell commands or scheduled jobs, execute them concurrently via workers, automatically handle retries, and monitor system health using a real-time dashboard.

---

## 🛠️ Tech Stack

| Component     | Technology Used                       |
| ------------- | ------------------------------------- |
| Language      | Python 3.11+                          |
| CLI Framework | Click                                 |
| Database      | SQLite (persistent storage)           |
| Web Framework | Flask                                 |
| Frontend      | Bootstrap 5 + Chart.js + Font Awesome |
| Concurrency   | Python `threading`                    |
| Logging       | Python `logging`                      |
| Visualization | Live metrics dashboard (`/dashboard`) |

---

## 🎯 Core Features

✅ **Persistent Job Queue** — Durable storage in SQLite for all jobs  
✅ **Multi-Worker Execution** — Run multiple workers concurrently  
✅ **Retries with Exponential Backoff** — Automatically retry failed jobs  
✅ **Graceful Shutdown** — Workers exit safely on stop signal  
✅ **Dead Letter Queue (DLQ)** — Handles permanently failed jobs  
✅ **Job Scheduling (`run_at`)** — Schedule jobs for future execution  
✅ **Priority Queueing** — Lower priority value → earlier execution  
✅ **Per-Job Logging** — Each job logs to its own file  
✅ **Timeout Protection** — Prevent long-running or hanging jobs  
✅ **Configurable Parameters** — Update retry & backoff dynamically  
✅ **Metrics Collection** — Job counts and average durations tracked  
✅ **Interactive Dashboard** — Modern web interface with glassmorphism design  
✅ **DLQ Retry via Web** — Retry failed jobs directly from the dashboard  
✅ **Real-time Updates** — Live monitoring with 5-second refresh intervals

---

## 🧱 System Architecture

```
┌──────────────────────────────────────┐
│               CLI (Click)            │
│ queuectl enqueue / worker / config   │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│           Storage (SQLite)           │
│ jobs, metrics, dlq, config, control  │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│         Worker Threads Pool          │
│ executes commands, retries, logging  │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│       Dead Letter Queue (DLQ)        │
│   holds permanently failed jobs      │
└──────────────────┬───────────────────┘
                   ▼
┌──────────────────────────────────────┐
│     Web Monitoring Dashboard (Flask) │
│ charts, metrics, DLQ retry buttons   │
└──────────────────────────────────────┘
```

---

## ⚙️ Installation

```bash
# Clone the repository
git clone https://github.com/adityasah104/queuectl.git
cd queuectl

# (Optional) Create a virtual environment
python -m venv venv
venv\Scripts\activate   # Windows
# or
source venv/bin/activate   # macOS/Linux

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

# Schedule a future job
python -m queuectl.cli enqueue --command "echo Scheduled Job" --run-at "2025-11-07T10:00:00Z"
```

---

### ⚙️ 2. Start Worker(s)

```bash
# Start one worker
python -m queuectl.cli worker start

# Start multiple workers
python -m queuectl.cli worker start --count 3
```

✅ Each worker fetches pending jobs, executes them, and retries failed ones using exponential backoff.

---

### 🚦 3. Stop Workers Gracefully

```bash
python -m queuectl.cli worker stop
```

Safely signals all workers to finish their current jobs before stopping.

---

### 🧾 4. Monitor Queue Status

```bash
python -m queuectl.cli status
```

**Example Output:**

```
Workers active: 2
Job counts by state:
  pending   : 2
  processing: 0
  completed : 5
  failed    : 0
  dead      : 1
DLQ size: 1
```

---

### 📋 5. List Jobs

```bash
python -m queuectl.cli list --state pending
```

---

### 💀 6. Manage Dead Letter Queue (DLQ)

```bash
# View DLQ
python -m queuectl.cli dlq list

# Retry a job
python -m queuectl.cli dlq retry <job_id>
```

---

### 🔧 7. Manage Configuration

```bash
# View config
python -m queuectl.cli config show

# Update parameters
python -m queuectl.cli config set max_retries 5
python -m queuectl.cli config set base_backoff 3
```

---

### 📜 8. View Job Logs

```bash
python -m queuectl.cli logs show <job_id>
```

All logs are stored at:

```
~/.queuectl/logs/<job_id>.log
```

---

### 🌐 9. Launch Web Dashboard

```bash
python -m queuectl.api
```

Then open:

👉 **[http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)**

---

## 🎨 Dashboard Features

The QueueCTL dashboard features a **modern, premium design** with glassmorphism effects and smooth animations:

| Feature                      | Description                                        |
| ---------------------------- | -------------------------------------------------- |
| 💹 **Live Refresh**          | Auto-refreshes every 5 seconds                     |
| 🎨 **Modern UI**             | Gradient backgrounds, glassmorphism cards          |
| 🧩 **State Overview**        | Color-coded cards showing system metrics           |
| 📊 **Visual Icons**          | Font Awesome icons for better visual communication |
| 🍩 **Donut Chart**           | Interactive job state distribution                 |
| 📈 **Time-Series Chart**     | Smooth line charts for completed vs failed jobs    |
| ⚰️ **DLQ Management**        | View and retry failed jobs with one click          |
| 🖱️ **Interactive Elements** | Hover effects and smooth transitions               |
| 📱 **Responsive Design**     | Optimized for desktop, tablet, and mobile          |
| 🕒 **Live Timestamp**        | Shows last update time                             |
| 🎯 **Status Indicators**     | Pulsing live monitoring badge                      |
| ✨ **Smooth Animations**     | Card hover effects and chart transitions           |

### Dashboard Screenshots

The dashboard includes:
- **Header Section**: Live monitoring status with animated pulse indicator
- **Metrics Cards**: Four color-coded cards showing:
  - Active Workers (Blue)
  - Pending Jobs (Yellow)
  - Completed Jobs (Green)
  - DLQ Size (Red)
- **Job Distribution Chart**: Interactive donut chart with hover effects
- **Trends Chart**: Line chart showing job completion trends over the last 60 minutes
- **DLQ Table**: Clean, modern table with retry buttons for failed jobs

---

## 🧮 Metrics API

### `/metrics`

Average job durations by state:

```json
{
  "completed": { "jobs": 5, "avg_time_sec": 0.27 },
  "failed": { "jobs": 2, "avg_time_sec": null }
}
```

### `/metrics/timeseries`

Job counts per minute for the last 60 minutes:

```json
{
  "labels": ["2025-11-07T05:21","2025-11-07T05:45"],
  "completed": [1,3],
  "failed": [0,1]
}
```

---

## ⚙️ Configurable Parameters

| Key               | Default | Description                                 |
| ----------------- | ------- | ------------------------------------------- |
| `max_retries`     | `3`     | Maximum retry attempts before moving to DLQ |
| `base_backoff`    | `2`     | Exponential backoff base                    |
| `job_timeout_sec` | `60`    | Timeout per job (in seconds)                |

---

## 🧪 Test Scenarios

| Scenario            | Expected Result            |
| ------------------- | -------------------------- |
| ✅ Valid command     | Completes successfully     |
| ❌ Invalid command   | Retries → Moves to DLQ     |
| ⚙️ Multiple workers | Process jobs concurrently  |
| 🕒 Scheduled jobs   | Executed at specified time |
| 💾 Restart app      | Jobs persist in database   |
| ♻️ DLQ retry        | Job moves back to pending  |
| 📊 Dashboard        | Displays real-time metrics |

---

## 📂 Directory Structure

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

## 🌟 Additional Highlights

✅ Real-time donut + line chart visualization with smooth animations  
✅ Graceful worker shutdown command (`queuectl worker stop`)  
✅ Modern Bootstrap 5 UI with glassmorphism design  
✅ Historical job metrics via `/metrics/timeseries`  
✅ Job priority and scheduling support  
✅ Persistent configuration management  
✅ Per-job logging and retry tracking  
✅ Font Awesome icons for enhanced visual experience  
✅ Color-coded status indicators for quick insights  
✅ Responsive layout optimized for all screen sizes

---

## 🧠 Design Choices

* **SQLite** chosen for simplicity, durability, and easy restart recovery
* **Threaded workers** for efficient parallel execution
* **Exponential backoff** based on `base_backoff^attempts`
* **Job execution** handled via `subprocess.run()` for isolation
* **Flask-based dashboard** for local observability
* **Chart.js** for smooth, lightweight visualization
* **Modern UI/UX** with gradient backgrounds and glassmorphism effects
* **Font Awesome** for consistent iconography
* **Bootstrap 5** for responsive, mobile-first design

---

## 👨‍💻 Author

**Aditya Sah**  
📧 [adityasah712@gmail.com](mailto:adityasah712@gmail.com)  
🌐 [GitHub](https://github.com/adityasah104) • [LinkedIn](https://linkedin.com/in/aditya-sah-574550257)

---

## ⚙️ License

© 2025 Aditya Sah. All rights reserved.

---

## 🎬 Demo

Experience QueueCTL's modern dashboard in action:
1. Start the API server: `python -m queuectl.api`
2. Navigate to: `http://127.0.0.1:8000/dashboard`
3. Watch real-time metrics update every 5 seconds
4. Interact with the retry buttons to requeue failed jobs
5. Explore the smooth animations and responsive design

---

**Built with ❤️ using Python, Flask, and modern web technologies**