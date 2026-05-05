from datetime import datetime, timedelta, timezone


def _ts(days_ago=0, hour=12):
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


def _record(db, script="substack_heart", status="success", processed=10,
            failed=1, skipped=2, errors=None, days_ago=0):
    db.record_run(script, _ts(days_ago), status, processed, failed, skipped, errors or [])


# ── get_last_run ──────────────────────────────────────────────────────────────

def test_get_last_run_returns_none_when_no_runs(fresh_db):
    assert fresh_db.get_last_run("substack_heart") is None


def test_get_last_run_returns_most_recent(fresh_db):
    _record(fresh_db, processed=5, days_ago=2)
    _record(fresh_db, processed=99, days_ago=0)
    result = fresh_db.get_last_run("substack_heart")
    assert result["processed"] == 99


def test_get_last_run_is_scoped_to_script(fresh_db):
    _record(fresh_db, script="substack_heart", processed=10)
    _record(fresh_db, script="medium_clap", processed=50)
    assert fresh_db.get_last_run("substack_heart")["processed"] == 10
    assert fresh_db.get_last_run("medium_clap")["processed"] == 50


def test_get_last_run_deserialises_errors(fresh_db):
    _record(fresh_db, errors=["warn 1", "warn 2"])
    result = fresh_db.get_last_run("substack_heart")
    assert result["errors"] == ["warn 1", "warn 2"]


def test_get_last_run_returns_all_fields(fresh_db):
    _record(fresh_db, processed=10, failed=2, skipped=3, status="partial")
    result = fresh_db.get_last_run("substack_heart")
    assert result["processed"] == 10
    assert result["failed"] == 2
    assert result["skipped"] == 3
    assert result["status"] == "partial"


# ── get_all_runs ──────────────────────────────────────────────────────────────

def test_get_all_runs_empty(fresh_db):
    assert fresh_db.get_all_runs("substack_heart") == []


def test_get_all_runs_returns_newest_first(fresh_db):
    _record(fresh_db, processed=1, days_ago=2)
    _record(fresh_db, processed=2, days_ago=1)
    _record(fresh_db, processed=3, days_ago=0)
    runs = fresh_db.get_all_runs("substack_heart")
    assert [r["processed"] for r in runs] == [3, 2, 1]


def test_get_all_runs_respects_limit(fresh_db):
    for i in range(5):
        _record(fresh_db, days_ago=i)
    assert len(fresh_db.get_all_runs("substack_heart", limit=3)) == 3


def test_get_all_runs_scoped_to_script(fresh_db):
    _record(fresh_db, script="substack_heart")
    _record(fresh_db, script="medium_clap")
    assert len(fresh_db.get_all_runs("substack_heart")) == 1
    assert len(fresh_db.get_all_runs("medium_clap")) == 1


# ── get_run_history ───────────────────────────────────────────────────────────

def test_get_run_history_length(fresh_db):
    assert len(fresh_db.get_run_history("substack_heart", days=14)) == 14


def test_get_run_history_no_runs_all_none(fresh_db):
    history = fresh_db.get_run_history("substack_heart", days=7)
    assert all(d["status"] is None for d in history)


def test_get_run_history_fills_in_todays_run(fresh_db):
    _record(fresh_db, status="success", days_ago=0)
    history = fresh_db.get_run_history("substack_heart", days=7)
    assert history[-1]["status"] == "success"


def test_get_run_history_uses_most_recent_run_per_day(fresh_db):
    # Two runs today — first partial, second success
    ts_early = datetime.now(timezone.utc).replace(hour=8).isoformat()
    ts_late = datetime.now(timezone.utc).replace(hour=14).isoformat()
    fresh_db.record_run("substack_heart", ts_early, "partial", 5, 5, 0, [])
    fresh_db.record_run("substack_heart", ts_late, "success", 10, 0, 0, [])
    history = fresh_db.get_run_history("substack_heart", days=7)
    assert history[-1]["status"] == "success"


def test_get_run_history_oldest_first(fresh_db):
    _record(fresh_db, days_ago=2)
    _record(fresh_db, days_ago=0)
    history = fresh_db.get_run_history("substack_heart", days=7)
    days_with_data = [d["day"] for d in history if d["status"]]
    assert days_with_data == sorted(days_with_data)


# ── ran_today ─────────────────────────────────────────────────────────────────

def test_ran_today_false_when_no_runs(fresh_db):
    assert fresh_db.ran_today("substack_heart") is False


def test_ran_today_true_after_todays_run(fresh_db):
    _record(fresh_db, days_ago=0)
    assert fresh_db.ran_today("substack_heart") is True


def test_ran_today_false_for_yesterdays_run(fresh_db):
    _record(fresh_db, days_ago=1)
    assert fresh_db.ran_today("substack_heart") is False


def test_ran_today_scoped_to_script(fresh_db):
    _record(fresh_db, script="medium_clap", days_ago=0)
    assert fresh_db.ran_today("substack_heart") is False
    assert fresh_db.ran_today("medium_clap") is True
