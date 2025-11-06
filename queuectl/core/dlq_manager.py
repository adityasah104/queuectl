from datetime import datetime
from queuectl.core.storage import Storage
from queuectl.core.job import Job

class DLQManager:
    def __init__(self):
        self.storage = Storage()

    def add_to_dlq(self, job):
        cur = self.storage.conn.cursor()
        cur.execute('''
            INSERT OR REPLACE INTO dlq (id, command, attempts, max_retries, failed_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (job["id"], job["command"], job["attempts"],
              job["max_retries"], datetime.utcnow().isoformat()))
        self.storage.conn.commit()

    def list_dlq(self):
        cur = self.storage.conn.cursor()
        cur.execute("SELECT * FROM dlq")
        return [dict(r) for r in cur.fetchall()]

    def retry_job(self, job_id):
        cur = self.storage.conn.cursor()
        cur.execute("SELECT * FROM dlq WHERE id=?", (job_id,))
        row = cur.fetchone()
        if not row:
            return None
        cur.execute("DELETE FROM dlq WHERE id=?", (job_id,))
        self.storage.conn.commit()

        new_job = Job.from_dict({
            "id": row["id"],
            "command": row["command"],
            "attempts": 0,
            "max_retries": row["max_retries"]
        })
        self.storage.add_job(new_job)
        return new_job
