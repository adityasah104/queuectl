import sqlite3
import os
from datetime import datetime
from queuectl.core.job import Job

DB_FILE = os.path.join(os.path.expanduser("~"), ".queuectl.db")

class Storage:
    def __init__(self):
        # Ensure DB directory exists
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    # ------------------------------------------------------------------
    def _create_tables(self):
        """Create all necessary tables safely if they don't exist."""
        c = self.conn.cursor()

        # Main job table
        c.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                command TEXT,
                state TEXT,
                attempts INTEGER,
                max_retries INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
        ''')

        # Config table
        c.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Dead Letter Queue
        c.execute('''
            CREATE TABLE IF NOT EXISTS dlq (
                id TEXT PRIMARY KEY,
                command TEXT,
                attempts INTEGER,
                max_retries INTEGER,
                failed_at TEXT
            )
        ''')

        # Worker heartbeat table
        c.execute('''
            CREATE TABLE IF NOT EXISTS worker_heartbeats (
                worker_id TEXT PRIMARY KEY,
                pid INTEGER,
                hostname TEXT,
                started_at TEXT,
                last_seen TEXT
            )
        ''')

        # Default config values
        c.execute("INSERT OR IGNORE INTO config (key,value) VALUES ('max_retries','3')")
        c.execute("INSERT OR IGNORE INTO config (key,value) VALUES ('base_backoff','2')")
        c.execute("INSERT OR IGNORE INTO config (key,value) VALUES ('job_timeout_sec','60')")

        self.conn.commit()

    # ------------------------------------------------------------------
    # Job Operations
    # ------------------------------------------------------------------
    def add_job(self, job: Job):
        c = self.conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO jobs (id, command, state, attempts, max_retries, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (job.id, job.command, job.state, job.attempts,
              job.max_retries, job.created_at, job.updated_at))
        self.conn.commit()

    def get_jobs_by_state(self, state: str):
        c = self.conn.cursor()
        c.execute('SELECT * FROM jobs WHERE state=?', (state,))
        return [dict(r) for r in c.fetchall()]

    def get_all_jobs(self):
        c = self.conn.cursor()
        c.execute('SELECT * FROM jobs')
        return [dict(r) for r in c.fetchall()]

    def get_job(self, job_id: str):
        c = self.conn.cursor()
        c.execute('SELECT * FROM jobs WHERE id=?', (job_id,))
        row = c.fetchone()
        return dict(row) if row else None

    def update_job_state(self, job_id: str, new_state: str, attempts: int = None):
        c = self.conn.cursor()
        c.execute('''
            UPDATE jobs
            SET state=?, attempts=?, updated_at=?
            WHERE id=?
        ''', (new_state, attempts, datetime.utcnow().isoformat(), job_id))
        self.conn.commit()

    # ------------------------------------------------------------------
    # Status & Heartbeat helpers
    # ------------------------------------------------------------------
    def count_by_state(self):
        c = self.conn.cursor()
        c.execute("SELECT state, COUNT(*) AS cnt FROM jobs GROUP BY state")
        rows = c.fetchall()
        summary = {"pending": 0, "processing": 0, "completed": 0, "failed": 0, "dead": 0}
        for r in rows:
            summary[r["state"]] = r["cnt"]
        return summary

    def dlq_count(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) AS cnt FROM dlq")
        return c.fetchone()["cnt"]

    def upsert_heartbeat(self, worker_id: str, pid: int, hostname: str):
        now = datetime.utcnow().isoformat()
        c = self.conn.cursor()
        c.execute('''
            INSERT INTO worker_heartbeats (worker_id, pid, hostname, started_at, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(worker_id) DO UPDATE SET last_seen=excluded.last_seen
        ''', (worker_id, pid, hostname, now, now))
        self.conn.commit()

    def remove_heartbeat(self, worker_id: str):
        c = self.conn.cursor()
        c.execute("DELETE FROM worker_heartbeats WHERE worker_id=?", (worker_id,))
        self.conn.commit()

    def active_workers(self, freshness_sec=5):
        import datetime as _dt
        c = self.conn.cursor()
        # Ensure table exists (safety guard)
        c.execute('''
            CREATE TABLE IF NOT EXISTS worker_heartbeats (
                worker_id TEXT PRIMARY KEY,
                pid INTEGER,
                hostname TEXT,
                started_at TEXT,
                last_seen TEXT
            )
        ''')
        self.conn.commit()
        c.execute("SELECT worker_id,last_seen FROM worker_heartbeats")
        now = _dt.datetime.utcnow()
        active = 0
        for r in c.fetchall():
            last = _dt.datetime.fromisoformat(r["last_seen"])
            if (now - last).total_seconds() <= freshness_sec:
                active += 1
        return active
