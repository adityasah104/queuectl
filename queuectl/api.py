from flask import Flask, jsonify, request, render_template_string
from queuectl.core.storage import Storage
from queuectl.core.dlq_manager import DLQManager
from queuectl.utils.logger import get_logger

app = Flask(__name__)
logger = get_logger()

# ---------------------------------------------------------------------
# Utility: Safe DB access wrapper
# ---------------------------------------------------------------------
def with_storage(func):
    def wrapper(*args, **kwargs):
        s = Storage()
        try:
            return func(s, *args, **kwargs)
        except Exception as e:
            logger.error(f"API error: {e}")
            return jsonify({"error": str(e)}), 500
    wrapper.__name__ = func.__name__
    return wrapper


# ---------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------
@app.route("/")
def index():
    return jsonify({
        "service": "QueueCTL Monitoring API",
        "version": "1.0",
        "routes": ["/status", "/jobs", "/metrics", "/dlq", "/dlq/retry/<job_id>"]
    })


@app.route("/status")
@with_storage
def get_status(s: Storage):
    """Return workers, job counts, DLQ count."""
    return jsonify({
        "workers_active": s.active_workers(),
        "job_counts": s.count_by_state(),
        "dlq_size": s.dlq_count()
    })


@app.route("/jobs")
@with_storage
def list_jobs(s: Storage):
    """List all jobs or filter by state via ?state=pending"""
    state = request.args.get("state")
    if state:
        jobs = s.get_jobs_by_state(state)
    else:
        jobs = s.get_all_jobs()
    return jsonify({"count": len(jobs), "jobs": jobs})


@app.route("/dlq")
def list_dlq():
    """Return all dead-lettered jobs."""
    dlq = DLQManager()
    jobs = dlq.list_dlq()
    clean_jobs = [
        {"id": j.get("id"), "command": j.get("command"), "attempts": j.get("attempts", 0)}
        for j in jobs
    ]
    return jsonify(clean_jobs)


@app.route("/dlq/retry/<job_id>", methods=["POST"])
def retry_dlq_job(job_id):
    """Retry a DLQ job by ID via API."""
    try:
        dlq = DLQManager()
        job = dlq.retry_job(job_id)
        if job:
            logger.info(f"Requeued DLQ job {job_id} from API")
            return jsonify({"status": "requeued", "job_id": job.id})
        return jsonify({"error": f"Job {job_id} not found in DLQ"}), 404
    except Exception as e:
        logger.error(f"Failed to retry DLQ job {job_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/metrics")
@with_storage
def metrics_summary(s: Storage):
    """Aggregate average duration per job status."""
    c = s.conn.cursor()
    try:
        c.execute("""
            SELECT status, COUNT(*) AS jobs, AVG(duration) AS avg_time
            FROM metrics GROUP BY status
        """)
        rows = c.fetchall()
        result = {
            r["status"]: {
                "jobs": r["jobs"],
                "avg_time_sec": round(r["avg_time"], 2) if r["avg_time"] else None
            } for r in rows
        }
    except Exception as e:
        result = {"error": str(e)}
    return jsonify(result)


