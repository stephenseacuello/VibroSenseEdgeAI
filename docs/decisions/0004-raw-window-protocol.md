# ADR-0004 — Raw window binary protocol over BLE

**Date:** 2026-05-22
**Status:** Proposed — finalize alongside firmware implementation (Wk 3)

## Context

The Nano needs to stream complete IMU windows to the Pi during data capture so the team can build a labeled dataset. A 256-sample window of `(ax, ay, az)` is far larger than a single BLE notify (~244 byte ATT payload after MTU negotiation), so the firmware must chunk each window and the Python side must reassemble.

JSON would be wasteful at this size. A fixed binary frame is denser, easier to parse, and makes alignment errors obvious.

## Decision

A new BLE characteristic on the VibroSense PDM service:

| Name        | UUID                                      | Properties |
|-------------|-------------------------------------------|------------|
| `raw_window`| `12345678-1234-5678-1234-56789abcdef4`    | notify     |

**Frame layout (little-endian, packed):**

```
offset  size   field             type     meaning
0       4      window_seq        uint32   monotonic per device session
4       1      chunk_idx         uint8    0 .. total_chunks - 1
5       1      total_chunks      uint8
6       2      samples_in_chunk  uint16
8       N*6    interleaved samples       int16 triples: ax, ay, az, ax, ay, az, ...
```

`N = samples_in_chunk`. Each sample is `int16(round(g_value * 1000))` so a reading of 1.0 g becomes 1000, ±4 g range becomes ±4000 — comfortable inside int16 ±32768.

**Chunking parameters:**

| Parameter             | Value |
|---|---|
| Samples per full chunk| 32    |
| Bytes per full chunk  | 8 + 32 × 6 = **200** |
| Chunks per 256-window | 8     |
| Last chunk            | full (256 / 32 = 8 evenly) |

For window sizes that are not multiples of 32, the final chunk has `samples_in_chunk < 32`.

**Reassembly rules (Python side):**

1. Buffer chunks per `window_seq`.
2. Emit the window once all `total_chunks` arrive in order.
3. If `total_chunks` ever changes mid-window, reset the buffer for that `window_seq`.
4. Drop incomplete windows older than 5 s to prevent unbounded memory growth.

## Consequences

- **Density.** 256 × 3 × 2 = 1536 payload bytes + 64 bytes of headers = 1600 bytes per window. JSON would be ~5× larger.
- **Loss tolerance.** Any dropped chunk silently drops the whole window, which is fine for training data (we want clean inputs, not interpolated ones).
- **Out-of-order safe.** `window_seq` + `chunk_idx` lets the receiver assemble in any order.
- **Firmware-side cost.** 200-byte BLE notify is well within ATT_MTU 247. No fragmentation needed at the BLE layer.
- **Coupled change.** Bumping the protocol (e.g., adding gyro) requires a new characteristic UUID OR a `protocol_ver` field in the header. We'll choose the latter when we need it.

## Implementation pointers

- Python encoder/decoder: [`ml/src/raw_window.py`](../../ml/src/raw_window.py).
- Round-trip tests: [`ml/tests/test_raw_window.py`](../../ml/tests/test_raw_window.py).
- Firmware producer: `BLEService::publishRawWindow` in [`firmware/nano33/src/ble_service.cpp`](../../firmware/nano33/src/ble_service.cpp).
- Receiver in capture tool: [`ml/src/capture.py`](../../ml/src/capture.py).
