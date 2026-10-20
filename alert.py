import json
import logging
import os
import urllib.request

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
# DigitalOcean blocks outbound SMTP, so alerts go over Resend's HTTPS API; the
# timeout keeps a slow send well inside gunicorn's 30s worker timeout.
SEND_TIMEOUT_SECS = 10

RESEND_API_KEY = os.environ.get("MONITOR_RESEND_API_KEY", "")
ALERT_FROM = os.environ.get("MONITOR_ALERT_FROM", "")
ALERT_TO = os.environ.get("MONITOR_ALERT_TO", ALERT_FROM)


def send_alert(subject, body):
    if not RESEND_API_KEY or not ALERT_FROM:
        log.warning("Alert skipped — MONITOR_RESEND_API_KEY or MONITOR_ALERT_FROM not set")
        return
    payload = json.dumps({
        "from": ALERT_FROM,
        "to": [ALERT_TO],
        "subject": subject,
        "text": body,
    }).encode()
    request = urllib.request.Request(
        RESEND_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "comfy-monitor",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=SEND_TIMEOUT_SECS):
            pass
        log.info(f"Alert sent: {subject}")
    except Exception as e:
        log.error(f"Failed to send alert: {e}")
