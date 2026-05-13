"""
Daily Planet FR — Pipeline Dashboard
Accessible sur http://VPS_IP:8080 avec HTTP Basic Auth.
"""
import json
import os
from datetime import datetime, timezone, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, Response, render_template, request

LOGS_DIR = Path(os.getenv("LOGS_DIR", "/app/logs"))
RUNS_DIR = LOGS_DIR / "runs"

app = Flask(__name__, template_folder="templates")


# ── Auth ──────────────────────────────────────────────────────────────────────

DASHBOARD_USER = os.getenv("DASHBOARD_USER", "admin")
DASHBOARD_PASS = os.getenv("DASHBOARD_PASSWORD", "changeme")


def _check_auth(username: str, password: str) -> bool:
    return username == DASHBOARD_USER and password == DASHBOARD_PASS


def _require_auth():
    return Response(
        "Accès restreint.",
        401,
        {"WWW-Authenticate": 'Basic realm="Daily Planet Dashboard"'},
    )


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not _check_auth(auth.username, auth.password):
            return _require_auth()
        return f(*args, **kwargs)
    return decorated


# ── Data loading ──────────────────────────────────────────────────────────────

def load_runs(limit: int = 60) -> list:
    if not RUNS_DIR.exists():
        return []
    runs = []
    for f in sorted(RUNS_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            with open(f) as fp:
                runs.append(json.load(fp))
        except Exception:
            pass
    return runs


def compute_stats(runs: list) -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    runs_today = [r for r in runs if (r.get("started_at") or "")[:10] == today]
    successes  = [r for r in runs_today if r.get("status") == "success"]
    cost_today = sum(r.get("costs", {}).get("total_usd", 0.0) for r in runs_today)

    success_rate = (
        round(len(successes) / len(runs_today) * 100) if runs_today else 0
    )

    return {
        "runs_today":    len(runs_today),
        "success_rate":  success_rate,
        "cost_today":    cost_today,
        "articles_today": len(successes),
    }


def format_duration(run: dict) -> str:
    started  = run.get("started_at")
    finished = run.get("finished_at")
    if not started or not finished:
        return "—"
    try:
        def _parse(s):
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s)
        delta = _parse(finished) - _parse(started)
        secs  = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s"
        return f"{secs // 60}m{secs % 60:02d}s"
    except Exception:
        return "—"


def format_date(iso: str) -> str:
    if not iso:
        return "—"
    try:
        if iso.endswith("Z"):
            iso = iso[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso)
        # Convert to Paris time (UTC+1/+2) — approximate with UTC+1
        dt = dt.astimezone(timezone(timedelta(hours=1)))
        return dt.strftime("%d %b %Y · %H:%M")
    except Exception:
        return iso[:16]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
@requires_auth
def dashboard():
    runs  = load_runs()
    stats = compute_stats(runs)

    # Enrich runs with display fields
    for r in runs:
        r["_duration"] = format_duration(r)
        r["_date"]     = format_date(r.get("started_at"))

    now_str = datetime.now(timezone(timedelta(hours=1))).strftime("%d/%m/%Y %H:%M")
    return render_template("index.html", runs=runs, stats=stats, now=now_str)


@app.route("/api/runs")
@requires_auth
def api_runs():
    return app.response_class(
        response=json.dumps(load_runs(), ensure_ascii=False),
        mimetype="application/json",
    )


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
