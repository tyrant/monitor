import subprocess
from unittest.mock import MagicMock, mock_open, patch

import pytest


def _run(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


# ── load_api_key ──────────────────────────────────────────────────────────────

def test_load_api_key_reads_from_env_file():
    content = "OTHER=val\nMONITOR_API_KEY=secret123\nMORE=stuff\n"
    with patch("builtins.open", mock_open(read_data=content)):
        import importlib, run_backup
        importlib.reload(run_backup)
        assert run_backup.load_api_key() == "secret123"


def test_load_api_key_returns_empty_string_when_file_missing():
    with patch("builtins.open", side_effect=OSError("not found")):
        import importlib, run_backup
        importlib.reload(run_backup)
        assert run_backup.load_api_key() == ""


def test_load_api_key_returns_empty_string_when_key_absent():
    content = "OTHER=val\nANOTHER=thing\n"
    with patch("builtins.open", mock_open(read_data=content)):
        import importlib, run_backup
        importlib.reload(run_backup)
        assert run_backup.load_api_key() == ""


# ── post_result ───────────────────────────────────────────────────────────────

def test_post_result_sends_success_payload():
    import importlib, run_backup, urllib.request
    importlib.reload(run_backup)

    with patch("urllib.request.urlopen") as mock_open:
        run_backup.post_result("key", "success", [])

    req = mock_open.call_args[0][0]
    import json
    body = json.loads(req.data)
    assert body["script"] == "blog_backup"
    assert body["status"] == "success"
    assert body["processed"] == 1
    assert body["failed"] == 0
    assert req.get_header("X-api-key") == "key"


def test_post_result_sends_crashed_payload():
    import importlib, run_backup
    importlib.reload(run_backup)

    with patch("urllib.request.urlopen") as mock_urlopen:
        run_backup.post_result("key", "crashed", ["err1"])

    import json
    body = json.loads(mock_urlopen.call_args[0][0].data)
    assert body["status"] == "crashed"
    assert body["processed"] == 0
    assert body["failed"] == 1
    assert body["errors"] == ["err1"]


def test_post_result_does_not_raise_on_network_error():
    import importlib, run_backup
    importlib.reload(run_backup)

    with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
        run_backup.post_result("key", "success", [])  # must not raise


# ── main ──────────────────────────────────────────────────────────────────────

def test_main_posts_success_on_zero_exit(tmp_path):
    import importlib, run_backup
    importlib.reload(run_backup)

    with patch("subprocess.run", return_value=_run(0)) as mock_sub, \
         patch.object(run_backup, "post_result") as mock_post, \
         patch.object(run_backup, "load_api_key", return_value="k"):
        run_backup.main()

    mock_post.assert_called_once_with("k", "success", [])


def test_main_posts_crashed_on_nonzero_exit():
    import importlib, run_backup
    importlib.reload(run_backup)

    with patch("subprocess.run", return_value=_run(1, stderr="pg_dump failed")), \
         patch.object(run_backup, "post_result") as mock_post, \
         patch.object(run_backup, "load_api_key", return_value="k"):
        with pytest.raises(SystemExit):
            run_backup.main()

    mock_post.assert_called_once_with("k", "crashed", ["pg_dump failed"])


def test_main_exits_with_backup_return_code():
    import importlib, run_backup
    importlib.reload(run_backup)

    with patch("subprocess.run", return_value=_run(2)), \
         patch.object(run_backup, "post_result"), \
         patch.object(run_backup, "load_api_key", return_value="k"):
        with pytest.raises(SystemExit) as exc_info:
            run_backup.main()

    assert exc_info.value.code == 2


def test_main_includes_stdout_in_errors_when_stderr_empty():
    import importlib, run_backup
    importlib.reload(run_backup)

    with patch("subprocess.run", return_value=_run(1, stdout="some output", stderr="")), \
         patch.object(run_backup, "post_result") as mock_post, \
         patch.object(run_backup, "load_api_key", return_value="k"):
        with pytest.raises(SystemExit):
            run_backup.main()

    assert "some output" in mock_post.call_args[0][2]


def test_main_calls_correct_backup_script():
    import importlib, run_backup
    importlib.reload(run_backup)

    with patch("subprocess.run", return_value=_run(0)) as mock_sub, \
         patch.object(run_backup, "post_result"), \
         patch.object(run_backup, "load_api_key", return_value="k"):
        run_backup.main()

    assert mock_sub.call_args[0][0] == ["bash", run_backup.BACKUP_SCRIPT]
