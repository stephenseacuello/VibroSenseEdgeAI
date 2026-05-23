"""Runnable entrypoint: `python -m app.app`. See PROJECT_PLAN.md §13.

The MQTT → WebSocket bridge runs in a daemon thread alongside the Flask app so
tests that import `create_app()` directly never start it. Set
`VIBROSENSE_NO_BRIDGE=1` to disable the bridge explicitly.
"""

from __future__ import annotations

import os
import threading

from . import create_app
from .extensions import socketio
from .mqtt_bridge import run_bridge


def main() -> None:
    app = create_app()
    if not os.environ.get("VIBROSENSE_NO_BRIDGE"):
        threading.Thread(
            target=run_bridge,
            args=(socketio, app.config["MQTT_HOST"], app.config["MQTT_PORT"]),
            daemon=True,
            name="mqtt-bridge",
        ).start()
    socketio.run(
        app,
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=False,
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    main()
