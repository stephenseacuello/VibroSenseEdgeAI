"""MQTT → SocketIO bridge.

Subscribes to `pdm/+/state` and `pdm/+/alarm`, validates each payload against
its v1 schema, and re-emits as a `state` or `alarm` SocketIO event respectively.
Malformed messages are logged and dropped so a single bad publisher cannot
poison the UI.

See PROJECT_PLAN.md §13.3 and ATP-04 (schema conformance).
"""

from __future__ import annotations

import json
import logging
import time

import paho.mqtt.client as mqtt
from flask_socketio import SocketIO

from ml.src.schema import AlarmV1, StateV1

log = logging.getLogger("app.mqtt_bridge")

STATE_TOPIC = "pdm/+/state"
ALARM_TOPIC = "pdm/+/alarm"
RECONNECT_DELAY_S = 2.0


def validate_state(data: bytes) -> dict | None:
    try:
        m = json.loads(data.decode())
        StateV1(**m)
        return m
    except Exception as exc:  # noqa: BLE001
        log.warning("dropping bad state payload: %s", exc)
        return None


def validate_alarm(data: bytes) -> dict | None:
    try:
        m = json.loads(data.decode())
        AlarmV1(**m)
        return m
    except Exception as exc:  # noqa: BLE001
        log.warning("dropping bad alarm payload: %s", exc)
        return None


# Back-compat: the existing app/tests/test_bridge.py imports validate_payload.
validate_payload = validate_state


def run_bridge(socketio: SocketIO, host: str, port: int) -> None:
    """Block on an MQTT client; reconnects forever."""
    client = mqtt.Client(
        client_id="flask_sockets",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )

    def on_message(_c, _u, msg):
        if msg.topic.endswith("/state"):
            payload = validate_state(msg.payload)
            if payload is not None:
                socketio.emit("state", payload)
        elif msg.topic.endswith("/alarm"):
            payload = validate_alarm(msg.payload)
            if payload is not None:
                socketio.emit("alarm", payload)

    client.on_message = on_message

    while True:
        try:
            client.connect(host, port, keepalive=30)
            client.subscribe([(STATE_TOPIC, 0), (ALARM_TOPIC, 1)])
            log.info("bridge listening on %s + %s at %s:%s", STATE_TOPIC, ALARM_TOPIC, host, port)
            client.loop_forever()
        except Exception as exc:  # noqa: BLE001
            log.exception("bridge error; retrying in %.1fs: %s", RECONNECT_DELAY_S, exc)
            time.sleep(RECONNECT_DELAY_S)
