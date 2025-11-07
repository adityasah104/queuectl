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
        "routes": [
            "/status",
            "/jobs",
            "/metrics",
            "/metrics/timeseries",
            "/dlq",
            "/dlq/retry/<job_id>",
            "/dashboard"
        ]
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


@app.route("/metrics/timeseries")
@with_storage
def metrics_timeseries(s: Storage):
    """Return per-minute job completions and failures for the last 60 minutes."""
    c = s.conn.cursor()
    c.execute("""
        SELECT substr(finished_at, 1, 16) AS minute, status, COUNT(*) AS cnt
        FROM metrics
        WHERE finished_at >= datetime('now','-60 minutes')
        GROUP BY minute, status
        ORDER BY minute ASC
    """)
    rows = c.fetchall()

    if not rows:
        return jsonify({"labels": [], "completed": [], "failed": []})

    minutes = sorted({r["minute"] for r in rows})
    series = {"completed": {m: 0 for m in minutes}, "failed": {m: 0 for m in minutes}}

    for r in rows:
        status = r["status"]
        if status in series:
            series[status][r["minute"]] = r["cnt"]

    return jsonify({
        "labels": minutes,
        "completed": [series["completed"][m] for m in minutes],
        "failed": [series["failed"][m] for m in minutes],
    })


