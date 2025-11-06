import json
import threading
import time
import click
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
def enqueue(job_json, command, file_path):
    """Enqueue a new job.

    Examples:
        queuectl enqueue --command "echo Hello"
        queuectl enqueue -f job.json
        queuectl enqueue '{"command": "echo Hello"}'
    """
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

        # --- 2️⃣ Create and store job ---
        job = Job.from_dict(job_data)
        storage.add_job(job)
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
# MAIN
# -----------------------------------------------------------
if __name__ == "__main__":
    cli()
