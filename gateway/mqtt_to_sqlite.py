"""MQTT subscriber that persists `pdm/+/state` and `pdm/+/alarm` to SQLite.

See PROJECT_PLAN.md §12.3 (schemas), ATP-08 (state persistence soak), and the
Node-RED state-change detector that produces alarms in §12.4.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path

import paho.mqtt.client as mqtt

DB_PATH = Path(os.environ.get("VIBROSENSE_DB", "gateway/db/vibrosense.sqlite"))
MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
STATE_TOPIC = "pdm/+/state"
ALARM_TOPIC = "pdm/+/alarm"
SCHEMA_PATH = Path(__file__).parent / "db" / "schema.sql"

log = logging.getLogger("mqtt_to_sqlite")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text())


def insert_state(conn: sqlite3.Connection, m: dict) -> None:
    conn.execute(
        "INSERT INTO events (asset_id, ts_utc, state, confidence, seq, schema_ver) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            m["asset_id"],
            m["ts_utc"],
            m["state"],
            float(m["confidence"]),
            int(m["seq"]),
            int(m.get("schema_ver", 1)),
        ),
    )


def insert_alarm(conn: sqlite3.Connection, m: dict) -> None:
    # Accept both the "from" / "to" wire format and the from_state / to_state internal naming.
    from_state = m.get("from", m.get("from_state"))
    to_state = m.get("to", m.get("to_state"))
    if to_state is None:
        raise ValueError("alarm missing 'to' field")
    conn.execute(
        "INSERT INTO alarms (asset_id, ts_utc, from_state, to_state, confidence, schema_ver) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            m["asset_id"],
            m["ts_utc"],
            from_state,
            to_state,
            float(m["confidence"]),
            int(m.get("schema_ver", 1)),
        ),
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, isolation_level=None, check_same_thread=False)
    ensure_schema(conn)

    def on_message(_client, _userdata, msg):
        try:
            m = json.loads(msg.payload.decode())
            topic = msg.topic
            if topic.endswith("/state"):
                insert_state(conn, m)
            elif topic.endswith("/alarm"):
                insert_alarm(conn, m)
            else:
                log.warning("ignoring topic %s", topic)
        except Exception as exc:  # noqa: BLE001
            log.warning("insert failed on %s: %s", msg.topic, exc)

    client = mqtt.Client(
        client_id="mqtt_to_sqlite", callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.subscribe([(STATE_TOPIC, 0), (ALARM_TOPIC, 1)])
    log.info("listening on %s and %s → %s", STATE_TOPIC, ALARM_TOPIC, DB_PATH)
    client.loop_forever()


if __name__ == "__main__":
    main()
