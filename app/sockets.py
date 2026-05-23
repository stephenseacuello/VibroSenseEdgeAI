"""SocketIO event handlers.

The MQTT subscriber thread that emits `state` and `alarm` events lives in
`mqtt_bridge.py`. This module only registers connect/disconnect handlers so a
fresh client receives the latest persisted state + last alarm immediately on
connect.
"""

from __future__ import annotations

import logging

from flask_socketio import SocketIO, emit

from .db import get_db

log = logging.getLogger("app.sockets")


def register_handlers(socketio: SocketIO) -> None:
    @socketio.on("connect")
    def _on_connect():
        log.info("socket client connected")
        try:
            db = get_db()
            state_row = db.execute(
                "SELECT asset_id, ts_utc, state, confidence, seq "
                "FROM events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if state_row:
                emit("state", dict(state_row))

            alarm_row = db.execute(
                "SELECT asset_id, ts_utc, from_state, to_state, confidence "
                "FROM alarms ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if alarm_row:
                emit("alarm", dict(alarm_row))
        except Exception as exc:  # noqa: BLE001
            log.exception("on_connect: %s", exc)

    @socketio.on("disconnect")
    def _on_disconnect():
        log.info("socket client disconnected")
