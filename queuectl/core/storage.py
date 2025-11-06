import sqlite3
import os
from datetime import datetime
from queuectl.core.job import Job

DB_FILE = os.path.join(os.path.expanduser("~"), ".queuectl.db")

class Storage:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    # ------------------------------------------------------------------
    def _create_tables(self):
        cursor = self.conn.cursor()

        # main jobs table
        cursor.execute('''
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

        # configuration table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # DLQ table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dlq (
                id TEXT PRIMARY KEY,
                command TEXT,
                attempts INTEGER,
                max_retries INTEGER,
                failed_at TEXT
            )
        ''')

        # defaults
        cursor.execute(
            "INSERT OR IGNORE INTO config (key,value) VALUES ('max_retries','3')"
        )
        cursor.execute(
            "INSERT OR IGNORE INTO config (key,value) VALUES ('base_backoff','2')"
        )

        self.conn.commit()

    # ------------------------------------------------------------------
    # Job Operations
    # ------------------------------------------------------------------
    def add_job(self, job: Job):
        cursor = self.conn.cursor()
        cursor.execute('''
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
