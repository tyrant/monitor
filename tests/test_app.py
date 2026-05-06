import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


HEADERS = {"X-API-Key": "test-key", "Content-Type": "application/json"}


def _post(client, payload):
    return client.post("/api/run", data=json.dumps(payload), headers=HEADERS)


def _run_payload(**kwargs):
    return {
        "script": "substack_heart",
        "status": "success",
        "processed": 10,
        "failed": 1,
        "skipped": 2,
        "errors": [],
        "ran_at": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }


# ── GET / ─────────────────────────────────────────────────────────────────────

def test_index_returns_200(app_client):
    assert app_client.get("/").status_code == 200


def test_index_shows_script_names(app_client):
    html = app_client.get("/").data.decode()
    assert "substack heart" in html
    assert "medium clap" in html


def test_index_shows_no_runs_when_empty(app_client):
    html = app_client.get("/").data.decode()
    assert html.count("No runs recorded") == 3


def test_index_shows_run_history_after_run_posted(app_client):
    _post(app_client, _run_payload(processed=42))
    html = app_client.get("/").data.decode()
    assert "42" in html


# ── POST /api/run — auth ──────────────────────────────────────────────────────

def test_post_run_rejects_missing_api_key(app_client):
    resp = app_client.post("/api/run", data=json.dumps(_run_payload()),
                           content_type="application/json")
    assert resp.status_code == 401


def test_post_run_rejects_wrong_api_key(app_client):
    headers = {**HEADERS, "X-API-Key": "wrong"}
    resp = app_client.post("/api/run", data=json.dumps(_run_payload()),
                           headers=headers)
    assert resp.status_code == 401


def test_post_run_rejects_unknown_script(app_client):
    resp = _post(app_client, _run_payload(script="unknown_script"))
    assert resp.status_code == 400


def test_post_run_rejects_missing_body(app_client):
    resp = app_client.post("/api/run", data="not json", headers=HEADERS)
    assert resp.status_code == 400


# ── POST /api/run — status determination ─────────────────────────────────────

def test_post_run_stores_success(app_client, fresh_db):
    _post(app_client, _run_payload(status="success", processed=10, failed=2))
    assert fresh_db.get_last_run("substack_heart")["status"] == "success"


def test_post_run_stores_crashed(app_client, fresh_db):
    _post(app_client, _run_payload(status="crashed", processed=0, failed=0))
    assert fresh_db.get_last_run("substack_heart")["status"] == "crashed"


def test_post_run_upgrades_to_partial_on_high_failure_rate(app_client, fresh_db):
    # 4 failed out of 10 total = 40% > 30% threshold
    _post(app_client, _run_payload(status="success", processed=6, failed=4))
    assert fresh_db.get_last_run("substack_heart")["status"] == "partial"


def test_post_run_stays_success_below_threshold(app_client, fresh_db):
    # 3 failed out of 10 total = 30%, not strictly greater than threshold
    _post(app_client, _run_payload(status="success", processed=7, failed=3))
    assert fresh_db.get_last_run("substack_heart")["status"] == "success"


def test_post_run_success_with_zero_processed(app_client, fresh_db):
    _post(app_client, _run_payload(processed=0, failed=0, skipped=5))
    assert fresh_db.get_last_run("substack_heart")["status"] == "success"


def test_post_run_returns_status_in_response(app_client):
    resp = _post(app_client, _run_payload(processed=6, failed=4))
    assert resp.get_json()["status"] == "partial"


# ── POST /api/run — alerting ──────────────────────────────────────────────────

def test_post_run_sends_crash_alert(app_client):
    with patch("app.send_alert") as mock_alert:
        _post(app_client, _run_payload(status="crashed", errors=["Traceback..."]))
    mock_alert.assert_called_once()
    subject = mock_alert.call_args[0][0]
    assert "crashed" in subject


def test_post_run_sends_partial_alert(app_client):
    with patch("app.send_alert") as mock_alert:
        _post(app_client, _run_payload(processed=6, failed=4))
    mock_alert.assert_called_once()
    subject = mock_alert.call_args[0][0]
    assert "failure rate" in subject


def test_post_run_no_alert_on_success(app_client):
    with patch("app.send_alert") as mock_alert:
        _post(app_client, _run_payload(processed=10, failed=1))
    mock_alert.assert_not_called()


def test_post_run_crash_alert_includes_errors(app_client):
    with patch("app.send_alert") as mock_alert:
        _post(app_client, _run_payload(status="crashed", errors=["line 1", "line 2"]))
    body = mock_alert.call_args[0][1]
    assert "line 1" in body
    assert "line 2" in body


def test_post_run_partial_alert_includes_percentage(app_client):
    with patch("app.send_alert") as mock_alert:
        # 5 failed out of 10 = 50%
        _post(app_client, _run_payload(processed=5, failed=5))
    subject = mock_alert.call_args[0][0]
    assert "50%" in subject


# ── POST /api/run — persistence ───────────────────────────────────────────────

def test_post_run_persists_all_fields(app_client, fresh_db):
    _post(app_client, _run_payload(
        script="medium_clap", processed=20, failed=3, skipped=5, errors=["w1"]
    ))
    run = fresh_db.get_last_run("medium_clap")
    assert run["processed"] == 20
    assert run["failed"] == 3
    assert run["skipped"] == 5
    assert run["errors"] == ["w1"]


