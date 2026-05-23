"""Engineering trend view — Chart.js over SQLite + live socket updates.

See PROJECT_PLAN.md §13.1.
"""

from __future__ import annotations

from flask import Blueprint, current_app, render_template, request

bp = Blueprint("trend", __name__)


@bp.route("/trend")
def trend():
    asset_id = request.args.get("asset_id", current_app.config["DEFAULT_ASSET_ID"])
    return render_template("trend.html", asset_id=asset_id)
