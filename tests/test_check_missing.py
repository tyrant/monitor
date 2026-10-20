from datetime import datetime, timezone
from unittest.mock import call, patch


def _record_today(db, script):
    db.record_run(script, datetime.now(timezone.utc).isoformat(),
                  "success", 10, 0, 0, [])


# ── check_missing.main ────────────────────────────────────────────────────────

def test_no_alert_when_all_scripts_ran_today(fresh_db):
    _record_today(fresh_db, "substack_heart")
    _record_today(fresh_db, "medium_clap")
    _record_today(fresh_db, "gmail_substack_archive")
    _record_today(fresh_db, "blog_backup")
    _record_today(fresh_db, "ticketmaster_import")

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
    _record_today(fresh_db, "gmail_substack_archive")
    _record_today(fresh_db, "blog_backup")
    _record_today(fresh_db, "ticketmaster_import")

    with patch("alert.send_alert") as mock_alert:
        import importlib, check_missing
        importlib.reload(check_missing)
        check_missing.main()

    mock_alert.assert_called_once()
    subject = mock_alert.call_args[0][0]
    assert "medium_clap" in subject
    assert "substack_heart" not in subject
    assert "blog_backup" not in subject


def test_alerts_when_blog_backup_missing(fresh_db):
    _record_today(fresh_db, "substack_heart")
    _record_today(fresh_db, "medium_clap")
    _record_today(fresh_db, "gmail_substack_archive")
    _record_today(fresh_db, "ticketmaster_import")

    with patch("alert.send_alert") as mock_alert:
        import importlib, check_missing
        importlib.reload(check_missing)
        check_missing.main()

    mock_alert.assert_called_once()
    assert "blog_backup" in mock_alert.call_args[0][0]


def test_alerts_when_ticketmaster_import_missing(fresh_db):
    _record_today(fresh_db, "substack_heart")
    _record_today(fresh_db, "medium_clap")
    _record_today(fresh_db, "gmail_substack_archive")
    _record_today(fresh_db, "blog_backup")

    with patch("alert.send_alert") as mock_alert:
        import importlib, check_missing
        importlib.reload(check_missing)
        check_missing.main()

    mock_alert.assert_called_once()
    assert "ticketmaster_import" in mock_alert.call_args[0][0]


def test_alerts_when_gmail_substack_archive_missing(fresh_db):
    _record_today(fresh_db, "substack_heart")
    _record_today(fresh_db, "medium_clap")
    _record_today(fresh_db, "blog_backup")
    _record_today(fresh_db, "ticketmaster_import")

    with patch("alert.send_alert") as mock_alert:
        import importlib, check_missing
        importlib.reload(check_missing)
        check_missing.main()

    mock_alert.assert_called_once()
    assert "gmail_substack_archive" in mock_alert.call_args[0][0]


def test_prints_ok_when_all_ran(fresh_db, capsys):
    _record_today(fresh_db, "substack_heart")
    _record_today(fresh_db, "medium_clap")
    _record_today(fresh_db, "gmail_substack_archive")
    _record_today(fresh_db, "blog_backup")
    _record_today(fresh_db, "ticketmaster_import")

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


# ── check_missing.load_env_file ───────────────────────────────────────────────

def test_load_env_file_sets_unset_variables(tmp_path, monkeypatch):
    monkeypatch.delenv("MONITOR_TEST_VAR", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("MONITOR_TEST_VAR=Monitor <monitor@example.com>\n")
    import check_missing
    check_missing.load_env_file(str(env_file))
    import os
    assert os.environ["MONITOR_TEST_VAR"] == "Monitor <monitor@example.com>"


def test_load_env_file_keeps_existing_variables(tmp_path, monkeypatch):
    monkeypatch.setenv("MONITOR_TEST_VAR", "from-cron")
    env_file = tmp_path / ".env"
    env_file.write_text("MONITOR_TEST_VAR=from-file\n")
    import check_missing
    check_missing.load_env_file(str(env_file))
    import os
    assert os.environ["MONITOR_TEST_VAR"] == "from-cron"


def test_load_env_file_skips_comments_and_blank_lines(tmp_path, monkeypatch):
    monkeypatch.delenv("MONITOR_TEST_VAR", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("# MONITOR_TEST_VAR=commented\n\nnot a setting\n")
    import check_missing
    check_missing.load_env_file(str(env_file))
    import os
    assert "MONITOR_TEST_VAR" not in os.environ


def test_load_env_file_ignores_missing_file(tmp_path):
    import check_missing
    check_missing.load_env_file(str(tmp_path / "absent.env"))