def test_post_run_uses_provided_ran_at(app_client, fresh_db):
    ts = "2026-01-15T08:00:00+00:00"
    _post(app_client, _run_payload(ran_at=ts))
    run = fresh_db.get_last_run("substack_heart")
    assert run["ran_at"] == ts


def test_multiple_runs_accumulate(app_client, fresh_db):
    _post(app_client, _run_payload(script="substack_heart"))
    _post(app_client, _run_payload(script="substack_heart"))
    _post(app_client, _run_payload(script="medium_clap"))
    assert len(fresh_db.get_all_runs("substack_heart")) == 2
    assert len(fresh_db.get_all_runs("medium_clap")) == 1


# ── blog_backup script ────────────────────────────────────────────────────────

def test_index_shows_blog_backup(app_client):
    html = app_client.get("/").data.decode()
    assert "blog backup" in html


def test_post_run_accepts_blog_backup(app_client, fresh_db):
    resp = _post(app_client, _run_payload(script="blog_backup", processed=1, failed=0))
    assert resp.status_code == 200
    assert fresh_db.get_last_run("blog_backup")["status"] == "success"


def test_post_run_blog_backup_crash_sends_alert(app_client):
    with patch("app.send_alert") as mock_alert:
        _post(app_client, _run_payload(script="blog_backup", status="crashed",
                                       processed=0, failed=1,
                                       errors=["pg_dump: error: connection failed"]))
    mock_alert.assert_called_once()
    assert "crashed" in mock_alert.call_args[0][0]


# ── Timestamps ───────────────────────────────────────────────────────────────

def test_timestamps_show_utc_tooltip(app_client, fresh_db):
    _post(app_client, _run_payload(ran_at="2026-01-15T00:00:00+00:00"))
    html = app_client.get("/").data.decode()
    assert "UTC+" in html
    assert "UTC" in html


def test_timestamps_include_utc_time_in_title(app_client, fresh_db):
    _post(app_client, _run_payload(ran_at="2026-01-15T00:00:00+00:00"))
    html = app_client.get("/").data.decode()
    assert "15 Jan 2026" in html


# ── Pagination ───────────────────────────────────────────────────────────────

def _post_runs(client, n, script="substack_heart"):
    for i in range(n):
        _post(client, _run_payload(script=script, processed=i))


def test_index_shows_10_runs_per_page(app_client):
    _post_runs(app_client, 15)
    html = app_client.get("/").data.decode()
    # processed values 14..5 on page 1; "4" would only appear on page 2
    assert html.count('<tr class="row-success"') == 10


def test_index_shows_pagination_controls_when_more_than_one_page(app_client):
    _post_runs(app_client, 11)
    html = app_client.get("/").data.decode()
    assert "Next →" in html


def test_index_no_pagination_controls_when_one_page(app_client):
    _post_runs(app_client, 5)
    html = app_client.get("/").data.decode()
    assert "Next →" not in html


def test_index_page_2_shows_prev_link_not_next(app_client):
    _post_runs(app_client, 12)
    html = app_client.get("/?substack_heart_page=2").data.decode()
    assert 'href="/?substack_heart_page=1"' in html
    assert 'href="/?substack_heart_page=3"' not in html


def test_index_preserves_other_scripts_page_params(app_client):
    _post_runs(app_client, 11, script="substack_heart")
    _post_runs(app_client, 11, script="medium_clap")
    html = app_client.get("/?medium_clap_page=2").data.decode()
    # medium_clap prev link points to page 1 and preserves nothing extra
    assert "medium_clap_page=1" in html
    # substack_heart next link preserves medium_clap_page=2
    assert "medium_clap_page=2" in html


# ── POST /trigger/<script> ────────────────────────────────────────────────────

def test_trigger_redirects_with_triggered_param(app_client):
    with patch("app.subprocess.Popen", return_value=MagicMock()):
        resp = app_client.post("/trigger/substack_heart")
    assert resp.status_code == 302
    assert "triggered=substack_heart" in resp.headers["Location"]


def test_trigger_calls_correct_command(app_client):
    with patch("app.subprocess.Popen", return_value=MagicMock()) as mock_popen:
        app_client.post("/trigger/substack_heart")
    assert "substack_heart.py" in mock_popen.call_args[0][0][-1]


def test_trigger_unknown_script_returns_404(app_client):
    resp = app_client.post("/trigger/unknown_script")
    assert resp.status_code == 404


def test_trigger_already_running_redirects_to_busy(app_client):
    import app as app_module
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    app_module._running["substack_heart"] = mock_proc

    with patch("app.subprocess.Popen") as mock_popen:
        resp = app_client.post("/trigger/substack_heart")

    mock_popen.assert_not_called()
    assert "busy=substack_heart" in resp.headers["Location"]


def test_trigger_unavailable_redirects_gracefully(app_client):
    with patch("app.subprocess.Popen", side_effect=FileNotFoundError):
        resp = app_client.post("/trigger/substack_heart")
    assert "unavailable=substack_heart" in resp.headers["Location"]


def test_index_shows_run_now_buttons(app_client):
    html = app_client.get("/").data.decode()
    assert html.count("Run now") == 3


def test_index_shows_triggered_message(app_client):
    html = app_client.get("/?triggered=substack_heart").data.decode()
    assert "triggered" in html.lower()


def test_index_shows_busy_message(app_client):
    html = app_client.get("/?busy=substack_heart").data.decode()
    assert "already running" in html.lower()


def test_index_shows_unavailable_message(app_client):
    html = app_client.get("/?unavailable=substack_heart").data.decode()
    assert "not available" in html.lower()
