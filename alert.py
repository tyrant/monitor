import logging
import os
import smtplib
from email.mime.text import MIMEText

log = logging.getLogger(__name__)

GMAIL_ADDRESS = os.environ.get("MONITOR_ALERT_FROM", "")
GMAIL_APP_PASSWORD = os.environ.get("MONITOR_GMAIL_APP_PASSWORD", "")
ALERT_TO = os.environ.get("MONITOR_ALERT_TO", GMAIL_ADDRESS)


def send_alert(subject, body):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        log.warning("Alert skipped — MONITOR_ALERT_FROM or MONITOR_GMAIL_APP_PASSWORD not set")
        return
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = ALERT_TO
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        log.info(f"Alert sent: {subject}")
    except Exception as e:
        log.error(f"Failed to send alert: {e}")
