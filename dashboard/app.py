"""Ops dashboard: pipeline health + schedule-collision detection.

Reads execution history from SQLite (seeded with demo data below). In
production this reads from BigQuery via the Cloud Run Admin API instead,
same shape, same collision logic, just a different source.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

DB_PATH = Path(__file__).parent / "demo_executions.db"
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI()


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    (count,) = conn.execute("SELECT COUNT(*) FROM executions").fetchone()
    if count:
        return
    now = datetime.now(timezone.utc)
    seed = [
        ("data-extraction-demo", now - timedelta(hours=2), now - timedelta(hours=1, minutes=52), "success"),
        ("data-etl-demo", now - timedelta(hours=1), now - timedelta(minutes=57), "success"),
        ("inventory-sync-demo", now - timedelta(minutes=90), now - timedelta(minutes=85), "success"),
        ("inventory-sync-demo", now - timedelta(hours=1, minutes=58), now - timedelta(hours=1, minutes=52), "failed"),
        # deliberate overlap, this is what the collision detector below should catch
        ("data-extraction-demo", now - timedelta(minutes=30), now - timedelta(minutes=22), "success"),
        ("data-etl-demo", now - timedelta(minutes=29), now - timedelta(minutes=25), "success"),
    ]
    conn.executemany(
        "INSERT INTO executions (job_name, started_at, finished_at, status) VALUES (?, ?, ?, ?)",
        [(j, s.isoformat(), f.isoformat(), st) for j, s, f, st in seed],
    )
    conn.commit()


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT, started_at TEXT, finished_at TEXT, status TEXT
        )"""
    )
    _seed_if_empty(conn)
    return conn


def find_collisions(executions):
    """Two executions collide if their [started_at, finished_at] windows
    overlap and they're different jobs. Same self-join-on-time-windows
    technique as the real dashboard this is modeled on, the thing that
    actually catches a rate-limit collision before it happens instead of
    after."""
    collisions = []
    for i, a in enumerate(executions):
        for b in executions[i + 1 :]:
            if a["job_name"] == b["job_name"]:
                continue
            a_start, a_end = datetime.fromisoformat(a["started_at"]), datetime.fromisoformat(a["finished_at"])
            b_start, b_end = datetime.fromisoformat(b["started_at"]), datetime.fromisoformat(b["finished_at"])
            if a_start < b_end and b_start < a_end:
                collisions.append((a, b))
    return collisions


@app.get("/", response_class=HTMLResponse)
def overview(request: Request):
    conn = get_db()
    executions = conn.execute(
        "SELECT * FROM executions ORDER BY started_at DESC LIMIT 50"
    ).fetchall()
    collisions = find_collisions(executions)
    return TEMPLATES.TemplateResponse(
        request, "dashboard.html", {"executions": executions, "collisions": collisions}
    )
