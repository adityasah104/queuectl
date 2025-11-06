import threading, subprocess, time
from datetime import datetime
from queuectl.core.storage import Storage
from queuectl.core.config import Config
from queuectl.core.dlq_manager import DLQManager
from queuectl.utils.logger import get_logger

logger = get_logger()

class Worker(threading.Thread):
    def __init__(self, worker_id: int, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.worker_id = worker_id
        self.stop_event = stop_event
        self.storage = Storage()
        self.config = Config()
        self.dlq = DLQManager()

    def run(self):
        logger.info(f"Worker-{self.worker_id} started.")
        while not self.stop_event.is_set():
            job = self._fetch_pending_job()
            if not job:
                time.sleep(1)
                continue
            self._process_job(job)
        logger.info(f"Worker-{self.worker_id} stopped gracefully.")

    # ------------------------------------------------------------------
    def _fetch_pending_job(self):
        """Atomically claim one pending job."""
        c = self.storage.conn.cursor()
        c.execute("""
            SELECT * FROM jobs WHERE state='pending' ORDER BY created_at LIMIT 1
        """)
        row = c.fetchone()
        if not row:
            return None

        job_id = row["id"]
        # try to mark as processing only if still pending
        c.execute("""
            UPDATE jobs SET state='processing', updated_at=?
            WHERE id=? AND state='pending'
        """, (datetime.utcnow().isoformat(), job_id))
        self.storage.conn.commit()

        if c.rowcount == 0:  # someone else took it
            return None

        logger.info(f"Worker-{self.worker_id} picked job {job_id}")
        return dict(row)

    # ------------------------------------------------------------------
    def _process_job(self, job):
        job_id = job["id"]
        cmd = job["command"]
        attempts = job["attempts"] + 1
        base_backoff = int(self.config.get("base_backoff", 2))
        max_retries = int(job["max_retries"])

        try:
            logger.info(f"Worker-{self.worker_id} executing: {cmd}")
            subprocess.run(cmd, shell=True, check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.storage.update_job_state(job_id, "completed", attempts)
            logger.info(f"Worker-{self.worker_id} completed {job_id}")

        except subprocess.CalledProcessError as e:
            if attempts < max_retries:
                delay = base_backoff ** attempts
                logger.warning(
                    f"Worker-{self.worker_id} failed job {job_id}, retrying in {delay}s"
                )
                time.sleep(delay)
                # reset state for retry
                self.storage.update_job_state(job_id, "pending", attempts)
            else:
                logger.error(
                    f"Worker-{self.worker_id} job {job_id} exhausted retries → DLQ"
                )
                job["attempts"] = attempts
                job["max_retries"] = max_retries
                self.storage.update_job_state(job_id, "dead", attempts)
                self.dlq.add_to_dlq(job)
