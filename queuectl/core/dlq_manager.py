import sqlite3
import os
from datetime import datetime
from queuectl.core.job import Job
from queuectl.utils.logger import get_logger

logger = get_logger()

DB_FILE = os.path.join(os.path.expanduser("~"), ".queuectl.db")


class DLQManager:
    """Manages Dead Letter Queue (DLQ) operations safely."""

    def __init__(self):
        # Ensure DB directory exists
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_table()

    # ----------------------------------------------------------------------
    def _create_table(self):
        """Create DLQ table if not exists."""
        c = self.conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS dlq (
                id TEXT PRIMARY KEY,
                command TEXT,
                attempts INTEGER,
                max_retries INTEGER,
                failed_at TEXT
            )
        ''')
        self.conn.commit()

    # ----------------------------------------------------------------------
    def add_to_dlq(self, job_dict: dict):
        """Add a failed job to the DLQ table."""
        c = self.conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO dlq (id, command, attempts, max_retries, failed_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            job_dict["id"],
            job_dict["command"],
            job_dict.get("attempts", 0),
            job_dict.get("max_retries", 3),
            datetime.utcnow().isoformat()
        ))
        self.conn.commit()
        logger.warning(f"Job {job_dict['id']} moved to DLQ.")

    # ----------------------------------------------------------------------
    def list_dlq(self):
        """Return all DLQ jobs as list of plain dicts (JSON-safe)."""
        c = self.conn.cursor()
        c.execute("SELECT * FROM dlq ORDER BY failed_at DESC")
        rows = c.fetchall()

        # ✅ Convert sqlite3.Row → dict for API/CLI
        dlq_jobs = [dict(r) for r in rows]
        return dlq_jobs

    # ----------------------------------------------------------------------
    def retry_job(self, job_id: str):
        """Move a DLQ job back to the jobs queue."""
        c = self.conn.cursor()
        c.execute("SELECT * FROM dlq WHERE id=?", (job_id,))
        row = c.fetchone()

        if not row:
            return None

        job_data = dict(row)
        job = Job.from_dict({
            "command": job_data["command"],
            "max_retries": job_data["max_retries"]
        })

        # keep same id
        job.id = job_data["id"]
        job.attempts = 0
        job.state = "pending"

        # Reinsert into jobs table
        c.execute('''
            INSERT OR REPLACE INTO jobs (id, command, state, attempts, max_retries, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            job.id,
            job.command,
            job.state,
            job.attempts,
            job.max_retries,
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat()
        ))

        # Remove from DLQ
        c.execute("DELETE FROM dlq WHERE id=?", (job_id,))
        self.conn.commit()

        logger.info(f"Job {job.id} retried and moved back to pending queue.")
        return job
