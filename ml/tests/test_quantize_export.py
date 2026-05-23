"""Quantize → export → re-import round-trip. Gated by TensorFlow installation."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

tf = pytest.importorskip("tensorflow")


def _train_and_save_tiny_model(parquet: Path, out: Path) -> None:
    from ml.src.train_cnn import build_model, load_dataset

    X, y, _ = load_dataset(parquet)
    model = build_model(window_size=X.shape[1])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.fit(X, y, epochs=1, batch_size=16, verbose=0)
    model.save(out)


def test_quantize_emits_tflite(tiny_synth_parquet, tmp_path):
    keras = tmp_path / "tiny.keras"
    _train_and_save_tiny_model(tiny_synth_parquet, keras)

    # Invoke the CLI exactly as `make quantize` would.
    res = subprocess.run(
        [sys.executable, "-m", "ml.src.quantize", str(keras), "--rep-data", str(tiny_synth_parquet),
         "--n-samples", "32"],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stderr
    tflite = keras.with_suffix(".tflite")
    assert tflite.exists()
    assert tflite.stat().st_size > 0


def test_export_emits_valid_c_header(tiny_synth_parquet, tmp_path):
    keras = tmp_path / "tiny.keras"
    _train_and_save_tiny_model(tiny_synth_parquet, keras)

    # First quantize
    subprocess.run(
        [sys.executable, "-m", "ml.src.quantize", str(keras), "--rep-data", str(tiny_synth_parquet),
         "--n-samples", "32"],
        check=True, capture_output=True, text=True,
    )
    tflite = keras.with_suffix(".tflite")

    # Then export to a C header
    header = tmp_path / "model.h"
    subprocess.run(
        [sys.executable, "-m", "ml.src.export", str(tflite), "--out", str(header)],
        check=True, capture_output=True, text=True,
    )
    text = header.read_text()

    # Sanity-check: header has the expected symbol declarations and the byte count matches the file.
    assert "vibrosense_model_tflite[]" in text
    assert "vibrosense_model_tflite_len" in text
    m = re.search(r"vibrosense_model_tflite_len\s*=\s*(\d+)", text)
    assert m
    declared_len = int(m.group(1))
    assert declared_len == tflite.stat().st_size


def test_tflite_roundtrip_predictions_close(tiny_synth_parquet, tmp_path):
    """Smoke: float Keras and INT8 TFLite agree on most samples."""
    import numpy as np
    from ml.src.train_cnn import load_dataset

    keras = tmp_path / "tiny.keras"
    _train_and_save_tiny_model(tiny_synth_parquet, keras)

    subprocess.run(
        [sys.executable, "-m", "ml.src.quantize", str(keras), "--rep-data", str(tiny_synth_parquet),
         "--n-samples", "32"],
        check=True, capture_output=True, text=True,
    )
    tflite = keras.with_suffix(".tflite")

    X, _y, _g = load_dataset(tiny_synth_parquet)

    model = tf.keras.models.load_model(keras)
    keras_pred = np.argmax(model.predict(X, verbose=0), axis=1)

    interp = tf.lite.Interpreter(model_path=str(tflite))
    interp.allocate_tensors()
    inp = interp.get_input_details()[0]
    out = interp.get_output_details()[0]
    scale, zp = inp["quantization"]

    tflite_pred = np.zeros(len(X), dtype=np.int32)
    for i, x in enumerate(X):
        q = np.clip(np.round(x[None, ...] / scale + zp), -128, 127).astype(np.int8)
        interp.set_tensor(inp["index"], q)
        interp.invoke()
        tflite_pred[i] = int(np.argmax(interp.get_tensor(out["index"])[0]))

    agreement = float((keras_pred == tflite_pred).mean())
    # On a 1-epoch model the agreement floor is loose; we just check the pipeline doesn't randomize.
    assert agreement >= 0.5, f"keras/tflite agreement was only {agreement:.3f}"
