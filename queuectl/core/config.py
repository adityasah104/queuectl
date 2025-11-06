from queuectl.core.storage import Storage

class Config:
    def __init__(self):
        self.storage = Storage()

    def get(self, key, default=None):
        cursor = self.storage.conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key=?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default

    def set(self, key, value):
        cursor = self.storage.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO config (key,value) VALUES (?,?)", (key, str(value))
        )
        self.storage.conn.commit()
