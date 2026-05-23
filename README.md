# VibroSenseEdgeAI

Edge-AI predictive maintenance for a small rotating asset. ISE 575 capstone, Summer 2026, University of Rhode Island.

> *"From vibration to decision, on-device."*

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the full plan, charter mapping, and acceptance criteria.

## What this is

The **production / hardware-targeted** repository. The firmware boots on a real Arduino Nano 33 BLE Sense + Tiny ML Shield, the Python ML pipeline trains against captured vibration data, the gateway runs on a Raspberry Pi 4 over BLE → Mosquitto → SQLite, and the Flask app serves the operator HMI + trend view + REST API.

For development without hardware (synthetic data, fake BLE producer, mock pipeline) see the sister repo [`../VibroSenseEdgeAI-demo/`](../VibroSenseEdgeAI-demo/) — same structure, plus a `mock_ble_producer` and a `demo-mock` make target.

The system covers **ISA-95 Levels 0–3**.

## Quick start (with hardware)

```bash
# One-time — installs arduino-cli, the core, all libraries, Mosquitto, the Python venv
make dev-bootstrap

# Build + flash the Nano
make firmware
PORT=/dev/cu.usbmodem14101 make flash             # confirm port with `arduino-cli board list`

# On the Pi (one-shot provisioning)
./scripts/bootstrap_pi.sh

# Or, for a local dev box (macOS / Linux):
brew install mosquitto
make demo
open http://localhost:5000
```

The Nano boots as `VibroSense-Nano`, advertises BLE, accepts CAPTURE-mode raw-window streaming **before any model is trained** — so you can immediately start collecting data. Inference returns `HEALTHY @ 0.0` until you train and flash a real model (`make ml-pipeline` then re-flash).

## Capture → train → deploy loop

```bash
# 1. Capture labeled vibration data — repeat per class until ≥ 30 min each.
make capture ARGS="--class-label HEALTHY   --operator amuszynski --speed 2 --duration-s 300"
make capture ARGS="--class-label IMBALANCE --operator amuszynski --speed 2 --duration-s 300 \
                   --fault-params '{\"mass_g\": 1.0, \"position\": \"B1-tip\"}'"
# ... LOOSENESS, BEARING_FAULT ...

# 2. Concatenate captured parquets (or train against your latest sessions directly).
# 3. Train, quantize, export to firmware/nano33/model/model.h, flash.
make train    ARGS="ml/data/raw/session.parquet --epochs 60"
make quantize ARGS="ml/artifacts/cnn.keras --rep-data ml/data/raw/session.parquet"
make export   ARGS="ml/artifacts/cnn.tflite"
make firmware && make flash

# 4. Verify with the ATP suite.
make eval     ARGS="ml/artifacts/cnn.keras ml/data/raw/session.parquet"
```

## Layout

| Path | What lives there |
|---|---|
| `firmware/nano33/` | Arduino sketch + BLE service + **real** TFLite Micro inference + `model.h` |
| `ml/` | Python pipeline: capture → features → RF baseline → 1D-CNN → INT8 → `model.h` → eval |
| `gateway/` | `bleak` central (with ATP-03 seq-gap accounting), Mosquitto, Node-RED, SQLite, systemd |
| `app/` | Flask app: operator HMI, trend view, REST API, WebSocket, alarms |
| `scripts/` | Pi bootstrap, demo runner |
| `docs/` | Charter, design reviews, test plan, ADRs, schematics |
| `tests/` | Cross-layer integration tests |

## Documentation

- [PROJECT_PLAN.md](PROJECT_PLAN.md) — single source of truth for the project plan
- [CONTRIBUTING.md](CONTRIBUTING.md) — dev loop and code-review rules
- [docs/hardware_bringup.md](docs/hardware_bringup.md) — step-by-step bring-up + failure-mode triage
- [docs/test-plan/test_plan_v1.md](docs/test-plan/test_plan_v1.md) — formal ATP-mapped test plan
- [firmware/README.md](firmware/README.md) — Nano build / flash / debug
- [ml/README.md](ml/README.md) — pipeline overview + experiment-log convention
- [gateway/README.md](gateway/README.md) — Pi service topology, MQTT topics, ATP-03
- [app/README.md](app/README.md) — Flask routes, env vars, design notes
- [docs/decisions/](docs/decisions/) — architecture decision records (ADRs)

## License

MIT — see [LICENSE](LICENSE).
