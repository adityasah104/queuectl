import threading
import subprocess
import time
import os
import socket
from datetime import datetime
from queuectl.core.storage import Storage
from queuectl.core.config import Config
from queuectl.core.dlq_manager import DLQManager
from queuectl.utils.logger import get_logger

logger = get_logger()

# Directory for job logs
LOG_DIR = os.path.join(os.path.expanduser("~"), ".queuectl", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

class Worker(threading.Thread):
    """
    Worker thread that continuously polls for pending jobs,
    executes them, retries on failure (with exponential backoff),
    moves dead jobs to DLQ, and logs output.
    """

    def __init__(self, worker_id: int, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.worker_id = str(worker_id)
        self.stop_event = stop_event
        self.storage = Storage()
        self.config = Config()
        self.dlq = DLQManager()
        self.hostname = socket.gethostname()
        self.pid = os.getpid()

    # --------------------------------------------------------------
    def run(self):
        """Main loop: update heartbeat and process jobs."""
        logger.info(f"Worker-{self.worker_id} started.")
        heartbeat_interval = 2
        next_hb = time.time()

        while not self.stop_event.is_set():
            now = time.time()
            if now >= next_hb:
                self.storage.upsert_heartbeat(self.worker_id, self.pid, self.hostname)
                next_hb = now + heartbeat_interval

            job = self._fetch_pending_job()
            if not job:
                time.sleep(0.5)
                continue

            self._process_job(job)

        self.storage.remove_heartbeat(self.worker_id)
        logger.info(f"Worker-{self.worker_id} stopped gracefully.")

    # --------------------------------------------------------------
    def _fetch_pending_job(self):
        """Fetch one pending job (whose run_at is due) and mark as processing."""
        c = self.storage.conn.cursor()
        now = datetime.utcnow().isoformat()
        c.execute("""
            SELECT * FROM jobs
            WHERE state='pending' AND (run_at IS NULL OR run_at <= ?)
            ORDER BY COALESCE(run_at, created_at), created_at
            LIMIT 1
        """, (now,))
        row = c.fetchone()
        if not row:
            return None

        job_id = row["id"]
        c.execute(
            "UPDATE jobs SET state='processing', updated_at=? WHERE id=? AND state='pending'",
            (datetime.utcnow().isoformat(), job_id)
        )
        self.storage.conn.commit()

        if c.rowcount == 0:
            return None  # another worker took it

        logger.info(f"Worker-{self.worker_id} picked job {job_id}")
        return dict(row)

    # --------------------------------------------------------------
    def _log_path(self, job_id: str):
        return os.path.join(LOG_DIR, f"{job_id}.log")

    # --------------------------------------------------------------
    def _process_job(self, job):
        job_id = job["id"]
        cmd = job["command"]
        attempts = job["attempts"] + 1
        max_retries = int(job["max_retries"])
        base_backoff = int(self.config.get("base_backoff", 2))
        timeout_sec = int(self.config.get("job_timeout_sec", 60))

        log_file = self._log_path(job_id)
        start_ts = datetime.utcnow().isoformat()

        try:
            logger.info(f"Worker-{self.worker_id} executing: {cmd}")
            proc = subprocess.run(
                cmd,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_sec
            )

            out = proc.stdout.decode(errors="replace").strip()
            err = proc.stderr.decode(errors="replace").strip()

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"=== Job {job_id} START {start_ts} ===\n")
                f.write(f"Command: {cmd}\n")
                f.write(f"STDOUT:\n{out}\n")
                if err:
                    f.write(f"STDERR:\n{err}\n")
                f.write(f"Exit: 0\n")
                f.write(f"=== Job {job_id} END {datetime.utcnow().isoformat()} ===\n\n")

            self.storage.update_job_state(job_id, "completed", attempts)
            logger.info(f"Worker-{self.worker_id} completed {job_id}")

        except subprocess.TimeoutExpired:
            msg = f"timeout after {timeout_sec}s"
            self._handle_failure(job, attempts, base_backoff, max_retries, reason=msg)

        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode(errors="replace").strip() if e.stderr else f"Exit code {e.returncode}"
            self._handle_failure(job, attempts, base_backoff, max_retries, reason=err_msg)

        except Exception as e:
            logger.error(f"Worker-{self.worker_id} unexpected error: {e}")
            self._handle_failure(job, attempts, base_backoff, max_retries, reason=str(e))

    # --------------------------------------------------------------
    def _handle_failure(self, job, attempts, base_backoff, max_retries, reason: str):
        job_id = job["id"]

        if attempts < max_retries:
            delay = base_backoff ** attempts
            logger.warning(f"Worker-{self.worker_id} failed job {job_id} ({reason}), retrying in {delay}s")
            time.sleep(delay)
            self.storage.update_job_state(job_id, "pending", attempts)
        else:
            logger.error(f"Worker-{self.worker_id} job {job_id} exhausted retries → DLQ ({reason})")
            job["attempts"] = attempts
            job["max_retries"] = max_retries
            self.storage.update_job_state(job_id, "dead", attempts)
            self.dlq.add_to_dlq(job)
