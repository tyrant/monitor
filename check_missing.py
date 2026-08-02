#!/usr/bin/env python3
"""Daily cron — alerts if any script hasn't reported in today.

Cron entry (2pm server time):
    0 14 * * * /home/noob/monitor/venv/bin/python /home/noob/monitor/check_missing.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from datetime import date

from alert import send_alert
from db import ran_today

SCRIPTS = ["substack_heart", "medium_clap", "gmail_substack_archive", "blog_backup", "ticketmaster_import"]


def main():
    today = date.today().isoformat()
    missing = [s for s in SCRIPTS if not ran_today(s)]
    if missing:
        send_alert(
            f"[Monitor] Scripts haven't run today: {', '.join(missing)}",
            f"No run recorded today ({today}) for:\n\n" + "\n".join(f"  • {s}" for s in missing),
        )
        print(f"Alert sent for: {', '.join(missing)}")
    else:
        print(f"All scripts ran today ({today}). OK.")


if __name__ == "__main__":
    main()
