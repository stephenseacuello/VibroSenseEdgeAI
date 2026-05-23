"""Tests for the MQTT → SQLite persister.

The persister's hot path is its `on_message` callback. We exercise it directly
without standing up Mosquitto by importing the topic-dispatch helpers.
"""

from __future__ import annotations

import json
import sqlite3
import types
from pathlib import Path

import pytest

import gateway.mqtt_to_sqlite as mod


def _msg(topic, payload):
    """Build the duck-typed object paho hands to on_message callbacks."""
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload).encode()
    elif isinstance(payload, str):
        payload = payload.encode()
    return types.SimpleNamespace(topic=topic, payload=payload)


@pytest.fixture
def db_conn(tmp_path):
    p = tmp_path / "events.sqlite"
    conn = sqlite3.connect(p, isolation_level=None)
    conn.executescript(Path("gateway/db/schema.sql").read_text())
    yield conn
    conn.close()


def _dispatch(conn, msg):
    """Recreate the on_message closure from gateway.mqtt_to_sqlite.main()."""
    try:
        m = json.loads(msg.payload.decode())
        topic = msg.topic
        if topic.endswith("/state"):
            mod.insert_state(conn, m)
        elif topic.endswith("/alarm"):
            mod.insert_alarm(conn, m)
    except Exception as exc:  # noqa: BLE001
        mod.log.warning("insert failed on %s: %s", msg.topic, exc)


# state -------------------------------------------------------------------


def test_state_inserts_valid_row(db_conn):
    _dispatch(db_conn, _msg("pdm/fan-01/state", {
        "schema_ver": 1,
        "asset_id": "fan-01",
        "ts_utc": "2026-07-15T14:30:00Z",
        "state": "HEALTHY",
        "confidence": 0.91,
        "seq": 5,
    }))
    row = db_conn.execute("SELECT asset_id, state, seq FROM events").fetchone()
    assert row == ("fan-01", "HEALTHY", 5)


def test_state_drops_non_json(db_conn):
    _dispatch(db_conn, _msg("pdm/fan-01/state", b"not json"))
    assert db_conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


def test_state_drops_missing_field(db_conn):
    _dispatch(db_conn, _msg("pdm/fan-01/state", {
        "schema_ver": 1,
        "asset_id": "fan-01",
        # ts_utc missing
        "state": "HEALTHY",
        "confidence": 0.91,
        "seq": 5,
    }))
    assert db_conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


# alarm -------------------------------------------------------------------


def test_alarm_inserts_full_transition(db_conn):
    _dispatch(db_conn, _msg("pdm/fan-01/alarm", {
        "schema_ver": 1,
        "asset_id": "fan-01",
        "ts_utc": "2026-07-15T14:30:01Z",
        "from": "HEALTHY",
        "to": "IMBALANCE",
        "confidence": 0.88,
    }))
    row = db_conn.execute(
        "SELECT asset_id, from_state, to_state, confidence FROM alarms"
    ).fetchone()
    assert row == ("fan-01", "HEALTHY", "IMBALANCE", 0.88)


def test_alarm_accepts_null_from_first_transition(db_conn):
    _dispatch(db_conn, _msg("pdm/fan-02/alarm", {
        "schema_ver": 1,
        "asset_id": "fan-02",
        "ts_utc": "2026-07-15T14:30:00Z",
        "from": None,
        "to": "BEARING_FAULT",
        "confidence": 0.81,
    }))
    row = db_conn.execute(
        "SELECT asset_id, from_state, to_state FROM alarms"
    ).fetchone()
    assert row == ("fan-02", None, "BEARING_FAULT")


def test_alarm_missing_to_dropped(db_conn):
    _dispatch(db_conn, _msg("pdm/fan-01/alarm", {
        "schema_ver": 1,
        "asset_id": "fan-01",
        "ts_utc": "2026-07-15T14:30:01Z",
        "from": "HEALTHY",
        # no "to"
        "confidence": 0.88,
    }))
    assert db_conn.execute("SELECT COUNT(*) FROM alarms").fetchone()[0] == 0


def test_state_and_alarm_dont_cross_tables(db_conn):
    _dispatch(db_conn, _msg("pdm/fan-01/state", {
        "schema_ver": 1, "asset_id": "fan-01", "ts_utc": "t",
        "state": "HEALTHY", "confidence": 0.9, "seq": 1,
    }))
    _dispatch(db_conn, _msg("pdm/fan-01/alarm", {
        "schema_ver": 1, "asset_id": "fan-01", "ts_utc": "t",
        "from": "HEALTHY", "to": "IMBALANCE", "confidence": 0.9,
    }))
    assert db_conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    assert db_conn.execute("SELECT COUNT(*) FROM alarms").fetchone()[0] == 1


def test_ensure_schema_is_idempotent(tmp_path):
    p = tmp_path / "events.sqlite"
    conn = sqlite3.connect(p, isolation_level=None)
    mod.ensure_schema(conn)
    mod.ensure_schema(conn)  # second call must not raise
    conn.execute("SELECT * FROM events")
    conn.execute("SELECT * FROM alarms")
    conn.close()