# ---------------------------------------------------------------------
# DASHBOARD (HTML view)
# ---------------------------------------------------------------------
@app.route("/dashboard")
def dashboard():
    """Enhanced real-time dashboard with modern UI design."""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>QueueCTL Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
            
            * { margin: 0; padding: 0; box-sizing: border-box; }
            
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                min-height: 100vh;
                padding: 2rem 1rem;
            }
            
            .container {
                max-width: 1400px;
                margin: 0 auto;
            }
            
            .header {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 2rem;
                margin-bottom: 2rem;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 1rem;
            }
            
            .header h1 {
                font-weight: 700;
                font-size: 2rem;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                display: flex;
                align-items: center;
                gap: 0.75rem;
                margin: 0;
            }
            
            .status-badge {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.5rem 1rem;
                background: #10b981;
                color: white;
                border-radius: 50px;
                font-size: 0.875rem;
                font-weight: 500;
                animation: pulse 2s ease-in-out infinite;
            }
            
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.8; }
            }
            
            .pulse-dot {
                width: 8px;
                height: 8px;
                background: white;
                border-radius: 50%;
                animation: pulse-dot 1.5s ease-in-out infinite;
            }
            
            @keyframes pulse-dot {
                0%, 100% { transform: scale(1); opacity: 1; }
                50% { transform: scale(1.2); opacity: 0.7; }
            }
            
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 1.5rem;
                margin-bottom: 2rem;
            }
            
            .stat-card {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 16px;
                padding: 1.75rem;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
            }
            
            .stat-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 4px;
                background: linear-gradient(90deg, #667eea, #764ba2);
                transform: scaleX(0);
                transition: transform 0.3s ease;
            }
            
            .stat-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 15px 40px rgba(0, 0, 0, 0.15);
            }
            
            .stat-card:hover::before {
                transform: scaleX(1);
            }
            
            .stat-card.green { border-left: 4px solid #10b981; }
            .stat-card.yellow { border-left: 4px solid #f59e0b; }
            .stat-card.red { border-left: 4px solid #ef4444; }
            .stat-card.blue { border-left: 4px solid #3b82f6; }
            
            .stat-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 1rem;
            }
            
            .stat-icon {
                width: 48px;
                height: 48px;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.5rem;
            }
            
            .stat-icon.green { background: rgba(16, 185, 129, 0.1); color: #10b981; }
            .stat-icon.yellow { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }
            .stat-icon.red { background: rgba(239, 68, 68, 0.1); color: #ef4444; }
            .stat-icon.blue { background: rgba(59, 130, 246, 0.1); color: #3b82f6; }
            
            .stat-label {
                font-size: 0.875rem;
                color: #6b7280;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }
            
            .stat-value {
                font-size: 2.5rem;
                font-weight: 700;
                color: #111827;
                line-height: 1;
            }
            
            .chart-container {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 16px;
                padding: 2rem;
                margin-bottom: 2rem;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            }
            
            .chart-title {
                font-size: 1.25rem;
                font-weight: 600;
                color: #111827;
                margin-bottom: 1.5rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }
            
            .chart-title i {
                color: #667eea;
            }
            
            canvas {
                max-height: 300px !important;
            }
            
            .dlq-section {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 16px;
                padding: 2rem;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                margin-bottom: 2rem;
            }
            
            .section-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1.5rem;
                flex-wrap: wrap;
                gap: 1rem;
            }
            
            .section-title {
                font-size: 1.25rem;
                font-weight: 600;
                color: #111827;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }
            
            .dlq-badge {
                background: #ef4444;
                color: white;
                padding: 0.25rem 0.75rem;
                border-radius: 50px;
                font-size: 0.875rem;
                font-weight: 600;
            }
            
            .table-responsive {
                overflow-x: auto;
                border-radius: 12px;
                box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.05);
            }
            
            table {
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                background: white;
            }
            
            thead th {
                background: #f9fafb;
                color: #6b7280;
                font-weight: 600;
                font-size: 0.75rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                padding: 1rem;
                text-align: left;
                border-bottom: 2px solid #e5e7eb;
            }
            
            tbody td {
                padding: 1rem;
                color: #111827;
                border-bottom: 1px solid #f3f4f6;
                font-size: 0.875rem;
            }
            
            tbody tr {
                transition: background-color 0.2s ease;
            }
            
            tbody tr:hover {
                background-color: #f9fafb;
            }
            
            .btn-retry {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 0.5rem 1.25rem;
                border-radius: 8px;
                font-size: 0.875rem;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.3s ease;
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
            }
            
            .btn-retry:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }
            
            .btn-retry:active {
                transform: translateY(0);
            }
            
            .empty-state {
                text-align: center;
                padding: 3rem 1rem;
                color: #6b7280;
            }
            
            .empty-state i {
                font-size: 3rem;
                color: #d1d5db;
                margin-bottom: 1rem;
            }
            
            .empty-state p {
                font-size: 1rem;
                margin: 0;
            }
            
            .footer {
                text-align: center;
                color: rgba(255, 255, 255, 0.9);
                font-size: 0.875rem;
                margin-top: 2rem;
                padding: 1rem;
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 0.5rem;
            }
            
            .footer i {
                color: rgba(255, 255, 255, 0.7);
            }
            
            @media (max-width: 768px) {
                .header h1 { font-size: 1.5rem; }
                .stats-grid { grid-template-columns: 1fr; }
                .stat-value { font-size: 2rem; }
            }
            
            .loading-spinner {
                border: 3px solid #f3f4f6;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 2rem auto;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>
                    <i class="fas fa-tachometer-alt"></i>
                    QueueCTL Dashboard
                </h1>
                <div class="status-badge">
                    <div class="pulse-dot"></div>
                    Live Monitoring
                </div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card blue" id="card-workers">
                    <div class="stat-header">
                        <div>
                            <div class="stat-label">Active Workers</div>
                            <div class="stat-value" id="workers">0</div>
                        </div>
                        <div class="stat-icon blue">
                            <i class="fas fa-users"></i>
                        </div>
                    </div>
                </div>
                
                <div class="stat-card yellow" id="card-pending">
                    <div class="stat-header">
                        <div>
                            <div class="stat-label">Pending Jobs</div>
                            <div class="stat-value" id="pending">0</div>
                        </div>
                        <div class="stat-icon yellow">
                            <i class="fas fa-clock"></i>
                        </div>
                    </div>
                </div>
                
                <div class="stat-card green" id="card-completed">
                    <div class="stat-header">
                        <div>
                            <div class="stat-label">Completed Jobs</div>
                            <div class="stat-value" id="completed">0</div>
                        </div>
                        <div class="stat-icon green">
                            <i class="fas fa-check-circle"></i>
                        </div>
                    </div>
                </div>
                
                <div class="stat-card red" id="card-dlq">
                    <div class="stat-header">
                        <div>
                            <div class="stat-label">DLQ Size</div>
                            <div class="stat-value" id="dlq">0</div>
                        </div>
                        <div class="stat-icon red">
                            <i class="fas fa-exclamation-triangle"></i>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="chart-container">
                <div class="chart-title">
                    <i class="fas fa-chart-pie"></i>
                    Job Distribution
                </div>
                <canvas id="jobChart"></canvas>
            </div>
            
            <div class="chart-container">
                <div class="chart-title">
                    <i class="fas fa-chart-line"></i>
                    Trends (Last 60 Minutes)
                </div>
                <canvas id="trendChart"></canvas>
            </div>
            
            <div class="dlq-section">
                <div class="section-header">
                    <div class="section-title">
                        <i class="fas fa-inbox"></i>
                        Dead Letter Queue
                        <span class="dlq-badge" id="dlq-badge">0</span>
                    </div>
                </div>
                
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>Job ID</th>
                                <th>Command</th>
                                <th>Attempts</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="dlq-table">
                            <tr><td colspan="4"><div class="loading-spinner"></div></td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div class="footer">
                <i class="far fa-clock"></i>
                Last updated: <strong id="last-updated">–</strong>
            </div>
        </div>

        <script>
        let jobChart = null;
        let trendChart = null;

        async function fetchData() {
            try {
                const [statusRes, dlqRes, trendRes] = await Promise.all([
                    fetch('/status'),
                    fetch('/dlq'),
                    fetch('/metrics/timeseries')
                ]);

                const statusData = await statusRes.json();
                const dlqData = await dlqRes.json();
                const trendData = await trendRes.json();

                document.getElementById('workers').innerText = statusData.workers_active;
                document.getElementById('pending').innerText = statusData.job_counts.pending || 0;
                document.getElementById('completed').innerText = statusData.job_counts.completed || 0;
                document.getElementById('dlq').innerText = statusData.dlq_size;
                document.getElementById('dlq-badge').innerText = statusData.dlq_size;

                const dlqTable = document.getElementById('dlq-table');
                dlqTable.innerHTML = '';
                if (!dlqData || dlqData.length === 0) {
                    dlqTable.innerHTML = `
                        <tr>
                            <td colspan="4">
                                <div class="empty-state">
                                    <i class="fas fa-check-circle"></i>
                                    <p>No jobs in Dead Letter Queue</p>
                                </div>
                            </td>
                        </tr>`;
                } else {
                    dlqData.forEach(job => {
                        dlqTable.innerHTML += `
                            <tr>
                                <td><strong>${job.id}</strong></td>
                                <td><code>${job.command}</code></td>
                                <td>${job.attempts}</td>
                                <td>
                                    <button class="btn-retry" onclick="retryJob('${job.id}')">
                                        <i class="fas fa-redo"></i>
                                        Retry
                                    </button>
                                </td>
                            </tr>`;
                    });
                }

                updateChart(statusData, trendData);
                document.getElementById('last-updated').innerText = new Date().toLocaleTimeString();
            } catch (err) {
                console.error("Error fetching data:", err);
            }
        }

        function updateChart(statusData, trendData) {
            const ctx = document.getElementById('jobChart');
            if (jobChart) jobChart.destroy();
            
            jobChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: Object.keys(statusData.job_counts),
                    datasets: [{
                        data: Object.values(statusData.job_counts),
                        backgroundColor: ['#3b82f6', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6'],
                        borderWidth: 0,
                        hoverOffset: 10
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 15,
                                font: { size: 12, family: 'Inter' },
                                usePointStyle: true,
                                pointStyle: 'circle'
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            padding: 12,
                            cornerRadius: 8,
                            titleFont: { size: 14, family: 'Inter' },
                            bodyFont: { size: 13, family: 'Inter' }
                        }
                    }
                }
            });

            const tctx = document.getElementById('trendChart');
            if (trendChart) trendChart.destroy();
            
            if (trendData.labels.length > 0) {
                trendChart = new Chart(tctx, {
                    type: 'line',
                    data: {
                        labels: trendData.labels,
                        datasets: [
                            {
                                label: 'Completed',
                                data: trendData.completed,
                                borderColor: '#10b981',
                                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                tension: 0.4,
                                fill: true,
                                borderWidth: 2,
                                pointRadius: 3,
                                pointHoverRadius: 5
                            },
                            {
                                label: 'Failed',
                                data: trendData.failed,
                                borderColor: '#ef4444',
                                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                                tension: 0.4,
                                fill: true,
                                borderWidth: 2,
                                pointRadius: 3,
                                pointHoverRadius: 5
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        interaction: {
                            mode: 'index',
                            intersect: false
                        },
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: {
                                    padding: 15,
                                    font: { size: 12, family: 'Inter' },
                                    usePointStyle: true,
                                    pointStyle: 'circle'
                                }
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                padding: 12,
                                cornerRadius: 8,
                                titleFont: { size: 14, family: 'Inter' },
                                bodyFont: { size: 13, family: 'Inter' }
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    precision: 0,
                                    font: { family: 'Inter' }
                                },
                                grid: {
                                    color: 'rgba(0, 0, 0, 0.05)'
                                }
                            },
                            x: {
                                ticks: {
                                    font: { family: 'Inter' },
                                    maxRotation: 45,
                                    minRotation: 45
                                },
                                grid: {
                                    display: false
                                }
                            }
                        }
                    }
                });
            }
        }

        async function retryJob(jobId) {
            if (!confirm(`Are you sure you want to requeue job ${jobId}?`)) return;
            
            try {
                const res = await fetch(`/dlq/retry/${jobId}`, { method: "POST" });
                const data = await res.json();
                
                if (data.status === "requeued") {
                    alert(`✓ Job ${jobId} requeued successfully.`);
                    fetchData();
                } else {
                    alert("✗ Retry failed: " + (data.error || "Unknown error"));
                }
            } catch (err) {
                alert("✗ Network error: " + err.message);
            }
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