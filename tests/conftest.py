import os
import pytest

# Point db at a fresh in-memory SQLite for every test
os.environ.setdefault("MONITOR_API_KEY", "test-key")
os.environ.setdefault("MONITOR_DB_PATH", ":memory:")


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch, tmp_path):
    """Each test gets its own isolated SQLite database."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("MONITOR_DB_PATH", db_path)

    # Re-import db so DB_PATH picks up the patched env var
    import importlib
    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    yield db_module


@pytest.fixture()
def app_client(fresh_db, monkeypatch):
    """Flask test client with a fresh database."""
    monkeypatch.setenv("MONITOR_API_KEY", "test-key")

    import importlib
    import app as app_module
    importlib.reload(app_module)

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client
