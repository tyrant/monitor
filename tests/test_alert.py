import smtplib
from unittest.mock import MagicMock, patch


def _send(**env):
    """Import alert fresh with patched env vars."""
    import importlib
    import alert
    importlib.reload(alert)
    return alert


# ── send_alert ────────────────────────────────────────────────────────────────

def test_send_alert_skips_when_no_credentials(monkeypatch, caplog):
    monkeypatch.delenv("MONITOR_ALERT_FROM", raising=False)
    monkeypatch.delenv("MONITOR_GMAIL_APP_PASSWORD", raising=False)
    import importlib, alert
    importlib.reload(alert)

    with patch("smtplib.SMTP_SSL") as mock_smtp:
        alert.send_alert("subject", "body")
        mock_smtp.assert_not_called()


def test_send_alert_sends_email_with_correct_fields(monkeypatch):
    monkeypatch.setenv("MONITOR_ALERT_FROM", "from@example.com")
    monkeypatch.setenv("MONITOR_GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setenv("MONITOR_ALERT_TO", "to@example.com")
    import importlib, alert
    importlib.reload(alert)

    mock_smtp = MagicMock()
    with patch("smtplib.SMTP_SSL", return_value=mock_smtp):
        mock_smtp.__enter__ = lambda s: s
        mock_smtp.__exit__ = MagicMock(return_value=False)
        alert.send_alert("Test subject", "Test body")

    mock_smtp.login.assert_called_once_with("from@example.com", "app-password")
    mock_smtp.send_message.assert_called_once()
    msg = mock_smtp.send_message.call_args[0][0]
    assert msg["Subject"] == "Test subject"
    assert msg["From"] == "from@example.com"
    assert msg["To"] == "to@example.com"


def test_send_alert_defaults_to_from_address_as_recipient(monkeypatch):
    monkeypatch.setenv("MONITOR_ALERT_FROM", "from@example.com")
    monkeypatch.setenv("MONITOR_GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.delenv("MONITOR_ALERT_TO", raising=False)
    import importlib, alert
    importlib.reload(alert)

    mock_smtp = MagicMock()
    with patch("smtplib.SMTP_SSL", return_value=mock_smtp):
        mock_smtp.__enter__ = lambda s: s
        mock_smtp.__exit__ = MagicMock(return_value=False)
        alert.send_alert("subj", "body")

    msg = mock_smtp.send_message.call_args[0][0]
    assert msg["To"] == "from@example.com"


def test_send_alert_logs_error_on_smtp_failure(monkeypatch, caplog):
    monkeypatch.setenv("MONITOR_ALERT_FROM", "from@example.com")
    monkeypatch.setenv("MONITOR_GMAIL_APP_PASSWORD", "bad-password")
    import importlib, alert
    importlib.reload(alert)

    with patch("smtplib.SMTP_SSL", side_effect=smtplib.SMTPAuthenticationError(535, b"Bad credentials")):
        import logging
        with caplog.at_level(logging.ERROR):
            alert.send_alert("subj", "body")

    assert any("Failed to send alert" in r.message for r in caplog.records)
