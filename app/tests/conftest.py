"""Shared pytest fixtures for the Flask app."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

import pytest

SCHEMA = Path("gateway/db/schema.sql")

SEED_EVENTS = [
    # asset_id, ts_utc,                  state,         confidence, seq
    ("fan-01", "2026-07-15T14:30:00.000Z", "HEALTHY",       0.92, 1),
    ("fan-01", "2026-07-15T14:30:01.000Z", "IMBALANCE",     0.88, 2),
    ("fan-01", "2026-07-15T14:30:02.000Z", "HEALTHY",       0.95, 3),
    ("fan-02", "2026-07-15T14:30:00.000Z", "BEARING_FAULT", 0.81, 1),
]

SEED_ALARMS = [
    # asset_id, ts_utc, from_state, to_state, confidence
    ("fan-01", "2026-07-15T14:30:01.000Z", "HEALTHY",   "IMBALANCE",     0.88),
    ("fan-01", "2026-07-15T14:30:02.000Z", "IMBALANCE", "HEALTHY",       0.95),
    ("fan-02", "2026-07-15T14:30:00.000Z", None,        "BEARING_FAULT", 0.81),
]


def _build_db(path: Path, events: Iterable[tuple], alarms: Iterable[tuple]) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA.read_text())
    conn.executemany(
        "INSERT INTO events (asset_id, ts_utc, state, confidence, seq) VALUES (?, ?, ?, ?, ?)",
        events,
    )
    conn.executemany(
        "INSERT INTO alarms (asset_id, ts_utc, from_state, to_state, confidence) "
        "VALUES (?, ?, ?, ?, ?)",
        alarms,
    )
    conn.commit()
    conn.close()


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "test.sqlite"
    _build_db(p, SEED_EVENTS, SEED_ALARMS)
    return p


@pytest.fixture
def empty_db_path(tmp_path):
    p = tmp_path / "empty.sqlite"
    _build_db(p, [], [])
    return p


@pytest.fixture
def app(db_path, monkeypatch):
    monkeypatch.setenv("VIBROSENSE_DB", str(db_path))
    monkeypatch.setenv("VIBROSENSE_NO_BRIDGE", "1")
    from app import create_app

    a = create_app()
    a.config["TESTING"] = True
    return a


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def empty_client(empty_db_path, monkeypatch):
    monkeypatch.setenv("VIBROSENSE_DB", str(empty_db_path))
    monkeypatch.setenv("VIBROSENSE_NO_BRIDGE", "1")
    from app import create_app

    a = create_app()
    a.config["TESTING"] = True
    return a.test_client()
