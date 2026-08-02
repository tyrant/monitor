# Script Monitor

Flask dashboard for monitoring `substack_heart.py` and `medium_clap.py`.

## Stack
- Python 3.12 / Flask 3 / Gunicorn
- SQLite (monitor.db — not in git)
- Deployed to `monitor.mikeyclarke.co.nz` on 119.9.131.4

## Architecture
- Scripts POST JSON to `POST /api/run` after each run (via `~/Work/scripts/monitor_client.py`)
- Flask stores run records in SQLite, triggers email alerts on crash or >30% failure rate
- `check_missing.py` runs via cron at 14:00 server time — alerts if either script hasn't reported in today
- Web UI at `GET /` is protected by nginx Basic Auth
- `POST /api/run` is exempt from Basic Auth — authenticated by `X-API-Key` header instead

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

## Server paths
- App: `/home/noob/monitor/`
- DB: `/home/noob/monitor/monitor.db`
- Env: `/home/noob/monitor/.env`
- Systemd: `sudo systemctl [start|stop|restart|status] monitor`
- nginx config: `/opt/nginx/conf/nginx.conf` (custom install, not system nginx)

## Alert behaviour
- Crash (traceback / login failure): immediate email alert
- >30% failure rate: immediate warning email (different subject prefix)
- No run by 14:00: daily cron sends warning email
- Alerts use Gmail SMTP with App Password (not OAuth) — set in `.env`

## Monitored scripts
- `substack_heart` — `~/Work/scripts/substack_heart.py`
- `medium_clap` — `~/Work/scripts/medium_clap.py`
- `gmail_substack_archive` — `~/Work/scripts/gmail_substack_archive.py`
- `blog_backup` — `~/Work/monitor/run_backup.py`
- `ticketmaster_import` — `comedy-gigs-app` (remote; reports in, not triggerable)

The `SCRIPTS` list is duplicated in `app.py` and `check_missing.py` — update both when adding a script.
