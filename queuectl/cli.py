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

    # ✅ Clear previous shutdown signal
    storage.set_control("shutdown", "0")

    for i in range(count):
        w = Worker(i + 1, _stop_event)
        w.start()
        _workers.append(w)

    logger.info(f"Started {count} workers. Press Ctrl+C or run 'queuectl worker stop' to stop.")

    try:
        while True:
            # 🕵️ Exit automatically if all workers finished
            alive_workers = [w for w in _workers if w.is_alive()]
            if not alive_workers:
                logger.info("✅ All workers have exited. Exiting CLI.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping workers manually (Ctrl+C)...")
        _stop_event.set()
        for w in _workers:
            w.join()
        logger.info("All workers stopped.")


@worker.command("stop")
@click.option("--wait", type=int, default=5, help="Seconds to wait for workers to exit")
def stop_workers(wait):
    """Signal workers to stop via DB flag (graceful, cross-platform)."""
    storage.set_control("shutdown", "1")
    logger.info("Shutdown flag set. Workers will stop gracefully.")
    time.sleep(wait)
    logger.info("Done.")


# -----------------------------------------------------------
# JOB COMMANDS
# -----------------------------------------------------------
@cli.command()
@click.argument("job_json", required=False)
@click.option("--command", "-c", help="Command to execute (alternative to JSON input)")
@click.option("--file", "-f", "file_path", type=click.Path(exists=True),
              help="Path to a JSON file containing job data")
@click.option("--run-at", help="ISO time to run at (e.g. 2025-11-07T10:00:00Z)")
@click.option("--priority", type=int, default=5, help="Job priority (lower runs sooner)")  # ✅ NEW
def enqueue(job_json, command, file_path, run_at, priority):
    """Enqueue a new job."""
    from datetime import datetime

    def _normalize_iso(ts: str) -> str:
        try:
            s = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            return dt.replace(tzinfo=None).isoformat()
        except Exception:
            raise click.BadParameter("Invalid --run-at format")

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

        # --- 3️⃣ Include job priority ---
        job_data["priority"] = priority

        # --- 4️⃣ Create & persist job ---
        job = Job.from_dict(job_data)
        storage.add_job(job)

        msg = f"Job {job.id} added successfully (priority={priority}): {job.command}"
        if run_at:
            msg = f"Job {job.id} scheduled for {job.run_at} (priority={priority}): {job.command}"
        logger.info(msg)
    except Exception as e:
        logger.error(f"Failed to enqueue job: {e}")


# -----------------------------------------------------------
# JOB LISTING
# -----------------------------------------------------------
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
            print(f"[{j['state'].upper()}] {j['id']} - {j['command']} "
                  f"(attempts: {j['attempts']}, priority: {j.get('priority', 5)})")
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
    print(f"job_timeout_sec: {c.get('job_timeout_sec')}")


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
# METRICS COMMAND
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
