import json
import threading
import time
import click
import os
from queuectl.core.job import Job
from queuectl.core.storage import Storage
from queuectl.core.worker import Worker
from queuectl.utils.logger import get_logger
from queuectl.core.dlq_manager import DLQManager
from queuectl.core.config import Config

# -----------------------------------------------------------
# GLOBALS
# -----------------------------------------------------------
logger = get_logger()
storage = Storage()
_workers = []
_stop_event = threading.Event()

# -----------------------------------------------------------
# CLI ROOT
# -----------------------------------------------------------
@click.group()
def cli():
    """QueueCTL - Background Job Queue System"""
    pass

# -----------------------------------------------------------
# WORKER COMMANDS
# -----------------------------------------------------------
@cli.group()
def worker():
    """Manage worker threads."""
    pass


@worker.command("start")
@click.option("--count", default=1, help="Number of workers to start")
def start_workers(count):
    """Start N worker threads"""
    global _workers, _stop_event
    _stop_event.clear()

    for i in range(count):
        w = Worker(i + 1, _stop_event)
        w.start()
        _workers.append(w)

    logger.info(f"Started {count} workers. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping workers...")
        _stop_event.set()
        for w in _workers:
            w.join()
        logger.info("All workers stopped.")

# -----------------------------------------------------------
# JOB COMMANDS
# -----------------------------------------------------------
@cli.command()
@click.argument("job_json", required=False)
@click.option("--command", "-c", help="Command to execute (alternative to JSON input)")
@click.option("--file", "-f", "file_path", type=click.Path(exists=True),
              help="Path to a JSON file containing job data")
@click.option("--run-at", help="ISO time to run at (e.g. 2025-11-07T10:00:00Z)")
def enqueue(job_json, command, file_path, run_at):
    """Enqueue a new job.

    Examples:
        queuectl enqueue --command "echo Hello"
        queuectl enqueue -f job.json
        queuectl enqueue '{"command": "echo Hello"}'
        queuectl enqueue --command "echo later" --run-at "2025-11-07T10:00:00Z"
    """
    from datetime import datetime

    def _normalize_iso(ts: str) -> str:
        # Accept ...Z or ...+00:00 or naive. Store as naive UTC ISO string for consistency.
        try:
            s = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            return dt.replace(tzinfo=None).isoformat()
        except Exception:
            raise click.BadParameter("Invalid --run-at. Use ISO 8601, e.g. 2025-11-07T10:00:00Z")

    try:
        # --- 1️⃣ Choose input source ---
        if command:
            job_data = {"command": command}
        elif file_path:
            with open(file_path, "r") as f:
                job_data = json.load(f)
        elif job_json:
            job_data = json.loads(job_json)
        else:
            raise click.UsageError("Please provide either --command, --file, or job_json input")

        # --- 2️⃣ Optional schedule time ---
        if run_at:
            job_data["run_at"] = _normalize_iso(run_at)

        # --- 3️⃣ Create and store job ---
        job = Job.from_dict(job_data)
        storage.add_job(job)
        if run_at:
            logger.info(f"Job {job.id} scheduled for {job.run_at}: {job.command}")
        else:
            logger.info(f"Job {job.id} added successfully: {job.command}")
    except Exception as e:
        logger.error(f"Failed to enqueue job: {e}")



@cli.command()
@click.option("--state", default=None,
              help="Filter jobs by state (pending/completed/failed)")
def list(state):
    """List jobs by state"""
    try:
        if state:
            jobs = storage.get_jobs_by_state(state)
        else:
            jobs = storage.get_all_jobs()

        if not jobs:
            print("No jobs found.")
            return

        for j in jobs:
            print(f"[{j['state'].upper()}] {j['id']} - {j['command']} (attempts: {j['attempts']})")
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")



# -----------------------------------------------------------
# DLQ COMMANDS
# -----------------------------------------------------------
@cli.group()
def dlq():
    """Dead Letter Queue management."""
    pass

@dlq.command("list")
def dlq_list():
    dlq = DLQManager()
    jobs = dlq.list_dlq()
    if not jobs:
        print("DLQ empty.")
    else:
        for j in jobs:
            print(f"[DEAD] {j['id']} - {j['command']} (attempts: {j['attempts']})")

@dlq.command("retry")
@click.argument("job_id")
def dlq_retry(job_id):
    dlq = DLQManager()
    job = dlq.retry_job(job_id)
    if job:
        logger.info(f"Job {job.id} requeued successfully.")
    else:
        logger.error(f"Job {job_id} not found in DLQ.")

# -----------------------------------------------------------
# CONFIG COMMANDS
# -----------------------------------------------------------
@cli.group()
def config():
    """System configuration management."""
    pass

@config.command("show")
def config_show():
    c = Config()
    print(f"max_retries: {c.get('max_retries')}")
    print(f"base_backoff: {c.get('base_backoff')}")

@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    c = Config()
    c.set(key, value)
    logger.info(f"Config {key} set to {value}")

# -----------------------------------------------------------
# STATUS COMMAND
# -----------------------------------------------------------
@cli.command()
def status():
    """Show system summary: workers, job counts, DLQ size."""
    s = Storage()
    counts = s.count_by_state()
    workers = s.active_workers()
    dlq_count = s.dlq_count()

    print(f"Workers active: {workers}")
    print("Job counts by state:")
    for k, v in counts.items():
        print(f"  {k:<10}: {v}")
    print(f"DLQ size: {dlq_count}")

# -----------------------------------------------------------
# LOGS COMMANDS
# -----------------------------------------------------------
@cli.group()
def logs():
    """View job output logs."""
    pass

@logs.command("show")
@click.argument("job_id")
def logs_show(job_id):
    """Show log file contents for a given job."""
    log_path = os.path.join(os.path.expanduser("~"), ".queuectl", "logs", f"{job_id}.log")
    if not os.path.exists(log_path):
        print(f"No log found for job {job_id}")
        return
    with open(log_path, "r", encoding="utf-8") as f:
        print(f.read())
# -----------------------------------------------------------
# METRICS COMMAND (Phase 6)
# -----------------------------------------------------------
@cli.command()
def metrics():
    """Display job performance metrics summary."""
    s = Storage()
    data = s.get_metrics_summary()
    if not data:
        print("No metrics recorded yet.")
        return

    print("Job Metrics Summary:")
    for row in data:
        avg = f"{row['avg_time']:.2f}s" if row['avg_time'] else "N/A"
        print(f"{row['status']:<10}: {row['count']} jobs, avg time {avg}")


# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------
if __name__ == "__main__":
    cli()
