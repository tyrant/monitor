import importlib
import json
import logging
import urllib.error
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def alert_module(monkeypatch):
    def load(**env):
        for name in ("MONITOR_RESEND_API_KEY", "MONITOR_ALERT_FROM", "MONITOR_ALERT_TO"):
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        import alert
        return importlib.reload(alert)
    return load


def _sent_request(mock_urlopen):
    return mock_urlopen.call_args[0][0]


@pytest.fixture
def mock_urlopen():
    with patch("urllib.request.urlopen") as mocked:
        mocked.return_value.__enter__.return_value = MagicMock()
        yield mocked


# ── send_alert ────────────────────────────────────────────────────────────────

def test_send_alert_skips_without_api_key(alert_module, mock_urlopen):
    alert = alert_module(MONITOR_ALERT_FROM="from@example.com")
    alert.send_alert("subject", "body")
    mock_urlopen.assert_not_called()


def test_send_alert_skips_without_from_address(alert_module, mock_urlopen):
    alert = alert_module(MONITOR_RESEND_API_KEY="re_key")
    alert.send_alert("subject", "body")
    mock_urlopen.assert_not_called()


def test_send_alert_posts_to_resend(alert_module, mock_urlopen):
    alert = alert_module(MONITOR_RESEND_API_KEY="re_key", MONITOR_ALERT_FROM="from@example.com")
    alert.send_alert("subject", "body")
    assert _sent_request(mock_urlopen).full_url == "https://api.resend.com/emails"


def test_send_alert_authenticates_with_bearer_key(alert_module, mock_urlopen):
    alert = alert_module(MONITOR_RESEND_API_KEY="re_key", MONITOR_ALERT_FROM="from@example.com")
    alert.send_alert("subject", "body")
    assert _sent_request(mock_urlopen).get_header("Authorization") == "Bearer re_key"


def test_send_alert_sends_correct_fields(alert_module, mock_urlopen):
    alert = alert_module(
        MONITOR_RESEND_API_KEY="re_key",
        MONITOR_ALERT_FROM="from@example.com",
        MONITOR_ALERT_TO="to@example.com",
    )
    alert.send_alert("Test subject", "Test body")
    assert json.loads(_sent_request(mock_urlopen).data) == {
        "from": "from@example.com",
        "to": ["to@example.com"],
        "subject": "Test subject",
        "text": "Test body",
    }


def test_send_alert_defaults_to_from_address_as_recipient(alert_module, mock_urlopen):
    alert = alert_module(MONITOR_RESEND_API_KEY="re_key", MONITOR_ALERT_FROM="from@example.com")
    alert.send_alert("subject", "body")
    assert json.loads(_sent_request(mock_urlopen).data)["to"] == ["from@example.com"]


def test_send_alert_uses_a_timeout(alert_module, mock_urlopen):
    alert = alert_module(MONITOR_RESEND_API_KEY="re_key", MONITOR_ALERT_FROM="from@example.com")
    alert.send_alert("subject", "body")
    assert mock_urlopen.call_args.kwargs["timeout"] == alert.SEND_TIMEOUT_SECS


def test_send_alert_logs_error_on_failure(alert_module, mock_urlopen, caplog):
    alert = alert_module(MONITOR_RESEND_API_KEY="re_key", MONITOR_ALERT_FROM="from@example.com")
    mock_urlopen.side_effect = urllib.error.URLError("timed out")
    with caplog.at_level(logging.ERROR):
        alert.send_alert("subject", "body")
    assert any("Failed to send alert" in record.message for record in caplog.records)
