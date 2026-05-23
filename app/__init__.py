"""Flask application factory for VibroSenseEdgeAI.

See PROJECT_PLAN.md §13. The factory is the single composition root:

    from app import create_app
    app = create_app()
"""

from __future__ import annotations

import logging

from flask import Flask

from . import db, errors, sockets
from .config import Config
from .extensions import socketio
from .routes import register_blueprints

__all__ = ["create_app"]


def create_app(config: Config | None = None) -> Flask:
    cfg = config or Config.from_env()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(cfg)

    logging.basicConfig(
        level=getattr(logging, app.config["LOG_LEVEL"], logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    db.init_app(app)
    register_blueprints(app)
    errors.init_app(app)

    socketio.init_app(
        app,
        cors_allowed_origins=app.config["CORS_ALLOWED_ORIGINS"],
        async_mode="threading",
    )
    sockets.register_handlers(socketio)

    app.logger.info("VibroSense app ready (db=%s)", app.config["DB_PATH"])
    return app
