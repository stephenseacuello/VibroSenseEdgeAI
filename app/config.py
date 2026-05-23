"""Centralized config — env-driven with sensible lab defaults.

Loaded into Flask's `app.config` via `app.config.from_object()`, which reads
the uppercase class attributes.
"""

from __future__ import annotations

import os


class Config:
    """Default config. Override per-instance via `Config.from_env()` or by
    constructing a custom subclass in tests."""

    DB_PATH: str = "gateway/db/vibrosense.sqlite"

    MQTT_HOST: str = "localhost"
    MQTT_PORT: int = 1883

    HOST: str = "0.0.0.0"
    PORT: int = 5000

    LOG_LEVEL: str = "INFO"
    CORS_ALLOWED_ORIGINS: str = "*"

    APP_VERSION: str = "0.2.0"
    FIRMWARE_SHA: str = "unknown"

    DEFAULT_ASSET_ID: str = "fan-01"
    HISTORY_MAX_ROWS: int = 10000

    @classmethod
    def from_env(cls) -> "Config":
        c = cls()
        c.DB_PATH = os.environ.get("VIBROSENSE_DB", cls.DB_PATH)
        c.MQTT_HOST = os.environ.get("MQTT_HOST", cls.MQTT_HOST)
        c.MQTT_PORT = int(os.environ.get("MQTT_PORT", cls.MQTT_PORT))
        c.HOST = os.environ.get("HOST", cls.HOST)
        c.PORT = int(os.environ.get("PORT", cls.PORT))
        c.LOG_LEVEL = os.environ.get("LOG_LEVEL", cls.LOG_LEVEL).upper()
        c.CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", cls.CORS_ALLOWED_ORIGINS)
        c.FIRMWARE_SHA = os.environ.get("FIRMWARE_SHA", cls.FIRMWARE_SHA)
        c.DEFAULT_ASSET_ID = os.environ.get("VIBROSENSE_ASSET_ID", cls.DEFAULT_ASSET_ID)
        c.HISTORY_MAX_ROWS = int(os.environ.get("HISTORY_MAX_ROWS", cls.HISTORY_MAX_ROWS))
        return c
