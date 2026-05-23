"""Error handlers. Returns JSON for `/api/*`; HTML otherwise.

The JSON shape matches the error envelope in PROJECT_PLAN.md §14.4 so clients
can rely on a single contract regardless of the failure source.
"""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request


def _is_api(path: str) -> bool:
    return path.startswith("/api/")


def init_app(app: Flask) -> None:
    @app.errorhandler(404)
    def _not_found(_e):
        if _is_api(request.path):
            return (
                jsonify({"error": {"code": "NOT_FOUND", "message": "no such route"}}),
                404,
            )
        return render_template("errors/404.html", path=request.path), 404

    @app.errorhandler(405)
    def _method_not_allowed(_e):
        if _is_api(request.path):
            return (
                jsonify(
                    {"error": {"code": "METHOD_NOT_ALLOWED", "message": "method not allowed"}}
                ),
                405,
            )
        return ("method not allowed", 405)

    @app.errorhandler(500)
    def _server_error(_e):
        app.logger.exception("unhandled error on %s", request.path)
        if _is_api(request.path):
            return (
                jsonify({"error": {"code": "INTERNAL", "message": "server error"}}),
                500,
            )
        return render_template("errors/500.html"), 500
