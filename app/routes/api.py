"""REST API.

See PROJECT_PLAN.md §13.2 (endpoints) and §14.4 (error envelope).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from ..db import get_db

bp = Blueprint("api", __name__)

ISO_HINT = "ISO 8601 UTC, e.g. 2026-07-15T14:30:00.000Z"


def _err(code: str, message: str, hint: str | None = None, http: int = 400):
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if hint:
        body["error"]["hint"] = hint
    return jsonify(body), http


def _is_iso8601(s: str) -> bool:
    try:
        datetime.fromisoformat(s.replace("Z", "+00:00"))
        return True
    except (TypeError, ValueError):
        return False


@bp.route("/state")
def state():
    asset_id = request.args.get("asset_id", current_app.config["DEFAULT_ASSET_ID"])
    db = get_db()
    row = db.execute(
        "SELECT asset_id, ts_utc, state, confidence, seq "
        "FROM events WHERE asset_id = ? ORDER BY id DESC LIMIT 1",
        (asset_id,),
    ).fetchone()
    if row is None:
        return _err("NO_DATA", "no events for asset", http=404)
    return jsonify(dict(row))


@bp.route("/history")
def history():
    asset_id = request.args.get("asset_id", current_app.config["DEFAULT_ASSET_ID"])
    frm = request.args.get("from")
    to = request.args.get("to")
    if not (frm and to):
        return _err("BAD_RANGE", "missing from/to", hint=ISO_HINT)
    if not (_is_iso8601(frm) and _is_iso8601(to)):
        return _err("BAD_RANGE", "from/to must be ISO 8601", hint=ISO_HINT)
    if to < frm:
        return _err("BAD_RANGE", "to < from", hint=ISO_HINT)

    limit = current_app.config["HISTORY_MAX_ROWS"]
    db = get_db()
    rows = db.execute(
        "SELECT ts_utc, state, confidence FROM events "
        "WHERE asset_id = ? AND ts_utc BETWEEN ? AND ? "
        "ORDER BY ts_utc ASC LIMIT ?",
        (asset_id, frm, to, limit),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/oee")
def oee():
    asset_id = request.args.get("asset_id", current_app.config["DEFAULT_ASSET_ID"])
    try:
        window_s = int(request.args.get("window", "300"))
    except ValueError:
        return _err("BAD_PARAM", "window must be an integer in seconds")
    if window_s <= 0:
        return _err("BAD_PARAM", "window must be positive")

    db = get_db()
    rows = db.execute(
        "SELECT state FROM events "
        "WHERE asset_id = ? AND ts_utc >= datetime('now', ?)",
        (asset_id, f"-{window_s} seconds"),
    ).fetchall()
    if not rows:
        return jsonify(
            {
                "asset_id": asset_id,
                "window_s": window_s,
                "availability": None,
                "samples": 0,
            }
        )
    healthy = sum(1 for r in rows if r["state"] == "HEALTHY")
    return jsonify(
        {
            "asset_id": asset_id,
            "window_s": window_s,
            "availability": healthy / len(rows),
            "samples": len(rows),
        }
    )


@bp.route("/assets")
def assets():
    db = get_db()
    rows = db.execute(
        "SELECT asset_id, COUNT(*) AS events, MAX(ts_utc) AS last_ts "
        "FROM events GROUP BY asset_id ORDER BY asset_id"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/alarms")
def alarms():
    asset_id = request.args.get("asset_id", current_app.config["DEFAULT_ASSET_ID"])
    try:
        limit = int(request.args.get("limit", "50"))
    except ValueError:
        return _err("BAD_PARAM", "limit must be an integer")
    if limit <= 0 or limit > 1000:
        return _err("BAD_PARAM", "limit must be in 1..1000")

    db = get_db()
    rows = db.execute(
        "SELECT ts_utc, from_state, to_state, confidence FROM alarms "
        "WHERE asset_id = ? ORDER BY id DESC LIMIT ?",
        (asset_id, limit),
    ).fetchall()
    return jsonify([dict(r) for r in rows])