# ---------------------------------------------------------------------
# DASHBOARD (HTML view)
# ---------------------------------------------------------------------
@app.route("/dashboard")
def dashboard():
    """Enhanced real-time dashboard with DLQ table, retry buttons, and colors."""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>QueueCTL Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background:#f9fafb; padding:2rem; font-family:Inter, sans-serif; }
            .card { box-shadow:0 2px 8px rgba(0,0,0,0.05); border:none; transition:0.3s; }
            .green { background-color:#d1fae5; }
            .yellow { background-color:#fef9c3; }
            .red { background-color:#fee2e2; }
            h1 { font-weight:600; }
            table { background:white; border-radius:0.5rem; overflow:hidden; }
            .footer { text-align:right; font-size:0.9rem; color:#6b7280; margin-top:1rem; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="mb-4">QueueCTL Monitoring Dashboard</h1>
            <div class="row mb-4">
                <div class="col-md-3"><div id="card-workers" class="card p-3"><h5>Active Workers</h5><h2 id="workers">0</h2></div></div>
                <div class="col-md-3"><div id="card-pending" class="card p-3"><h5>Pending Jobs</h5><h2 id="pending">0</h2></div></div>
                <div class="col-md-3"><div id="card-completed" class="card p-3"><h5>Completed Jobs</h5><h2 id="completed">0</h2></div></div>
                <div class="col-md-3"><div id="card-dlq" class="card p-3"><h5>DLQ Size</h5><h2 id="dlq">0</h2></div></div>
            </div>

            <canvas id="jobChart" height="100" class="mb-4"></canvas>

            <h4 class="mt-5">Dead Letter Queue (DLQ)</h4>
            <table class="table table-striped">
                <thead><tr><th>ID</th><th>Command</th><th>Attempts</th><th>Actions</th></tr></thead>
                <tbody id="dlq-table"><tr><td colspan="4">Loading...</td></tr></tbody>
            </table>

            <div class="footer">
                Last updated: <span id="last-updated">–</span>
            </div>
        </div>

        <script>
        async function fetchData() {
            try {
                const [statusRes, dlqRes] = await Promise.all([
                    fetch('/status'),
                    fetch('/dlq')
                ]);

                const statusData = await statusRes.json();
                const dlqData = await dlqRes.json();

                // Update counters
                document.getElementById('workers').innerText = statusData.workers_active;
                document.getElementById('pending').innerText = statusData.job_counts.pending || 0;
                document.getElementById('completed').innerText = statusData.job_counts.completed || 0;
                document.getElementById('dlq').innerText = statusData.dlq_size;

                // Update DLQ table
                const dlqTable = document.getElementById('dlq-table');
                dlqTable.innerHTML = '';
                if (!dlqData || dlqData.length === 0) {
                    dlqTable.innerHTML = '<tr><td colspan="4" class="text-center">DLQ empty.</td></tr>';
                } else {
                    dlqData.forEach(job => {
                        const row = `
                            <tr>
                                <td>${job.id}</td>
                                <td>${job.command}</td>
                                <td>${job.attempts}</td>
                                <td><button class="btn btn-sm btn-outline-primary" onclick="retryJob('${job.id}')">Retry</button></td>
                            </tr>`;
                        dlqTable.innerHTML += row;
                    });
                }

                // Color coding
                colorCard('card-pending', statusData.job_counts.pending > 0 ? 'yellow' : '');
                colorCard('card-completed', statusData.job_counts.completed > 0 ? 'green' : '');
                colorCard('card-dlq', statusData.dlq_size > 0 ? 'red' : '');
                colorCard('card-workers', statusData.workers_active > 0 ? 'green' : '');

                // Chart
                const ctx = document.getElementById('jobChart');
                if (window.jobChart) window.jobChart.destroy();
                window.jobChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: Object.keys(statusData.job_counts),
                        datasets: [{
                            data: Object.values(statusData.job_counts),
                            borderWidth: 1
                        }]
                    },
                    options: { plugins: { legend: { position: 'bottom' } } }
                });

                document.getElementById('last-updated').innerText = new Date().toLocaleTimeString();
            } catch (err) {
                console.error("Error fetching data:", err);
            }
        }

        async function retryJob(jobId) {
            if (!confirm(`Requeue job ${jobId}?`)) return;
            const res = await fetch(`/dlq/retry/${jobId}`, { method: "POST" });
            const data = await res.json();
            if (data.status === "requeued") {
                alert(`Job ${jobId} requeued successfully.`);
                fetchData();
            } else {
                alert("Retry failed: " + (data.error || "Unknown error"));
            }
        }

        function colorCard(id, colorClass) {
            const el = document.getElementById(id);
            el.classList.remove('green', 'yellow', 'red');
            if (colorClass) el.classList.add(colorClass);
        }

        fetchData();
        setInterval(fetchData, 5000);
        </script>
    </body>
    </html>
    """
    return render_template_string(html)


# ---------------------------------------------------------------------
# MAIN ENTRYPOINT
# ---------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting QueueCTL Monitoring API on http://127.0.0.1:8000")
    app.run(host="0.0.0.0", port=8000)
