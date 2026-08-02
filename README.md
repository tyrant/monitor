# Script Monitor

A Flask dashboard that tracks daily runs of several scripts (`substack_heart`, `medium_clap`, `gmail_substack_archive`, `blog_backup`, `ticketmaster_import`), sends email alerts on failure, and lets you trigger runs manually.

Live at **https://monitor.mikeyclarke.co.nz** (HTTP Basic Auth protected).

## Features

- Per-script status cards with colour-coded indicators (green / amber / red)
- 14-day sparkline history per script
- Paginated run history table (10 runs per page) with per-row warning details
- **Run now** button to trigger a script execution on demand
- Immediate email alerts on crash or >30% failure rate
- Daily cron alert if any script hasn't reported in by 14:00 server time

## Architecture

Scripts POST their results to `POST /api/run` after each run. The server stores runs in SQLite, evaluates status, and sends alerts if needed. `check_missing.py` runs via cron at 14:00 to catch scripts that never reported.

```
substack_heart          ──┐
medium_clap             ──┤
gmail_substack_archive  ──┤  POST /api/run  →  Flask app  →  SQLite
blog_backup             ──┤                              ↘  Gmail alerts
ticketmaster_import     ──┘
```

## Stack

- Python 3.12 / Flask 3 / Gunicorn
- SQLite (`monitor.db` — not in git)
- Gmail SMTP with App Password for alerts
- nginx (custom install at `/opt/nginx/`) with HTTP Basic Auth on the web UI
- `/api/run` is exempt from Basic Auth — authenticated by `X-API-Key` header

## Local dev

```bash
cd ~/Work/monitor
python3 -m venv venv && venv/bin/pip install -r requirements.txt
MONITOR_API_KEY=dev FLASK_DEBUG=1 venv/bin/flask run --port 5001
```

## Deployment

```bash
bash deploy.sh          # subsequent deploys
bash setup_server.sh    # first-time only
```

`deploy.sh` rsyncs the app to the server and restarts the systemd service.

## Server

| Item | Path |
|---|---|
| App | `/home/noob/monitor/` |
| DB | `/home/noob/monitor/monitor.db` |
| Env | `/home/noob/monitor/.env` |
| Logs | `sudo journalctl -u monitor -f` |
| Systemd | `sudo systemctl [start\|stop\|restart\|status] monitor` |
| nginx config | `/opt/nginx/conf/nginx.conf` |

## Alert behaviour

| Condition | Alert |
|---|---|
| Script crashes (unhandled exception) | Immediate email with traceback |
| >30% failure rate on a run | Immediate email with percentage |
| Script hasn't reported by 14:00 server time | Daily cron email |

Alerts use Gmail SMTP with an App Password (not OAuth) — configured in `.env`.

## Monitored scripts

| Script | Verb | Runs on |
|---|---|---|
| `substack_heart` | hearted | mikeyclarke.co.nz server, 00:00 UTC |
| `medium_clap` | clapped | mikeyclarke.co.nz server, 01:00 UTC |
| `gmail_substack_archive` | archived | mikeyclarke.co.nz server, 02:00 UTC |
| `blog_backup` | backed up | mikeyclarke.co.nz server, 02:00 UTC |
| `ticketmaster_import` | imported | comedy-gigs-app (remote; reports in, not triggerable) |

## Tests

```bash
venv/bin/pytest
```

All tests use an isolated in-memory SQLite database and mock `send_alert` / `subprocess.Popen`.
