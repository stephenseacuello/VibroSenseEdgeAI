# `ml/` — Python machine-learning pipeline

The capture → feature → model → quantize → export → eval pipeline. Built so every step can be exercised against synthetic data in CI, then re-run against real captures from the Nano during Weeks 3–8.

See [PROJECT_PLAN.md §10](../PROJECT_PLAN.md#10-ml-pipeline-plan).

## Layout

```
ml/
├── src/
│   ├── capture.py        # BLE-streamed raw-window capture (ADR-0004)
│   ├── raw_window.py     # binary protocol encode/decode (ADR-0004)
│   ├── schema.py         # pydantic StateV1, AlarmV1
│   ├── features.py       # time + frequency features (RMS, kurtosis, FFT bins, ...)
│   ├── baseline_rf.py    # sklearn RandomForest baseline
│   ├── train_cnn.py      # 1D-CNN trainer (PROJECT_PLAN.md §10.3)
│   ├── quantize.py       # Keras → INT8 TFLite
│   ├── export.py         # TFLite → C array at firmware/nano33/model/model.h
│   └── eval.py           # ATP-05 evaluator
├── tests/
│   ├── conftest.py       # synth dataset fixtures
│   ├── test_features.py
│   ├── test_raw_window.py
│   ├── test_baseline_rf.py
│   ├── test_train_cnn.py            # TF-gated
│   ├── test_quantize_export.py      # TF-gated
│   └── test_eval.py                 # TF-gated
├── data/
│   ├── README.md         # dataset card
│   ├── raw/              # captured + synthetic windows (.parquet)
│   └── processed/
├── notebooks/            # exploratory work
├── experiments/          # one markdown file per training run (manual)
└── artifacts/            # generated models (.keras, .tflite); gitignored
```

## End-to-end pipeline (synthetic, no hardware)

```bash
make synth-dataset   # generate 400-window synthetic parquet
make baseline ARGS=ml/data/raw/synth.parquet
make train    ARGS="ml/data/raw/synth.parquet --epochs 12"
make quantize ARGS="ml/artifacts/cnn.keras --rep-data ml/data/raw/synth.parquet"
make export   ARGS="ml/artifacts/cnn.tflite --out firmware/nano33/model/model.h"
make eval     ARGS="ml/artifacts/cnn.keras ml/data/raw/synth.parquet"
```

All five together:

```bash
make ml-pipeline
```

Requires the `[ml]` extra: `pip install -e ".[ml]"`.

## Real-hardware capture

When a Nano with the v0.2+ firmware is in range and advertising as `VibroSense-Nano`:

```bash
make capture ARGS="--class-label HEALTHY --operator amuszynski --speed 2 \
    --duration-s 300 --notes 'workbench A, oscillation off'"
```

The tool subscribes to the `raw_window` characteristic (ADR-0004), reassembles chunks via [`raw_window.WindowAssembler`](src/raw_window.py), runs the inline data-quality checks from [PROJECT_PLAN.md §9.4](../PROJECT_PLAN.md#94-data-quality-checks-run-inline-by-capturepy), and writes `ml/data/raw/{session_id}.parquet` + a sidecar `{session_id}.meta.json`.

If quality checks fail (e.g., sensor mis-mounted, clipping, < 3 min duration) the file is **not** saved. Add `--force` to override during bring-up only.

## Dataset format

Every parquet under `ml/data/raw/` has these columns:

| Column        | Type                       | Meaning |
|---------------|----------------------------|---------|
| `window`      | `float32 (N*3,)` flattened | One IMU window, ax/ay/az interleaved. Readers reshape to `(N, 3)`. |
| `class_label` | str                        | `HEALTHY` / `IMBALANCE` / `LOOSENESS` / `BEARING_FAULT` |
| `session_id`  | str                        | Used for stratified train/test splits — sessions never cross a split. |

The flattening exists because pyarrow can't store 2D arrays in object cells. `load_dataset()` and `_build_X()` reshape on read; this is transparent.

## Experiment log

Each training run gets one markdown file under `ml/experiments/`:

```
ml/experiments/2026-07-15_baseline-window-256.md
```

Template ([PROJECT_PLAN.md §10.5](../PROJECT_PLAN.md#105-experiment-tracking)):

```markdown
---
date_utc: 2026-07-15T18:22:00Z
operator: muszynski
dataset_sha: abc123…
code_sha:    def456…
---

## Hyperparameters
window_size: 256
batch_size: 64
epochs: 60
lr: 1e-3

## Results
train_acc: 0.97   val_acc: 0.93   test_acc: 0.91
model_size_pre_quant_kb: 24
model_size_int8_kb: 12
on_device_latency_ms_p95: 210

## Confusion matrix
…

## Notes
Bearing/looseness occasionally confused at fan speed 1.
```

Reproducibility > tooling — we stay off MLflow until we have a reason to need it.

## When you change features or model architecture

1. Update [`features.py`](src/features.py) or [`train_cnn.py`](src/train_cnn.py).
2. Update the relevant test if the contract changed.
3. Re-run `make ml-pipeline` and capture before/after metrics in the experiment log.
4. If model footprint changed materially, update [PROJECT_PLAN.md §4.2](../PROJECT_PLAN.md#42-nano-33-ble-sense-memory-budget-nrf52840).

## When you change the raw-window protocol

Bumping anything in ADR-0004 requires a coordinated change:

1. Edit [ADR-0004](../docs/decisions/0004-raw-window-protocol.md).
2. Update [`raw_window.py`](src/raw_window.py) and its tests.
3. Update [`firmware/nano33/src/ble_service.cpp`](../firmware/nano33/src/ble_service.cpp) in lockstep.
4. Re-run `pytest tests/integration/test_capture_pipeline.py` — the loopback test fails if the two sides drift.
