-- VibroSense Edge AI SQLite schema.
-- The events table is the source of truth for per-window classifications.
-- The alarms table records state transitions emitted by Node-RED.

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id    TEXT    NOT NULL,
    ts_utc      TEXT    NOT NULL,            -- ISO 8601 UTC, ms resolution
    state       TEXT    NOT NULL,            -- HEALTHY|IMBALANCE|LOOSENESS|BEARING_FAULT
    confidence  REAL    NOT NULL,            -- 0..1
    seq         INTEGER NOT NULL,            -- monotonic per device session
    schema_ver  INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS ix_events_asset_ts ON events (asset_id, ts_utc);

CREATE TABLE IF NOT EXISTS alarms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id    TEXT    NOT NULL,
    ts_utc      TEXT    NOT NULL,
    from_state  TEXT,                        -- NULL on first transition since boot
    to_state    TEXT    NOT NULL,
    confidence  REAL    NOT NULL,
    schema_ver  INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS ix_alarms_asset_ts ON alarms (asset_id, ts_utc);
