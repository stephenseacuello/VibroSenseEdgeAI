# Test Plan v1 — VibroSenseEdgeAI

**Owner:** Stephen Eacuello (PM)
**Last updated:** 2026-05-23
**Status:** Draft v1 — to be reviewed at the Wk 2 status meeting and finalized for the Test Plan deliverable.

This document operationalizes [PROJECT_PLAN.md §15](../../PROJECT_PLAN.md#15-test--verification--acceptance-test-procedures) into a runnable test plan with traceability to the SMART acceptance criteria in §2.2 and the Course Learning Objectives (CLOs) in §23.

## 1. Scope

In scope: every layer of the VibroSense Edge AI stack — firmware, ML pipeline, BLE transport, Pi gateway, Flask app. Covers unit, integration, system, and acceptance levels.

Out of scope: long-term reliability soak (> 30 min), thermal stress, EMC, formal safety review. The asset is consumer-grade and operated under bench conditions.

## 2. Test environments

| Environment | Purpose | Where |
|---|---|---|
| Dev box (laptop, macOS/Linux) | Unit + integration tests; mock loopback | Each team member |
| GitHub Actions CI | Lint + unit + ML pipeline + firmware compile sanity | `.github/workflows/ci.yml` |
| Hardware bench | All ATPs that require a real Nano | Stephen's lab bench |
| Pi gateway | ATP-06/07/08; demo recording | Lab-owned Pi 4 |

## 3. Traceability matrix

Every acceptance criterion (AC) maps to ≥ 1 ATP. Every ATP maps to ≥ 1 deliverable.

| AC | Requirement | ATP | Test environment | Captured in |
|---|---|---|---|---|
| AC-1 | Test-set accuracy ≥ 90% | ATP-05 | Dev box / Pi | Eval report under `ml/experiments/` |
| AC-2 | On-device inference latency p95 < 250 ms | ATP-01 | Hardware bench (serial) | `scripts/atp01_timing.py` output |
| AC-3 | Quantized model fits Nano flash budget with ≥ 30% headroom | ATP-02 | Dev box (`make verify-firmware`) | `arduino-cli compile` size output |
| AC-4 | Live demo: each fault ≥ 3 of 4 trials | ATP-09 | Hardware bench | Demo trial log (this doc, §6) |
| AC-5 | Flask tile updates within 1 s of state change | ATP-07 | Pi + browser | Manual timer; recorded in CDR notes |
| AC-6 | Every classification persisted | ATP-08 | Pi | MQTT vs SQLite count |
| AC-7 | `/api/v1/oee` returns sensible availability | ATP-10 | Pi | API response captured in test results |
| AC-8 | Source code shipped as tagged GitHub release | (manual) | GitHub | `v1.0-Final` tag |

## 4. Test levels and tooling

### 4.1 Unit
`pytest` against `ml/tests`, `app/tests`, `gateway/tests`. Covers feature math, payload-schema validation, error envelopes, raw_window protocol round-trip, BLE sequence-gap accounting, SQLite persistence path, MQTT bridge schema enforcement.

```bash
make test
```

### 4.2 Integration
`tests/integration/`. Cross-layer:
- `test_schema.py` — pydantic StateV1 / AlarmV1 conformance
- `test_capture_pipeline.py` — synth windows → encode → assemble → parquet → RF (validates ADR-0004 wire-format agreement between Python encoder and assembler)

### 4.3 System
End-to-end demo on hardware. Driven by [`docs/hardware_bringup.md`](../hardware_bringup.md). Includes manual sanity checks on every layer.

### 4.4 Acceptance
The ATPs below. Each is reproducible and gated.

## 5. Acceptance Test Procedures

These mirror [PROJECT_PLAN.md §15.2](../../PROJECT_PLAN.md#152-atps) but include the exact commands, expected output, and pass/fail recording for the Test Plan deliverable.

### ATP-01 — On-device inference latency (AC-2)

**Pre-conditions:**
- Nano flashed with a real `model.h` (not the placeholder)
- Firmware built with `-DDEBUG_TIMING=1`
- Nano connected via USB

**Procedure:**
```bash
arduino-cli compile --fqbn arduino:mbed_nano:nano33ble firmware/nano33 \
    --build-property "build.extra_flags=-DDEBUG_TIMING=1"
PORT=/dev/cu.usbmodemXXXX make flash
python scripts/atp01_timing.py --port $PORT --duration-s 60
```

**Acceptance:** `p95 < 250 ms` and `p99 < 350 ms`.
**Owner:** Firmware lead.

### ATP-02 — Nano memory footprint (AC-3)

**Pre-conditions:** Final `model.h` integrated.

**Procedure:**
```bash
make verify-firmware
```

**Acceptance:** Flash usage ≤ 70%; SRAM usage ≤ 70%. Record exact percentages in the v0.5 tag notes.
**Owner:** Firmware lead.

### ATP-03 — BLE link reliability

**Pre-conditions:** Pi within 3 m line-of-sight of the Nano; full stack up.

**Procedure:** Run for 30 min; observe `ble_central` log. The gateway emits an `ATP-03 metric` line every 60 s with cumulative `received` / `missed` counts (see [`gateway/ble_central.py`](../../gateway/ble_central.py) `SeqStats`).

**Acceptance:** loss_rate ≤ 0.5%; no disconnect > 5 s. Disconnects produce `BLE disconnected; will reconnect` in the log.

**Owner:** Gateway lead.

### ATP-04 — Schema conformance

**Procedure:**
```bash
pytest -q tests/integration/test_schema.py app/tests/test_bridge.py
```

**Acceptance:** 100% pass.
**Owner:** Gateway lead.

### ATP-05 — Test-set accuracy (AC-1)

**Pre-conditions:** Frozen dataset under `ml/data/raw/` and a trained model.

**Procedure:**
```bash
make merge-sessions
make train    ARGS="ml/data/processed/dataset.parquet --epochs 60"
make eval     ARGS="ml/artifacts/cnn.keras ml/data/processed/dataset.parquet"
```

The eval command exits 0 if the ATP-05 gate passes, non-zero otherwise.

**Acceptance:** Overall accuracy ≥ 90%; per-class recall ≥ 80%.
**Owner:** ML lead.

### ATP-06 — Gateway resilience

**Pre-conditions:** Full stack up on the Pi via systemd.

**Procedure:**
```bash
ssh pi@<pi-host>
sudo systemctl kill -s SIGKILL vibrosense-ble
# wait 15 s, confirm next event appears in SQLite
sudo journalctl -u vibrosense-ble -n 20
sqlite3 gateway/db/vibrosense.sqlite "SELECT MAX(ts_utc) FROM events"
```

**Acceptance:** Service back online and writing events within 15 s; no DB corruption.
**Owner:** Gateway lead.

### ATP-07 — HMI freshness (AC-5)

**Procedure:** Inject a known fault transition (per §9.2 SOPs). Time from injection to operator-tile color change.

**Acceptance:** Update visible within 1 s p95 on a local LAN browser.
**Owner:** App lead.

### ATP-08 — Persistence soak (AC-6)

**Procedure:** Run the full stack 30 min. Compare MQTT-side `state` message count to `events` row count:
```bash
mosquitto_sub -t 'pdm/+/state' -C 1800 -q 0 | wc -l
sqlite3 gateway/db/vibrosense.sqlite "SELECT COUNT(*) FROM events WHERE ts_utc >= datetime('now', '-30 minutes')"
```

**Acceptance:** Zero unaccounted drops (the two counts match).
**Owner:** Gateway lead.

### ATP-09 — Live fault recognition (AC-4)

**Procedure:** For each of `IMBALANCE`, `LOOSENESS`, `BEARING_FAULT`:
1. Reset to `HEALTHY` and wait for the operator tile to confirm green.
2. Inject the fault per the §9.2 SOP (4 independent trials per class).
3. Record the predicted class within 5 s of injection.

**Acceptance:** ≥ 3 of 4 correct per fault class. Trial log:

| Class | Trial 1 | Trial 2 | Trial 3 | Trial 4 | Pass? |
|---|---|---|---|---|---|
| IMBALANCE      | ☐ | ☐ | ☐ | ☐ | |
| LOOSENESS      | ☐ | ☐ | ☐ | ☐ | |
| BEARING_FAULT  | ☐ | ☐ | ☐ | ☐ | |

**Owner:** PM oversees; each team member operates one fault.

### ATP-10 — OEE endpoint sanity (AC-7)

**Procedure:**
```bash
# scripted sequence: 60 s HEALTHY, 30 s IMBALANCE, 60 s HEALTHY
curl -s 'http://<pi>:5000/api/v1/oee?window=180' | jq
```

**Acceptance:** `availability` within ±5% of expected (≈ 0.80).
**Owner:** App lead.

### ATP-11 — Demo dry-run

**Procedure:** Execute the demo script in [PROJECT_PLAN.md §16](../../PROJECT_PLAN.md#16-final-demo-script-week-10) end-to-end without ad-hoc fixes.

**Acceptance:** All steps complete in ≤ 7 minutes.
**Owner:** PM.

## 6. Demo trial log (template for ATP-09)

To be filled in live at the Wk 10 recording and again at the dress rehearsal (Wk 9).

| Date | Operator | Class | Trial | Predicted | Confidence | Notes |
|---|---|---|---|---|---|---|
| | | | | | | |

## 7. Schedule

| Week | What runs |
|---|---|
| 2 | ATP-04 (schema); test plan finalized |
| 3 | Capture rig built; first ATP-08 dry-run on Healthy-only data |
| 4 | ATP-05 against RF baseline; PDR gate |
| 5 | ATP-01, ATP-02 against first deployed model |
| 6 | ATP-03, ATP-06, ATP-08 with full stack |
| 7 | ATP-07; full pipeline at CDR |
| 8 | All ATPs end-to-end against the verification dataset |
| 9 | ATP-11 dry-run; ATP-09 dress rehearsal |
| 10 | ATP-09 live + ATP-11 for the recording |

## 8. Defect log policy

Defects discovered during ATP execution land in GitHub Issues with:
- ATP that surfaced the defect
- Severity: P0 (blocks acceptance) / P1 (fix this week) / P2 (track)
- Reproduction steps
- Owner

P0/P1 must be closed before the next milestone. P2 is reviewed in the weekly status meeting.

## 9. Sign-off

| Role | Name | Date |
|---|---|---|
| PM | Stephen Eacuello | |
| Sponsor | Dr. Lance Decker | |
