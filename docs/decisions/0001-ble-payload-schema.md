# ADR-0001 — BLE payload schema v1 + UUID freeze

**Date:** 2026-05-22 (proposed) → 2026-05-23 (locked)
**Status:** Accepted

## Context
The Nano publishes per-window classifications to the Pi gateway over a BLE GATT
notify characteristic. A versioned schema lets the downstream layers (gateway,
MQTT topics, Flask app) evolve independently of the firmware. We need stable
service / characteristic UUIDs and a payload contract we can validate at every
boundary.

## Decision

**Service UUID (frozen):** `7e5c0001-d9b7-4f12-8a6b-0a0b0c0d0e0f`

Service-wide base; characteristic UUIDs increment the last byte. All five form
a consistent family for grep / debug-tool clarity (nRF Connect, Bluetility, etc.).

**Characteristics (frozen):**

| Name        | UUID                                          | Properties      | Format |
|-------------|-----------------------------------------------|-----------------|--------|
| `state`     | `7e5c0001-d9b7-4f12-8a6b-0a0b0c0d0e10`        | read, notify    | UTF-8 JSON, schema v1 below |
| `mode`      | `7e5c0001-d9b7-4f12-8a6b-0a0b0c0d0e11`        | read, write     | uint8: 0 = INFER, 1 = CAPTURE |
| `version`   | `7e5c0001-d9b7-4f12-8a6b-0a0b0c0d0e12`        | read            | UTF-8 string: `firmware_sha + schema_ver` |
| `raw_window`| `7e5c0001-d9b7-4f12-8a6b-0a0b0c0d0e13`        | notify          | binary chunks per [ADR-0004](0004-raw-window-protocol.md) |

The UUIDs are mirrored in three places and **must move in lockstep** if ever changed:

- [`firmware/nano33/src/ble_service.cpp`](../../firmware/nano33/src/ble_service.cpp) — `SERVICE_UUID`, `STATE_UUID`, `MODE_UUID`, `VERSION_UUID`, `RAW_WINDOW_UUID`
- [`ml/src/capture.py`](../../ml/src/capture.py) — `MODE_UUID`, `RAW_WINDOW_UUID`
- [`gateway/ble_central.py`](../../gateway/ble_central.py) — `STATE_UUID`

**`state` payload (schema v1):**

```json
{"schema_ver":1,"ts_ms":<uint32>,"seq":<uint32>,"state":"<label>","confidence":<float>}
```

- `state` ∈ `{HEALTHY, IMBALANCE, LOOSENESS, BEARING_FAULT}`
- `confidence` ∈ `[0.0, 1.0]`
- Payload length ≤ 96 bytes
- Field order is stable (validators tolerate other orderings, but firmware emits in this order for ease of grep / diff)

Validated on the Python side by [`ml.src.schema.StateV1`](../../ml/src/schema.py).

## Consequences
- Trivial to inspect with nRF Connect or `bleak` during bring-up; easy to dump on the gateway.
- Costs a few bytes vs a binary layout — acceptable at ≤ 1 Hz over BLE.
- Bumping `schema_ver` is a deliberate, lockstep change across firmware + gateway + tests. See [CONTRIBUTING.md](../../CONTRIBUTING.md#when-you-change-a-payload-schema).
- The binary `raw_window` characteristic (ADR-0004) lives on the same service but uses an independent schema; bumping one does not require bumping the other.
- UUIDs are a 128-bit random space generated 2026-05-23; collision probability with other lab BLE devices is effectively zero.
