"""
Traffic Enforcement System – Real-Time Web Dashboard
=====================================================

A self-contained Flask web application that:
  • Reads violations from the CSV log in real time
  • Exposes a REST API for the frontend
  • Serves a single-page dashboard with live charts

Usage:
    python utils/dashboard.py --log logs/violations.csv --port 5000

Dependencies (added to requirements.txt):
    flask
    pandas
"""

import argparse
import json
import hmac
import ipaddress
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    from flask import Flask, jsonify, render_template_string, request, Response
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False


# ─────────────────────────────────────────────────────────────────────────────
# In-memory stats cache (refreshed every 5 s from CSV)
# ─────────────────────────────────────────────────────────────────────────────

class StatsCache:
    def __init__(self, csv_path: str, refresh_interval: float = 5.0):
        self.csv_path         = Path(csv_path)
        from utils.evidence_review import EvidenceReviewStore
        self.review_store = EvidenceReviewStore(self.csv_path)
        self.refresh_interval = refresh_interval
        self._lock            = threading.Lock()
        self._data            = self._empty_data()
        self._running         = True
        self._thread          = threading.Thread(target=self._refresh_loop,
                                                  daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    def get(self) -> dict:
        with self._lock:
            return dict(self._data)

    def stop(self):
        self._running = False

    # ------------------------------------------------------------------
    def _refresh_loop(self):
        while self._running:
            try:
                self._reload()
            except Exception as e:
                print(f"[DASHBOARD] Stats refresh error: {e}")
            time.sleep(self.refresh_interval)

    def _reload(self):
        if not self.csv_path.exists():
            return

        if HAS_PANDAS:
            df = pd.read_csv(self.csv_path, parse_dates=["timestamp"])
            data = self._compute_pandas(df)
        else:
            import csv
            rows = []
            with open(self.csv_path, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(row)
            data = self._compute_plain(rows)

        data["review_counts"] = self.review_store.review_summary()
        with self._lock:
            self._data = data

    # ------------------------------------------------------------------
    def _compute_pandas(self, df) -> dict:
        now   = datetime.now()
        today = df[df["timestamp"].dt.date == now.date()]

        # Violations by type
        by_type = df["violation_type"].value_counts().to_dict()

        # Hourly timeline (last 24 h)
        last24 = df[df["timestamp"] >= now - timedelta(hours=24)]
        hourly = (
            last24.set_index("timestamp")
                  .resample("1H")["violation_type"]
                  .count()
                  .reset_index()
        )
        hourly_labels  = [t.strftime("%H:%M") for t in hourly["timestamp"]]
        hourly_counts  = hourly["violation_type"].tolist()

        # Top plates
        top_plates = df["license_plate"].value_counts().head(10).to_dict()

        # Speed histogram
        speed_df    = df[df["violation_type"] == "SPEED"]["speed_kmh"].dropna()
        speed_vals  = speed_df.astype(float).tolist()

        # Recent violations (last 20)
        recent = (
            df.sort_values("timestamp", ascending=False)
              .head(20)[["timestamp", "violation_type", "license_plate", "speed_kmh"]]
              .fillna("")
              .assign(timestamp=lambda x: x["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S"))
              .to_dict("records")
        )

        return {
            "total":         len(df),
            "today":         len(today),
            "by_type":       by_type,
            "hourly_labels": hourly_labels,
            "hourly_counts": hourly_counts,
            "top_plates":    top_plates,
            "speed_values":  speed_vals[:500],   # cap for chart
            "recent":        recent,
            "last_updated":  now.isoformat(),
        }

    def _compute_plain(self, rows: list) -> dict:
        """Fallback without pandas."""
        by_type    = defaultdict(int)
        top_plates = defaultdict(int)
        speed_vals = []
        today_str  = datetime.now().strftime("%Y-%m-%d")
        today_cnt  = 0

        for row in rows:
            vtype = row.get("violation_type", "UNKNOWN")
            plate = row.get("license_plate", "UNKNOWN")
            spd   = row.get("speed_kmh", "")
            ts    = row.get("timestamp", "")
            by_type[vtype]    += 1
            top_plates[plate] += 1
            if spd:
                try:
                    speed_vals.append(float(spd))
                except ValueError:
                    pass
            if ts.startswith(today_str):
                today_cnt += 1

        recent = [
            {
                "timestamp":      r.get("timestamp", ""),
                "violation_type": r.get("violation_type", ""),
                "license_plate":  r.get("license_plate", ""),
                "speed_kmh":      r.get("speed_kmh", ""),
            }
            for r in rows[-20:]
        ]
        recent.reverse()

        top10 = dict(sorted(top_plates.items(), key=lambda x: x[1], reverse=True)[:10])
        return {
            "total":         len(rows),
            "today":         today_cnt,
            "by_type":       dict(by_type),
            "hourly_labels": [],
            "hourly_counts": [],
            "top_plates":    top10,
            "speed_values":  speed_vals[:500],
            "recent":        recent,
            "last_updated":  datetime.now().isoformat(),
        }

    @staticmethod
    def _empty_data() -> dict:
        return {
            "total": 0, "today": 0, "by_type": {},
            "hourly_labels": [], "hourly_counts": [],
            "top_plates": {}, "speed_values": [],
            "recent": [], "last_updated": "",
        }


# ─────────────────────────────────────────────────────────────────────────────
# HTML template (single-page app)
# ─────────────────────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Traffic Enforcement Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --accent: #238636; --danger: #da3633; --warn: #d29922;
    --text: #e6edf3; --muted: #8b949e; --blue: #1f6feb;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; }
  header { background: var(--surface); border-bottom: 1px solid var(--border);
           padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 1.2rem; font-weight: 600; }
  header span { font-size: 0.8rem; color: var(--muted); margin-left: auto; }
  .live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent);
              box-shadow: 0 0 6px var(--accent); animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

  .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
             gap: 16px; padding: 24px; }
  .kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
         padding: 16px; text-align: center; }
  .kpi .val { font-size: 2rem; font-weight: 700; }
  .kpi .lbl { font-size: 0.75rem; color: var(--muted); margin-top: 4px; }
  .kpi.danger .val { color: var(--danger); }
  .kpi.warn   .val { color: var(--warn); }
  .kpi.ok     .val { color: var(--accent); }

  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
            padding: 0 24px 24px; }
  @media (max-width: 800px) { .charts { grid-template-columns: 1fr; } }
  .card { background: var(--surface); border: 1px solid var(--border);
          border-radius: 8px; padding: 16px; }
  .card h2 { font-size: 0.85rem; color: var(--muted); margin-bottom: 12px;
             text-transform: uppercase; letter-spacing: 0.05em; }
  canvas { max-height: 220px; }

  .wide { grid-column: 1 / -1; }
  table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
  th { color: var(--muted); padding: 6px 8px; text-align: left;
       border-bottom: 1px solid var(--border); }
  td { padding: 6px 8px; border-bottom: 1px solid var(--border); }
  tr:last-child td { border-bottom: none; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
           font-size: 0.7rem; font-weight: 600; }
  .badge.SPEED         { background:#da363322; color:#da3633; }
  .badge.LANE_DEPARTURE{ background:#d2992222; color:#d29922; }
  .badge.NO_SEATBELT   { background:#8957e522; color:#8957e5; }
  .badge.NO_HELMET     { background:#da363322; color:#da3633; }
  .badge.RED_LIGHT     { background:#da363322; color:#ff4444; }
  .badge.PHONE_USAGE   { background:#1f6feb22; color:#58a6ff; }
  .badge.DROWSY_DRIVER { background:#d2992222; color:#ffa657; }
  .badge.DISTRACTION   { background:#d2992222; color:#d29922; }
  .badge.HONKING       { background:#23863622; color:#3fb950; }
</style>
</head>
<body>
<header>
  <div class="live-dot"></div>
  <h1>🚦 AI Traffic Enforcement – Live Dashboard</h1>
  <span id="last-updated">Connecting…</span>
</header>

<div class="kpi-row">
  <div class="kpi danger"><div class="val" id="kpi-total">–</div><div class="lbl">Total Violations</div></div>
  <div class="kpi warn"> <div class="val" id="kpi-today">–</div><div class="lbl">Today</div></div>
  <div class="kpi ok">   <div class="val" id="kpi-types">–</div><div class="lbl">Violation Types</div></div>
  <div class="kpi ok">   <div class="val" id="kpi-plates">–</div><div class="lbl">Unique Plates</div></div>
</div>

<div class="charts">
  <div class="card"><h2>Violations by Type</h2><canvas id="chartType"></canvas></div>
  <div class="card"><h2>Hourly Timeline (last 24 h)</h2><canvas id="chartHourly"></canvas></div>
  <div class="card"><h2>Speed Distribution</h2><canvas id="chartSpeed"></canvas></div>
  <div class="card"><h2>Top Repeat Offenders</h2><canvas id="chartPlates"></canvas></div>
  <div class="card wide">
    <h2>Evidence review queue</h2>
    <p style="color:var(--muted);margin-bottom:10px">Review each event before enforcement action. Decisions are stored in the append-only evidence review journal.</p>
    <div id="review-list">Loading review queue…</div>
  </div>
  <div class="card wide">
    <h2>Recent Violations</h2>
    <table>
      <thead><tr><th>Timestamp</th><th>Type</th><th>Plate</th><th>Speed (km/h)</th></tr></thead>
      <tbody id="recent-tbody"><tr><td colspan="4" style="color:var(--muted)">Loading…</td></tr></tbody>
    </table>
  </div>
</div>

<script>
const COLORS = ['#da3633','#d29922','#238636','#1f6feb','#8957e5',
                '#ffa657','#79c0ff','#56d364','#ff7b72','#d2a8ff'];

function mkChart(id, type, data, opts={}) {
  const ctx = document.getElementById(id).getContext('2d');
  return new Chart(ctx, { type, data, options: {
    responsive: true, maintainAspectRatio: true,
    plugins: { legend: { labels: { color: '#e6edf3', font: {size:11} } } },
    scales: type !== 'pie' && type !== 'doughnut' ? {
      x: { ticks: { color:'#8b949e', font:{size:10} }, grid:{color:'#21262d'} },
      y: { ticks: { color:'#8b949e', font:{size:10} }, grid:{color:'#21262d'} }
    } : undefined,
    ...opts
  }});
}

let charts = {};

function initCharts() {
  charts.type = mkChart('chartType', 'doughnut',
    { labels:[], datasets:[{data:[], backgroundColor: COLORS}] });
  charts.hourly = mkChart('chartHourly', 'line',
    { labels:[], datasets:[{label:'Violations', data:[], borderColor:'#238636',
      backgroundColor:'#23863622', fill:true, tension:0.4}] });
  charts.speed = mkChart('chartSpeed', 'bar',
    { labels:[], datasets:[{label:'Count', data:[], backgroundColor:'#1f6feb88'}] },
    { plugins: { legend:{ display:false } } });
  charts.plates = mkChart('chartPlates', 'bar',
    { labels:[], datasets:[{label:'Violations', data:[], backgroundColor:'#8957e5aa',
      indexAxis:'y'}] },
    { indexAxis:'y', plugins:{ legend:{ display:false } } });
}

function bucketSpeeds(vals) {
  const min=40, max=160, step=10;
  const buckets = {};
  for (let v=min; v<max; v+=step) buckets[`${v}-${v+step}`]=0;
  vals.forEach(v => {
    const b = Math.floor(v/step)*step;
    const key = `${b}-${b+step}`;
    if (buckets[key]!==undefined) buckets[key]++;
  });
  return { labels: Object.keys(buckets), counts: Object.values(buckets) };
}

function updateCharts(d) {
  // Type doughnut
  charts.type.data.labels   = Object.keys(d.by_type);
  charts.type.data.datasets[0].data = Object.values(d.by_type);
  charts.type.update();

  // Hourly
  charts.hourly.data.labels = d.hourly_labels;
  charts.hourly.data.datasets[0].data = d.hourly_counts;
  charts.hourly.update();

  // Speed
  const sp = bucketSpeeds(d.speed_values);
  charts.speed.data.labels = sp.labels;
  charts.speed.data.datasets[0].data = sp.counts;
  charts.speed.update();

  // Plates
  const plates = d.top_plates;
  charts.plates.data.labels = Object.keys(plates);
  charts.plates.data.datasets[0].data = Object.values(plates);
  charts.plates.update();

  // KPIs
  document.getElementById('kpi-total').textContent  = d.total;
  document.getElementById('kpi-today').textContent  = d.today;
  document.getElementById('kpi-types').textContent  = Object.keys(d.by_type).length;
  document.getElementById('kpi-plates').textContent = Object.keys(d.top_plates).length;
  document.getElementById('last-updated').textContent =
    'Updated: ' + new Date(d.last_updated).toLocaleTimeString();

  // Recent table
  const tbody = document.getElementById('recent-tbody');
  tbody.innerHTML = '';
  if (!d.recent.length) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--muted)">No violations yet.</td></tr>';
    return;
  }
  d.recent.forEach(r => {
    const tr = document.createElement('tr');
    const badge = `<span class="badge ${r.violation_type}">${r.violation_type}</span>`;
    const cells = [r.timestamp, r.violation_type, r.license_plate, r.speed_kmh || '–'];
    cells.forEach((value, index) => {
      const td = document.createElement('td');
      if (index === 1) {
        const badge = document.createElement('span');
        badge.className = 'badge';
        badge.textContent = String(value ?? '');
        td.appendChild(badge);
      } else {
        td.textContent = String(value ?? '');
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

async function fetchReviewQueue() {
  const host = document.getElementById("review-list");
  try {
    const response = await fetch("/api/review?status=PENDING_REVIEW&limit=100");
    const rows = await response.json();
    if (!response.ok) throw new Error(rows.error || "Review queue unavailable");
    host.replaceChildren();
    if (!rows.length) { host.textContent = "No evidence awaiting review."; return; }
    rows.forEach(row => {
      const item = document.createElement("div");
      item.style.cssText = "border-top:1px solid var(--border);padding:12px 0;display:flex;gap:12px;align-items:center;flex-wrap:wrap";
      const details = document.createElement("div");
      details.style.cssText = "flex:1;min-width:240px";
      const title = document.createElement("strong");
      title.textContent = String(row.violation_type || "EVENT") + " · " + String(row.license_plate || "UNKNOWN") + " · " + String(row.camera_id || "single camera");
      const meta = document.createElement("div");
      meta.style.cssText = "color:var(--muted);font-size:.8rem";
      meta.textContent = String(row.timestamp || "") + " | " + String(row.event_id || "") + " | " + (row.evidence_sha256 ? "SHA-256 recorded" : "No evidence hash");
      details.append(title, meta); item.append(details);
      [["APPROVED","Approve"],["REJECTED","Reject"],["NEEDS_MORE_EVIDENCE","Needs evidence"]].forEach(([status,label]) => {
        const button = document.createElement("button"); button.textContent = label; button.style.cssText = "padding:7px 10px;cursor:pointer";
        button.addEventListener("click", async () => {
          const reviewer = window.prompt("Reviewer identifier:"); if (!reviewer) return;
          const note = window.prompt("Review note (optional):") || "";
          const result = await fetch("/api/review/" + encodeURIComponent(row.event_id), {method:"POST",headers:{"Content-Type":"application/json","X-Requested-With":"XMLHttpRequest"},body:JSON.stringify({status,note})});
          if (!result.ok) { const err = await result.json(); window.alert(err.error || "Could not save review"); return; }
          fetchReviewQueue();
        }); item.append(button);
      });
      host.append(item);
    });
  } catch (error) { host.textContent = "Review queue error: " + error.message; }
}

async function fetchStats() {
  try {
    const res  = await fetch('/api/stats');
    const data = await res.json();
    updateCharts(data);
  } catch(e) {
    document.getElementById('last-updated').textContent = 'Connection error';
  }
}

initCharts();
fetchStats();
fetchReviewQueue();
setInterval(fetchStats, 5000);
setInterval(fetchReviewQueue, 15000);
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Flask app factory
# ─────────────────────────────────────────────────────────────────────────────

def create_app(csv_path: str, refresh: float = 5.0, username=None, password=None):
    if not HAS_FLASK:
        raise RuntimeError("Flask is not installed.  Run: pip install flask")

    cache = StatsCache(csv_path, refresh)
    from utils.evidence_review import EvidenceReviewStore
    review_store = EvidenceReviewStore(csv_path)
    app   = Flask(__name__)
    username = username if username is not None else os.getenv('DASHBOARD_USERNAME')
    password = password if password is not None else os.getenv('DASHBOARD_PASSWORD')
    if bool(username) != bool(password):
        cache.stop()
        raise RuntimeError('Set both DASHBOARD_USERNAME and DASHBOARD_PASSWORD, or neither')

    @app.before_request
    def require_dashboard_auth():
        if not username:
            return None  # Localhost-only mode; main() prevents unsafe network binding.
        auth = request.authorization
        supplied_user = auth.username if auth else ''
        supplied_password = auth.password if auth else ''
        user_ok = hmac.compare_digest(str(supplied_user), str(username))
        password_ok = hmac.compare_digest(str(supplied_password), str(password))
        if not (user_ok and password_ok):
            return Response('Authentication required', 401,
                            {'WWW-Authenticate': 'Basic realm="Traffic Dashboard"'})
        return None

    @app.route("/")
    def index():
        return render_template_string(DASHBOARD_HTML)

    @app.route("/api/stats")
    def api_stats():
        return jsonify(cache.get())

    @app.route("/api/violations")
    def api_violations():
        data = cache.get()
        return jsonify(data.get("recent", []))

    @app.route("/api/review", methods=["GET"])
    def api_review_queue():
        status = request.args.get("status", "PENDING_REVIEW")
        try:
            return jsonify(review_store.list_events(status=status, limit=request.args.get("limit", 100)))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/review/<event_id>", methods=["POST"])
    def api_review_event(event_id):
        payload = request.get_json(silent=True) or {}
        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
            return jsonify({"error": "Missing same-origin request header"}), 403
        origin = request.headers.get("Origin")
        if origin:
            from urllib.parse import urlsplit
            if urlsplit(origin).netloc != request.host:
                return jsonify({"error": "Cross-origin review request rejected"}), 403
        auth = request.authorization
        reviewer = auth.username if auth else "local-operator"
        role = os.getenv("DASHBOARD_ROLE", "reviewer").strip().lower()
        if role not in {"administrator", "reviewer"}:
            return jsonify({"error": "This account cannot review evidence"}), 403
        try:
            row = review_store.update_status(event_id, payload.get("status"), reviewer, payload.get("note", ""))
            return jsonify(row)
        except KeyError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 409

    return app, cache


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Traffic Enforcement Dashboard")
    parser.add_argument("--log",     default="logs/violations.csv",
                        help="Path to violations CSV")
    parser.add_argument("--port",    type=int, default=5000)
    parser.add_argument("--host",    default="127.0.0.1",
                        help="Bind address; non-loopback access requires DASHBOARD_USERNAME and DASHBOARD_PASSWORD")
    parser.add_argument("--refresh", type=float, default=5.0,
                        help="Stats cache refresh interval in seconds")
    parser.add_argument("--debug",   action="store_true")
    args = parser.parse_args()

    try:
        bind_ip = ipaddress.ip_address(args.host)
        loopback = bind_ip.is_loopback
    except ValueError:
        loopback = args.host.lower() == 'localhost'
    has_user = bool(os.getenv('DASHBOARD_USERNAME'))
    has_password = bool(os.getenv('DASHBOARD_PASSWORD'))
    if has_user != has_password:
        parser.error('Set both DASHBOARD_USERNAME and DASHBOARD_PASSWORD')
    if not loopback and not (has_user and has_password):
        parser.error('Non-loopback dashboard binding requires DASHBOARD_USERNAME and DASHBOARD_PASSWORD')

    print(f"[DASHBOARD] Starting on http://{args.host}:{args.port}")
    print(f"[DASHBOARD] Watching: {args.log}")

    app, cache = create_app(args.log, args.refresh)
    try:
        app.run(host=args.host, port=args.port, debug=args.debug,
                use_reloader=False)
    finally:
        cache.stop()


if __name__ == "__main__":
    main()
