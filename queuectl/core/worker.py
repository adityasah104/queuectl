import threading
import subprocess
import time
from queuectl.core.storage import Storage
from queuectl.utils.logger import get_logger

logger = get_logger()

class Worker(threading.Thread):
    """
    Single worker thread that continuously polls for pending jobs,
    executes them, and updates job state.
    """
    def __init__(self, worker_id: int, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.worker_id = worker_id
        self.stop_event = stop_event
        self.storage = Storage()

    def run(self):
        logger.info(f"Worker-{self.worker_id} started.")
        while not self.stop_event.is_set():
            job = self._fetch_pending_job()
            if not job:
                time.sleep(1)  # nothing to do
                continue

            self._process_job(job)
        logger.info(f"Worker-{self.worker_id} stopped gracefully.")

    def _fetch_pending_job(self):
        """Get a single pending job and mark as processing."""
        cursor = self.storage.conn.cursor()
        cursor.execute(
            "SELECT * FROM jobs WHERE state='pending' ORDER BY created_at LIMIT 1"
        )
        row = cursor.fetchone()
        if not row:
            return None

        job_id = row["id"]
        # Mark as processing
        self.storage.update_job_state(job_id, "processing", row["attempts"])
        logger.info(f"Worker-{self.worker_id} picked job {job_id}")
        return dict(row)

    def _process_job(self, job):
        job_id = job["id"]
        cmd = job["command"]
        try:
            logger.info(f"Worker-{self.worker_id} executing: {cmd}")
            result = subprocess.run(
                cmd, shell=True, check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            logger.info(f"Worker-{self.worker_id} completed {job_id}: {result.stdout.decode().strip()}")
            self.storage.update_job_state(job_id, "completed", job["attempts"])
        except subprocess.CalledProcessError as e:
            logger.error(f"Worker-{self.worker_id} failed {job_id}: {e.stderr.decode().strip()}")
            self.storage.update_job_state(job_id, "failed", job["attempts"])
