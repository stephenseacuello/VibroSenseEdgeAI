"""SQLite connection helper bound to Flask's per-request `g`.

Connections are opened lazily on first `get_db()` and closed at the end of the
request by the teardown hook registered in `init_app()`.
"""

from __future__ import annotations

import sqlite3

from flask import Flask, current_app, g


def init_app(app: Flask) -> None:
    """Register the per-request teardown so connections are always released."""
    app.teardown_appcontext(_close_db)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DB_PATH"])
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


def _close_db(_exc: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()
