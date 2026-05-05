from datetime import datetime, timezone
from unittest.mock import call, patch


def _record_today(db, script):
    db.record_run(script, datetime.now(timezone.utc).isoformat(),
                  "success", 10, 0, 0, [])


# ── check_missing.main ────────────────────────────────────────────────────────

def test_no_alert_when_both_scripts_ran_today(fresh_db):
    _record_today(fresh_db, "substack_heart")
    _record_today(fresh_db, "medium_clap")

    with patch("alert.send_alert") as mock_alert:
        import importlib, check_missing
        importlib.reload(check_missing)
        check_missing.main()

    mock_alert.assert_not_called()


def test_alerts_when_no_scripts_ran_today(fresh_db):
    with patch("alert.send_alert") as mock_alert:
        import importlib, check_missing
        importlib.reload(check_missing)
        check_missing.main()

    mock_alert.assert_called_once()
    subject = mock_alert.call_args[0][0]
    assert "substack_heart" in subject
    assert "medium_clap" in subject


def test_alerts_only_for_missing_script(fresh_db):
    _record_today(fresh_db, "substack_heart")

    with patch("alert.send_alert") as mock_alert:
        import importlib, check_missing
        importlib.reload(check_missing)
        check_missing.main()

    mock_alert.assert_called_once()
    subject = mock_alert.call_args[0][0]
    assert "medium_clap" in subject
    assert "substack_heart" not in subject


def test_prints_ok_when_all_ran(fresh_db, capsys):
    _record_today(fresh_db, "substack_heart")
    _record_today(fresh_db, "medium_clap")

    with patch("alert.send_alert"):
        import importlib, check_missing
        importlib.reload(check_missing)
        check_missing.main()

    assert "OK" in capsys.readouterr().out


def test_prints_alert_sent_when_missing(fresh_db, capsys):
    with patch("alert.send_alert"):
        import importlib, check_missing
        importlib.reload(check_missing)
        check_missing.main()

    assert "Alert sent" in capsys.readouterr().out
