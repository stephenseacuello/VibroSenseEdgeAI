"""Operator HMI — single-tile current state + last-alarm strip.

See PROJECT_PLAN.md §13.1.
"""

from __future__ import annotations

from flask import Blueprint, current_app, render_template, request

from ..db import get_db

bp = Blueprint("hmi", __name__)


@bp.route("/")
def operator():
    asset_id = request.args.get("asset_id", current_app.config["DEFAULT_ASSET_ID"])
    db = get_db()

    state_row = db.execute(
        "SELECT asset_id, ts_utc, state, confidence FROM events "
        "WHERE asset_id = ? ORDER BY id DESC LIMIT 1",
        (asset_id,),
    ).fetchone()

    alarm_row = db.execute(
        "SELECT ts_utc, from_state, to_state, confidence FROM alarms "
        "WHERE asset_id = ? ORDER BY id DESC LIMIT 1",
        (asset_id,),
    ).fetchone()

    return render_template(
        "hmi.html",
        state=dict(state_row) if state_row else None,
        alarm=dict(alarm_row) if alarm_row else None,
        asset_id=asset_id,
    )
