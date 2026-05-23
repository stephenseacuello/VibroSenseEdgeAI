# Hardware bring-up checklist

Step-by-step for the first time you take the Nano + Pi out of the box and run the stack end-to-end. Triage section at the bottom for the failure modes you'll likely hit.

## What you need on the bench

| | |
|---|---|
| Arduino Nano 33 BLE Sense | with the Tiny ML Shield seated |
| Micro-USB cable | data-capable, not power-only |
| Raspberry Pi 4 (optional) | with PSU and SD card flashed with Raspberry Pi OS Lite |
| Dev laptop | macOS or Linux + Python 3.11 + git |
| Asset | TBD per [OD-01](../PROJECT_PLAN.md#24-open-decisions-register) (basic desk fan or similar) |
| Mounting fixture | per §9 (built Wk 3) |

## 1. Dev box (laptop)

```bash
git clone git@github.com:<owner>/VibroSenseEdgeAI.git
cd VibroSenseEdgeAI
./scripts/bootstrap_dev.sh
```

This installs arduino-cli, the Arduino mbed_nano core, ArduinoBLE, Arduino_LSM9DS1, the TFLite Micro library, Mosquitto, a Python venv, and pre-commit. At the end it runs `arduino-cli compile` once to sanity-check the firmware builds against the libraries it just installed.

## 2. Flash the Nano

```bash
arduino-cli board list            # confirm the Nano appears; copy the port
PORT=/dev/cu.usbmodemXXXX make flash
```

If you see:

```
Sketch uses ...... bytes (...%) of program storage space.
Global variables use ...... bytes (...%) of dynamic memory.
```

…then you're good. Record those numbers against [PROJECT_PLAN.md §4.2](../PROJECT_PLAN.md#42-nano-33-ble-sense-memory-budget-nrf52840) — this is the ATP-02 input.

Expected behavior after flash:

- Blue LED solid for ~2 s (advertising)
- Then continues blue until something connects

## 3. Verify BLE from the laptop

Easiest path — `bluetoothctl` (Linux) or **nRF Connect** (mobile app, both platforms) — and scan for `VibroSense-Nano`. You should see:

- The Service UUID `7e5c0001-d9b7-4f12-8a6b-0a0b0c0d0e0f`
- Four characteristics (`state`, `mode`, `version`, `raw_window`)
- The `version` characteristic, when read, returns `v0.1-scaffold` (or whatever your tag is)

Subscribe to `state` (notify). At ~3.7 Hz (one notify per 256-sample window) you should see JSON like:

```json
{"schema_ver":1,"ts_ms":12345,"seq":42,"state":"HEALTHY","confidence":0.000}
```

The `confidence:0.000` is the placeholder model's signature — that's normal until you train.

## 4. Bring up the gateway

### Option A — dev box (the easy path)

In one terminal:

```bash
make demo
```

In a browser:

```bash
open http://localhost:5000
```

You should see the operator HMI tile update every second-ish.

### Option B — Raspberry Pi

```bash
ssh pi@<pi-host>
git clone git@github.com:<owner>/VibroSenseEdgeAI.git
cd VibroSenseEdgeAI
./scripts/bootstrap_pi.sh
```

Then from your laptop:

```bash
open http://<pi-host>:5000
```

## 5. Capture your first dataset session

Once BLE is verified:

```bash
make capture ARGS="--class-label HEALTHY --operator <you> --speed 2 --duration-s 300 \
                   --notes 'workbench A, oscillation off'"
```

Repeat per class until ≥ 30 min per class. The capture tool refuses to save sessions that fail the §9.4 quality checks.

## 6. Train + deploy a real model

See the firmware [README "Bringing up a real model"](../firmware/README.md#bringing-up-a-real-model) section. Summary:

```bash
make train ARGS="ml/data/raw/session.parquet --epochs 60"
make quantize ARGS="ml/artifacts/cnn.keras --rep-data ml/data/raw/session.parquet"
make export   ARGS="ml/artifacts/cnn.tflite"
make firmware && PORT=... make flash
```

## 7. Verify ATPs

```bash
PORT=/dev/cu.usbmodemXXXX python scripts/atp01_timing.py --port $PORT --duration-s 60  # ATP-01
make verify-firmware                                                                    # ATP-02
make eval ARGS="ml/artifacts/cnn.keras ml/data/raw/session.parquet"                     # ATP-05
```

---

## Triage — when it doesn't work

### "arduino-cli compile" fails with header-not-found

The Arduino library install hadn't run when you compiled, or completed only partially. Re-run:

```bash
./scripts/bootstrap_dev.sh
```

The script is idempotent — safe to re-run.

### "IMU init failed" on the serial monitor

- Check you have the **Nano 33 BLE Sense** (with IMU), not the plain Nano 33 BLE.
- `Arduino_LSM9DS1` library version mismatch — uninstall and reinstall via `arduino-cli lib`.
- The RGB LED will blink red — that's the firmware signaling the init failure.

### Nano flashes successfully but doesn't advertise

- Double-press reset on the board within 1 s to enter the bootloader, then re-flash.
- Power-cycle (unplug + replug USB) after flash.
- Check the Serial output — `setup()` prints "VibroSense-Nano advertising" on success.

### `bleak` / `make capture` reports "device not found"

- BLE permission on macOS: the first time the Python process scans BLE, the OS may silently block it. Open **System Settings → Privacy & Security → Bluetooth** and ensure the Terminal app (or your IDE) is allowed.
- On Linux, the user running the script needs membership in the `bluetooth` group, or sudo.
- Move the Nano closer; BLE LE has a ~3 m range with the chip antenna.

### Captured a session, but the parquet is empty / quality check fails

- The `raw_window` UUID drifted from the Python side. Confirm both sides match ADR-0001 (current frozen value: `…0e13`).
- Sensor mis-mounted: the z-axis must point along gravity (within ±30°). The quality check flags mean `|a_z|` outside `[0.7, 1.3] g`.
- Sample rate drift: the Nano can't sustain 952 Hz under heavy BLE backpressure — try a shorter `--duration-s` and confirm chunks aren't being dropped.

### `Inference::begin()` returns false after exporting a real model

`AllocateTensors()` ran out of arena. Bump `kTensorArenaSize` in [`firmware/nano33/src/inference.cpp`](../firmware/nano33/src/inference.cpp) (default 32 KB → try 48 or 64 KB) and re-flash. The needed value is one of the numbers you'll quote in §4.2.

### Flask app shows "—" forever

- Open `/healthz` and `/readyz` — if `readyz` returns 503, the gateway hasn't written any events to SQLite yet.
- Check `journalctl -u vibrosense-mqtt2db -f` on the Pi.
- Verify Mosquitto is up: `mosquitto_sub -t 'pdm/+/#' -v`.

### Operator tile is amber/red but the asset looks fine

Confidence-floor flicker — the per-window classifier disagrees with itself at the edges of fault transitions. The Node-RED state-change detector has a 0.6 confidence floor ([ADR-0003](decisions/0003-confidence-floor.md)); the operator tile, by design, shows every per-window prediction (not just transitions). If the live tile flickers but the alarm strip is steady, the system is behaving correctly — the alarm is the human-meaningful signal.
