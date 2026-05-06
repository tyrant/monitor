import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = os.environ.get(
    "MONITOR_DB_PATH",
    os.path.join(os.path.dirname(__file__), "monitor.db"),
)


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                script      TEXT    NOT NULL,
                ran_at      TEXT    NOT NULL,
                status      TEXT    NOT NULL,
                processed   INTEGER NOT NULL DEFAULT 0,
                failed      INTEGER NOT NULL DEFAULT 0,
                skipped     INTEGER NOT NULL DEFAULT 0,
                errors      TEXT    NOT NULL DEFAULT '[]',
                received_at TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_runs_script_ran_at ON runs(script, ran_at)"
        )


def record_run(script, ran_at, status, processed, failed, skipped, errors):
    with _conn() as conn:
        conn.execute(
            """INSERT INTO runs (script, ran_at, status, processed, failed, skipped, errors)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (script, ran_at, status, processed, failed, skipped, json.dumps(errors or [])),
        )


def get_last_run(script):
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE script = ? ORDER BY ran_at DESC LIMIT 1",
            (script,),
        ).fetchone()
    if not row:
        return None
    r = dict(row)
    r["errors"] = json.loads(r["errors"])
    return r


def get_run_history(script, days=14):
    """One record per day (most recent run) for the last N days, oldest first."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT date(ran_at) AS day, status, processed, failed, skipped
            FROM   runs
            WHERE  script = ? AND date(ran_at) >= ?
            GROUP  BY date(ran_at)
            HAVING ran_at = MAX(ran_at)
            ORDER  BY day ASC
            """,
            (script, since),
        ).fetchall()

    by_day = {r["day"]: dict(r) for r in rows}
    history = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        history.append(by_day.get(d, {"day": d, "status": None, "processed": 0, "failed": 0, "skipped": 0}))
    return history


def get_run_count(script):
    with _conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM runs WHERE script = ?", (script,)
        ).fetchone()[0]


def get_all_runs(script, limit=60, offset=0):
    with _conn() as conn:
        rows = conn.execute(
            """SELECT * FROM runs WHERE script = ?
               ORDER BY ran_at DESC LIMIT ? OFFSET ?""",
            (script, limit, offset),
        ).fetchall()
    result = []
    for row in rows:
        r = dict(row)
        r["errors"] = json.loads(r["errors"])
        result.append(r)
    return result


def ran_today(script):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM runs WHERE script = ? AND date(ran_at) = ? LIMIT 1",
            (script, today),
        ).fetchone()
    return row is not None
