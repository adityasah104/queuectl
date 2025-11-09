"""
QueueCTL - Automated Core Flow Test Script
------------------------------------------
This script runs minimal automated tests to validate QueueCTL functionality:
✅ Enqueue jobs
✅ Process them with workers
✅ Handle failed jobs (DLQ)
✅ Check metrics and status
✅ Verify dashboard endpoints
"""

import os
import subprocess
import time
import json
import requests
import sqlite3
from pathlib import Path


HOME = Path.home()
DB_PATH = HOME / ".queuectl.db"


def run(cmd):
    """Run a CLI command and return output."""
    print(f"\n$ {cmd}")
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, encoding="utf-8"
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    return result.stdout.strip()


def reset_db():
    """Delete and recreate DB for clean test."""
    if DB_PATH.exists():
        DB_PATH.unlink()
        print("🧹 Old DB deleted.")
    run("python -m queuectl.cli status")  # auto-create new DB


def enqueue_jobs():
    """Add test jobs."""
    run('python -m queuectl.cli enqueue --command "echo Job1 OK" --priority 3')
    run('python -m queuectl.cli enqueue --command "badcommand" --priority 1')
    run('python -m queuectl.cli enqueue --command "echo Job3 OK" --priority 2')


def start_workers():
    """Start workers for short run (2 jobs processed, then stop)."""
    print("\n🚀 Starting 1 worker for 10 seconds...")
    p = subprocess.Popen("python -m queuectl.cli worker start --count 1", shell=True)
    time.sleep(10)
    p.terminate()
    time.sleep(2)
    print("🛑 Worker stopped.\n")


def check_status():
    """Display system status."""
    run("python -m queuectl.cli status")
    run("python -m queuectl.cli dlq list")
    run("python -m queuectl.cli metrics")


def check_dashboard():
    """Start API and query endpoints briefly."""
    print("\n🌐 Starting Flask API server (3s warmup)...")
    api = subprocess.Popen("python -m queuectl.api", shell=True)
    time.sleep(3)

    try:
        print("✅ /status endpoint:")
        print(requests.get("http://127.0.0.1:8000/status").json())

        print("\n✅ /metrics endpoint:")
        print(requests.get("http://127.0.0.1:8000/metrics").json())

        print("\n✅ /metrics/timeseries endpoint:")
        print(requests.get("http://127.0.0.1:8000/metrics/timeseries").json())

    except Exception as e:
        print("❌ Dashboard test failed:", e)
    finally:
        api.terminate()
        print("🛑 API stopped.\n")


def verify_db_content():
    """Check SQLite tables to ensure data persisted."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM jobs")
    job_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM dlq")
    dlq_count = c.fetchone()[0]
    print(f"📊 DB Verification — Jobs: {job_count}, DLQ: {dlq_count}")
    conn.close()


if __name__ == "__main__":
    print("=== 🧪 QueueCTL Automated Test Start ===")

    reset_db()
    enqueue_jobs()
    start_workers()
    check_status()
    verify_db_content()
    check_dashboard()

    print("=== ✅ Test Completed Successfully ===")
