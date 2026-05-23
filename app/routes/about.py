"""GET /about — build info and DB stats."""

from __future__ import annotations

from flask import Blueprint, current_app, render_template

from ..db import get_db

bp = Blueprint("about", __name__)


@bp.route("/about")
def about():
    db = get_db()
    row = db.execute(
        "SELECT COUNT(*) AS n, MAX(ts_utc) AS last_ts FROM events"
    ).fetchone()
    return render_template(
        "about.html",
        firmware_sha=current_app.config["FIRMWARE_SHA"],
        app_version=current_app.config["APP_VERSION"],
        event_count=row["n"] if row else 0,
        last_event_ts=row["last_ts"] if row else None,
        db_path=current_app.config["DB_PATH"],
    )
