import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

from flask import Flask, abort, jsonify, redirect, render_template, request

from alert import send_alert
from db import get_all_runs, get_last_run, get_run_count, get_run_history, init_db, record_run

app = Flask(__name__)

API_KEY = os.environ.get("MONITOR_API_KEY", "")
SCRIPTS = ["substack_heart", "medium_clap", "blog_backup"]
SCRIPT_VERBS = {
    "substack_heart": "hearted",
    "medium_clap": "clapped",
    "blog_backup": "backed up",
}

FAILURE_RATE_THRESHOLD = 0.30
PAGE_SIZE = 10

NZ_TZ = ZoneInfo("Pacific/Auckland")

SCRIPT_COMMANDS = {
    "substack_heart": ["/home/noob/scripts/venv/bin/python", "/home/noob/scripts/substack_heart.py"],
    "medium_clap":    ["/home/noob/scripts/venv/bin/python", "/home/noob/scripts/medium_clap.py"],
    "blog_backup":    ["/home/noob/monitor/venv/bin/python", "/home/noob/monitor/run_backup.py"],
}

_running: dict[str, subprocess.Popen] = {}

init_db()


def _page_url(current_args, script_name, page):
    params = dict(current_args)
    params[f"{script_name}_page"] = page
    return "/?" + urlencode(params)


def _fmt_timestamp(iso):
    """Convert a UTC ISO string to a display dict with NZ local time and a UTC tooltip."""
    if not iso:
        return {"display": "—", "title": ""}
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        dt_nz = dt.astimezone(NZ_TZ)
        dt_utc = dt.astimezone(timezone.utc)

        today = datetime.now(NZ_TZ).date()
        if dt_nz.date() == today:
            display = f"Today, {dt_nz.strftime('%H:%M')}"
        elif dt_nz.date() == today - timedelta(days=1):
            display = f"Yesterday, {dt_nz.strftime('%H:%M')}"
        else:
            display = dt_nz.strftime("%-d %b %Y, %H:%M")

        offset = dt_nz.utcoffset()
        total_mins = int(offset.total_seconds() / 60)
        sign = "+" if total_mins >= 0 else "-"
        h, m = divmod(abs(total_mins), 60)
        offset_str = f"UTC{sign}{h}" if m == 0 else f"UTC{sign}{h}:{m:02d}"

        return {
            "display": display,
            "title": f"{offset_str} · {dt_utc.strftime('%-d %b %Y, %H:%M UTC')}",
        }
    except ValueError:
        return {"display": iso, "title": ""}


def _determine_status(client_status, processed, failed):
    if client_status == "crashed":
        return "crashed"
    total = processed + failed
    if total > 0 and failed / total > FAILURE_RATE_THRESHOLD:
        return "partial"
    return "success"


def _is_running(script: str) -> bool:
    proc = _running.get(script)
    return proc is not None and proc.poll() is None


@app.route("/trigger/<script>", methods=["POST"])
def trigger_script(script):
    if script not in SCRIPTS:
        abort(404)
    if _is_running(script):
        return redirect(f"/?busy={script}")
    try:
        _running[script] = subprocess.Popen(
            SCRIPT_COMMANDS[script], env=os.environ.copy()
        )
    except FileNotFoundError:
        return redirect(f"/?unavailable={script}")
    return redirect(f"/?triggered={script}")


@app.route("/")
def index():
    scripts = []
    for name in SCRIPTS:
        last = get_last_run(name)
        if last:
            last["ran_at_fmt"] = _fmt_timestamp(last["ran_at"])

        total = get_run_count(name)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(1, min(int(request.args.get(f"{name}_page", 1)), total_pages))
        offset = (page - 1) * PAGE_SIZE
        runs = get_all_runs(name, limit=PAGE_SIZE, offset=offset)
        for r in runs:
            r["ran_at_fmt"] = _fmt_timestamp(r["ran_at"])

        scripts.append({
            "name": name,
            "display": name.replace("_", " "),
            "verb": SCRIPT_VERBS.get(name, "processed"),
            "last": last,
            "history": get_run_history(name, days=14),
            "runs": runs,
            "page": page,
            "total_pages": total_pages,
            "prev_url": _page_url(request.args, name, page - 1) if page > 1 else None,
            "next_url": _page_url(request.args, name, page + 1) if page < total_pages else None,
        })
    running = {s for s in SCRIPTS if _is_running(s)}
    return render_template("index.html", scripts=scripts, now=_fmt_timestamp(
        datetime.now(timezone.utc).isoformat()
    ), running=running)


@app.route("/api/run", methods=["POST"])
def receive_run():
    if not API_KEY or request.headers.get("X-API-Key") != API_KEY:
        abort(401)

    data = request.get_json(silent=True)
    if not data or data.get("script") not in SCRIPTS:
        abort(400)

    script = data["script"]
    processed = int(data.get("processed", 0))
    failed = int(data.get("failed", 0))
    skipped = int(data.get("skipped", 0))
    errors = data.get("errors") or []
    ran_at = data.get("ran_at") or datetime.now(timezone.utc).isoformat()

    status = _determine_status(data.get("status", "success"), processed, failed)

    record_run(script, ran_at, status, processed, failed, skipped, errors)

    if status == "crashed":
        send_alert(
            f"[Monitor] {script} crashed",
            f"{script} crashed at {ran_at}.\n\nErrors:\n\n" + "\n".join(errors),
        )
    elif status == "partial":
        total = processed + failed
        pct = int(failed / total * 100) if total else 0
        send_alert(
            f"[Monitor] {script} high failure rate ({pct}%)",
            f"{script} ran at {ran_at}.\n\nProcessed: {processed}  Failed: {failed} ({pct}%)  Skipped: {skipped}",
        )

    return jsonify({"ok": True, "status": status})
