#!/home/noob/monitor/venv/bin/python3
"""Runs the blog DB backup and reports the outcome to the monitor dashboard."""
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

BACKUP_SCRIPT = "/home/noob/blog/backup_script.sh"
MONITOR_URL = "https://monitor.mikeyclarke.co.nz/api/run"
ENV_FILE = "/home/noob/monitor/.env"


def load_api_key():
    try:
        with open(ENV_FILE) as f:
            for line in f:
                if line.startswith("MONITOR_API_KEY="):
                    return line.strip().split("=", 1)[1]
    except OSError:
        pass
    return ""


def post_result(api_key, status, errors):
    payload = json.dumps({
        "script": "blog_backup",
        "status": status,
        "processed": 1 if status == "success" else 0,
        "failed": 1 if status == "crashed" else 0,
        "skipped": 0,
        "errors": errors,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }).encode()
    req = urllib.request.Request(
        MONITOR_URL,
        data=payload,
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Monitor report failed (non-fatal): {e}", file=sys.stderr)


def main():
    api_key = load_api_key()
    result = subprocess.run(
        ["bash", BACKUP_SCRIPT],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        post_result(api_key, "success", [])
    else:
        errors = [s.strip() for s in [result.stderr, result.stdout] if s.strip()]
        post_result(api_key, "crashed", errors)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
