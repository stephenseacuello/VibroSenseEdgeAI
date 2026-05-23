"""Blueprint registration. The factory calls `register_blueprints(app)`."""

from __future__ import annotations

from flask import Flask

from .about import bp as about_bp
from .api import bp as api_bp
from .health import bp as health_bp
from .hmi import bp as hmi_bp
from .trend import bp as trend_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(hmi_bp)
    app.register_blueprint(trend_bp)
    app.register_blueprint(about_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
