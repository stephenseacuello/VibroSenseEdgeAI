"""INT8 quantize a Keras model → .tflite, using a representative dataset slice.

Usage:
    python -m ml.src.quantize ml/artifacts/cnn.keras --rep-data path/to/dataset.parquet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import tensorflow as tf
except ImportError:  # pragma: no cover
    print("tensorflow not installed; `pip install -e \".[ml]\"`", file=sys.stderr)
    raise


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("keras_model")
    p.add_argument("--rep-data", required=True, help="Parquet with a 'window' column")
    p.add_argument("--n-samples", type=int, default=100)
    args = p.parse_args()

    model = tf.keras.models.load_model(args.keras_model)
    df = pd.read_parquet(args.rep_data)
    sample = df.sample(min(args.n_samples, len(df)), random_state=42)["window"].tolist()
    rep = np.stack([np.asarray(w, dtype=np.float32) for w in sample])

    def representative_gen():
        for x in rep:
            yield [x[None, ...]]

    conv = tf.lite.TFLiteConverter.from_keras_model(model)
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = representative_gen
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8

    tflite = conv.convert()
    out = Path(args.keras_model).with_suffix(".tflite")
    out.write_bytes(tflite)
    print(f"wrote {out} ({len(tflite)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
