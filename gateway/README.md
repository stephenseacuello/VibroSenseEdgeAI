# `gateway/` — Raspberry Pi supervisory layer

The ISA-95 Level 2 tier. Subscribes to the Nano over BLE, republishes via MQTT, runs Node-RED for orchestration, persists everything to SQLite, and exposes the data to the Flask app.

See [PROJECT_PLAN.md §12](../PROJECT_PLAN.md#12-gateway--supervisory-plan-raspberry-pi).

## Layout

```
gateway/
├── ble_central.py        # bleak → MQTT, validates StateV1, tracks ATP-03 seq stats
├── mqtt_to_sqlite.py     # MQTT subscriber → events / alarms tables
├── nodered/flows.json    # state-change detector + rolling availability
├── mosquitto/mosquitto.conf
├── db/schema.sql         # events + alarms tables (single source of truth)
├── systemd/              # vibrosense-{ble,mqtt2db,app}.service
└── tests/                # test_ble_central + test_mqtt_to_sqlite
```

## Service topology

```
[Nano] ──BLE notify──▶ [ble_central]
                            │ pdm/{asset_id}/state
                            ▼
                     [Mosquitto broker]
                            │
                  ┌─────────┴────────────┐
                  │                      │
                  ▼                      ▼
            [Node-RED flows]       [mqtt_to_sqlite]
              │                          │
   pdm/{asset_id}/alarm                  ▼
   pdm/{asset_id}/oee              [SQLite events/alarms]
                  │                          ▲
                  └──────────────────────────┘
                                             │
                                             ▼
                                        [Flask app]
```

## Topics

| Topic                        | Producer       | Consumer(s)               | QoS | Retained |
|------------------------------|----------------|---------------------------|-----|----------|
| `pdm/{asset_id}/state`       | `ble_central`  | Node-RED, mqtt_to_sqlite, Flask bridge | 0   | no       |
| `pdm/{asset_id}/alarm`       | Node-RED       | mqtt_to_sqlite, Flask bridge           | 1   | yes      |
| `pdm/{asset_id}/oee`         | Node-RED       | (future: Flask polls / displays)        | 0   | yes      |
| `pdm/{asset_id}/features`    | (optional)     | debug                                    | 0   | no       |
| `pdm/{asset_id}/raw_window`  | (optional)     | debug; data path is BLE direct          | 0   | no       |

## SQLite schema

See [`db/schema.sql`](db/schema.sql). Two append-only tables:

- **events** — one row per inference window: `asset_id, ts_utc, state, confidence, seq, schema_ver`
- **alarms** — one row per state transition emitted by Node-RED: `asset_id, ts_utc, from_state, to_state, confidence, schema_ver`

`mqtt_to_sqlite.ensure_schema()` is idempotent — safe to run on every boot.

## ATP-03: BLE link reliability

`ble_central.SeqStats` accounts for sequence-number continuity per asset. Every minute (and on every gap) it emits a log line:

```
2026-07-15 14:32:00 INFO ble_central ATP-03 metric: 1830/1832 notifies received (loss=0.109%)
```

Acceptance per [ATP-03](../PROJECT_PLAN.md#atp-03--ble-link-reliability): ≤ 0.5% missed sequence numbers; no disconnect > 5 s.

Device reboots (seq jumping back) are detected and treated as resets rather than as enormous gaps.

## Bring up a fresh Pi 4

```bash
./scripts/bootstrap_pi.sh
```

Idempotent: installs apt deps, configures Mosquitto, installs Node-RED via the official Pi installer, sets up the venv, drops in the three systemd units, and enables them.

Verify with:

```bash
systemctl status vibrosense-{ble,mqtt2db,app}
journalctl -u vibrosense-ble -f
mosquitto_sub -t 'pdm/+/#' -v
```

## Run pieces individually (development)

```bash
# from project root, after `make setup`
mosquitto -c gateway/mosquitto/mosquitto.conf -d
python -m gateway.mqtt_to_sqlite              # MQTT → SQLite
python -m gateway.ble_central                 # BLE → MQTT (requires real Nano in range)
python -m app.app                             # Flask UI
```

The `mock_ble_producer.py` (in `scripts/`) replaces `ble_central` for hardware-free demos:

```bash
python scripts/mock_ble_producer.py
```

## Node-RED flows

Import [`nodered/flows.json`](nodered/flows.json) once via the Node-RED UI (`http://<pi>:1880`) and click **Deploy**. Two function nodes do all the work:

1. **state-change detector** — drops messages with `confidence < 0.6` (ADR-0003), tracks last state per asset, emits an `AlarmV1` to `pdm/{asset_id}/alarm` on every real transition.
2. **rolling availability** — 60-second rolling fraction of `HEALTHY` samples, emitted to `pdm/{asset_id}/oee` (retained).

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `MQTT_HOST` | `localhost` | broker address used by `ble_central` + `mqtt_to_sqlite` |
| `MQTT_PORT` | `1883` | broker port |
| `VIBROSENSE_DB` | `gateway/db/vibrosense.sqlite` | SQLite path the persister writes to |
| `VIBROSENSE_ASSET_ID` | `fan-01` | asset_id stamped on every published `state` message |
| `VIBROSENSE_DEVICE_NAME` | `VibroSense-Nano` | BLE local name the central scans for |

Override at run time, e.g.:

```bash
VIBROSENSE_ASSET_ID=fan-02 python -m gateway.ble_central
```

## Testing

```bash
pytest -q gateway/tests
```

Covers: state insertion, alarm insertion (including NULL `from`), schema idempotency, ble_central message validation, and SeqStats gap accounting + device-reboot detection. Doesn't require Mosquitto or bleak — the handlers are exercised directly.
