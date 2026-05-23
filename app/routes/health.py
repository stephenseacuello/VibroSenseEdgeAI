"""Health probes — used by systemd / external monitoring.

- `/healthz` — liveness; always 200 if the process is up.
- `/readyz`  — readiness; 200 only if SQLite is reachable.
"""

from __future__ import annotations

import sqlite3

from flask import Blueprint, current_app, jsonify

bp = Blueprint("health", __name__)


@bp.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "version": current_app.config["APP_VERSION"]})


@bp.route("/readyz")
def readyz():
    db_path = current_app.config["DB_PATH"]
    try:
        conn = sqlite3.connect(db_path, timeout=1.0)
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"status": "not-ready", "error": str(exc)}), 503
    return jsonify({"status": "ready", "db_path": db_path})
