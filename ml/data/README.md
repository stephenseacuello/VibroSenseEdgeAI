# Dataset Card — VibroSense Edge AI

Captured vibration data for predictive maintenance of a small rotating asset.

## Source
- **Asset.** TBD Wk 2 (consumer-grade desk fan or smart fan, ≤ $100).
- **Sensor.** LSM9DS1 accelerometer on Arduino Nano 33 BLE Sense, ODR ~952 Hz.
- **Capture tool.** [`ml/src/capture.py`](../src/capture.py).
- **Window.** 256 samples, non-overlapping (tune Wk 4).

## Classes
| Label | Description |
|---|---|
| `HEALTHY` | Baseline, factory condition. |
| `IMBALANCE` | Calibrated mass per [PROJECT_PLAN.md §9.2.1](../../PROJECT_PLAN.md#921-imbalance). |
| `LOOSENESS` | Loose mount bolt per §9.2.2. |
| `BEARING_FAULT` | Simulated per §9.2.3 (method TBD; locked in ADR-0002). |

## Split policy
70 / 15 / 15 train / val / test, **stratified by `session_id`** — no session appears in more than one split.

## File layout
```
ml/data/raw/{session_id}.parquet      # window records
ml/data/raw/{session_id}.meta.json    # SessionMeta sidecar
```

## Manifest
Each model training run cites the SHA-256 of `manifest.txt` (a sorted listing of `session_id  sha256`) in its experiment log entry under `ml/experiments/`.

## Inline quality checks
The capture tool refuses to save sessions that fail any of:
- non-finite samples,
- gravity-axis mean |a_z| outside [0.7, 1.3] g,
- clipping rate ≥ 0.1%,
- duration < 3 min.
