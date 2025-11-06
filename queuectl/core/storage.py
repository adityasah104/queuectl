import sqlite3
import json
import os
from datetime import datetime
from queuectl.core.job import Job

DB_FILE = os.path.join(os.path.expanduser("~"), ".queuectl.db")

class Storage:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        self.conn.commit()

    # ---------- Job Operations ----------

    def add_job(self, job: Job):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO jobs (id, command, state, attempts, max_retries, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (job.id, job.command, job.state, job.attempts,
            job.max_retries, job.created_at, job.updated_at))
        self.conn.commit()


    def get_jobs_by_state(self, state: str):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM jobs WHERE state = ?', (state,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_all_jobs(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM jobs')
        return [dict(row) for row in cursor.fetchall()]

    def get_job(self, job_id: str):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM jobs WHERE id = ?', (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_job_state(self, job_id: str, new_state: str, attempts: int = None):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE jobs
            SET state = ?, attempts = ?, updated_at = ?
            WHERE id = ?
        ''', (new_state, attempts, datetime.utcnow().isoformat(), job_id))
        self.conn.commit()
