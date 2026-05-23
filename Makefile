.PHONY: setup test lint format capture train eval baseline quantize export firmware flash \
        verify-firmware merge-sessions atp01 demo pi-bootstrap dev-bootstrap synth-dataset \
        ml-pipeline clean

PY      := python3
VENV    := .venv
ACT     := . $(VENV)/bin/activate &&
ARGS    ?=
PORT    ?= /dev/cu.usbmodem14101
FQBN    ?= arduino:mbed_nano:nano33ble

# --- env ------------------------------------------------------------------
setup:
	$(PY) -m venv $(VENV)
	$(ACT) pip install -U pip
	$(ACT) pip install -e ".[dev]"
	$(ACT) pre-commit install

# --- quality --------------------------------------------------------------
test:
	$(ACT) pytest -q

lint:
	$(ACT) ruff check .
	$(ACT) black --check .

format:
	$(ACT) ruff check --fix .
	$(ACT) black .

# --- ML pipeline ---------------------------------------------------------
capture:
	$(ACT) python -m ml.src.capture $(ARGS)

baseline:
	$(ACT) python -m ml.src.baseline_rf $(ARGS)

train:
	$(ACT) python -m ml.src.train_cnn $(ARGS)

quantize:
	$(ACT) python -m ml.src.quantize $(ARGS)

export:
	$(ACT) python -m ml.src.export $(ARGS)

eval:
	$(ACT) python -m ml.src.eval $(ARGS)

synth-dataset:
	$(ACT) python scripts/synth_dataset.py --out ml/data/raw/synth.parquet

merge-sessions:
	$(ACT) python -m ml.src.merge_sessions $(ARGS)

# End-to-end ML smoke: synth → train → quantize → export → eval.
# Useful for verifying the whole pipeline without hardware. Requires the [ml] extra.
ml-pipeline: synth-dataset
	$(ACT) python -m ml.src.train_cnn ml/data/raw/synth.parquet \
	    --out ml/artifacts/cnn.keras --epochs 12
	$(ACT) python -m ml.src.quantize ml/artifacts/cnn.keras \
	    --rep-data ml/data/raw/synth.parquet --n-samples 64
	$(ACT) python -m ml.src.export ml/artifacts/cnn.tflite \
	    --out firmware/nano33/model/model.h
	$(ACT) python -m ml.src.eval ml/artifacts/cnn.keras ml/data/raw/synth.parquet

# --- Firmware ------------------------------------------------------------
firmware:
	arduino-cli compile --fqbn $(FQBN) firmware/nano33

# Quick local sanity: compile with strict warnings, print the size report so we
# can spot-check ATP-02 (memory budget) without flashing.
verify-firmware:
	arduino-cli compile --fqbn $(FQBN) firmware/nano33 --warnings default --verbose 2>&1 \
	    | tail -25

flash:
	arduino-cli upload -p $(PORT) --fqbn $(FQBN) firmware/nano33

# ATP-01 — needs the firmware built with -DDEBUG_TIMING=1 already flashed.
atp01:
	$(ACT) python scripts/atp01_timing.py --port $(PORT) $(ARGS)

# --- Demo (real hardware required) -------------------------------------
demo:
	./scripts/run_demo.sh

# --- Provisioning -------------------------------------------------------
dev-bootstrap:
	./scripts/bootstrap_dev.sh

pi-bootstrap:
	./scripts/bootstrap_pi.sh

# --- Housekeeping -------------------------------------------------------
clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache build dist *.egg-info
	find . -name __pycache__ -type d -exec rm -rf {} +
