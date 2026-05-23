# `app/` — Flask operations UI

The MES tier of VibroSenseEdgeAI (ISA-95 Level 3). Serves the operator HMI, the engineering trend view, a REST API, and a WebSocket live-push channel. Reads from the SQLite database written by [`gateway/mqtt_to_sqlite.py`](../gateway/mqtt_to_sqlite.py); subscribes to Mosquitto via the in-process MQTT bridge.

See [PROJECT_PLAN.md §13](../PROJECT_PLAN.md#13-flask-application-plan) for the design.

## Layout

```
app/
├── __init__.py       # create_app() factory — composition root
├── app.py            # `python -m app.app` entrypoint
├── config.py         # Config class (env-driven defaults)
├── extensions.py     # SocketIO singleton
├── db.py             # SQLite connection helper + teardown registration
├── mqtt_bridge.py    # MQTT subscriber → SocketIO emit (with schema validation)
├── sockets.py        # SocketIO connect/disconnect handlers
├── errors.py         # 404/405/500 (JSON for /api/*, HTML otherwise)
├── routes/
│   ├── hmi.py        # GET /
│   ├── trend.py      # GET /trend
│   ├── about.py      # GET /about
│   ├── health.py     # GET /healthz, /readyz
│   └── api.py        # GET /api/v1/{state,history,oee,assets}
├── templates/
├── static/
└── tests/
```

## Routes

| Route                       | Method | Returns      | Description |
|---|---|---|---|
| `/`                         | GET    | HTML         | Operator HMI single-tile current state |
| `/trend`                    | GET    | HTML         | Chart.js trend view, last 5 min + live |
| `/about`                    | GET    | HTML         | Build info + DB stats |
| `/healthz`                  | GET    | JSON         | Liveness — always 200 if process is up |
| `/readyz`                   | GET    | JSON         | Readiness — 200 if SQLite is reachable, else 503 |
| `/api/v1/state`             | GET    | JSON         | Latest classification for an asset |
| `/api/v1/history`           | GET    | JSON array   | Time-series of classifications in a range |
| `/api/v1/oee`               | GET    | JSON         | Availability KPI over a window |
| `/api/v1/assets`            | GET    | JSON array   | Known asset_ids with counts and last_ts |
| `/socket.io/`               | WS     | `state` event| Live push of every new classification |

### Query parameters

| Endpoint | Param | Type | Default | Notes |
|---|---|---|---|---|
| `/`, `/trend`, `/api/v1/*` | `asset_id` | string | `fan-01` (or `VIBROSENSE_ASSET_ID`) | which asset to show |
| `/api/v1/history` | `from`, `to` | ISO 8601 | — required — | rejected with `BAD_RANGE` if missing / malformed / inverted |
| `/api/v1/oee` | `window` | seconds (int > 0) | 300 | rejected with `BAD_PARAM` if non-positive or non-integer |

### Error envelope

All `/api/*` errors return:

```json
{ "error": { "code": "BAD_RANGE", "message": "to < from", "hint": "use ISO 8601" } }
```

See [PROJECT_PLAN.md §14.4](../PROJECT_PLAN.md#14-interface-contracts).

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `VIBROSENSE_DB` | `gateway/db/vibrosense.sqlite` | SQLite path |
| `MQTT_HOST` | `localhost` | broker address |
| `MQTT_PORT` | `1883` | broker port |
| `HOST` | `0.0.0.0` | bind address |
| `PORT` | `5000` | bind port |
| `LOG_LEVEL` | `INFO` | Python log level name |
| `CORS_ALLOWED_ORIGINS` | `*` | SocketIO CORS |
| `FIRMWARE_SHA` | `unknown` | shown on /about |
| `VIBROSENSE_ASSET_ID` | `fan-01` | default asset when query param omitted |
| `HISTORY_MAX_ROWS` | `10000` | upper bound on `/api/v1/history` |
| `VIBROSENSE_NO_BRIDGE` | unset | set to `1` to skip the MQTT bridge thread (used in tests) |

## Run

This repo is hardware-targeted — `make demo` expects the Nano to be flashed and in BLE range. For development without hardware (mock BLE producer, synthetic data), use the sister repo [`../VibroSenseEdgeAI-demo/`](../../VibroSenseEdgeAI-demo/).

```bash
brew install mosquitto       # macOS; on the Pi, the bootstrap script handles this
make demo                    # mosquitto + persistence + BLE central + Flask
open http://localhost:5000
```

The app reads from `gateway/db/vibrosense.sqlite` which is populated by `gateway/mqtt_to_sqlite.py`. The MQTT bridge inside the Flask process subscribes to `pdm/+/state` and `pdm/+/alarm` and fans out as SocketIO events — the database write and the WebSocket push happen on independent paths.

## Test

```bash
make test                    # full repo
pytest -q app/tests          # app only
pytest -q app/tests/test_api.py::test_oee_returns_availability   # a single case
```

`app/tests/conftest.py` builds a fresh SQLite, seeds 4 events (3 for `fan-01`, 1 for `fan-02`), and yields a Flask test client. The MQTT bridge thread is suppressed in tests via `VIBROSENSE_NO_BRIDGE=1`.

Coverage:

| File | What it covers |
|---|---|
| `test_api.py`     | All `/api/v1` endpoints, validation, the operator HMI HTML render, empty-DB behavior |
| `test_health.py`  | `/healthz` always-200, `/readyz` happy path + DB unreachable 503 |
| `test_errors.py`  | 404 JSON vs HTML, 405 on POST to GET-only |
| `test_bridge.py`  | `validate_payload` accepts conforming v1 messages and drops bad class / out-of-range confidence / non-JSON / missing field |

## Design notes

- **Factory pattern.** `create_app()` is the single composition root. Tests build their own app with a tmp SQLite; production calls the same factory via `app.app:main`. No module-level Flask app.
- **Bridge runs only in the entrypoint.** `create_app()` never starts the MQTT thread, so importing the app for tests is side-effect-free.
- **Schema validation at every boundary.** `gateway/ble_central.py` validates before publishing; `app/mqtt_bridge.py` re-validates before fanning out to the UI. Defense in depth that satisfies ATP-04 even if a future publisher misbehaves.
- **Latest-state on connect.** When a fresh client connects, the SocketIO handler queries the DB for the most recent event and pushes it immediately — the operator tile never shows "—" if any event is on disk.
- **WebSocket = source of truth for the UI; DB = source of truth for KPIs.** The trend page seeds with `/api/v1/history` and then live-extends via the socket; the operator tile is purely socket-driven after the initial render. Both pages tolerate the socket being temporarily disconnected (the connection indicator in the header turns red).

## When you change the payload schema

1. Add an ADR under [`../docs/decisions/`](../docs/decisions/).
2. Bump `schema_ver` in [`ml/src/schema.py`](../ml/src/schema.py).
3. Update the firmware payload in lockstep ([`firmware/nano33/src/ble_service.cpp`](../firmware/nano33/src/ble_service.cpp)).
4. Verify [`tests/integration/test_schema.py`](../tests/integration/test_schema.py) still passes and update if needed.
