"""Evaluate a trained Keras (or TFLite) model against a held-out test split.

Produces the ATP-05 acceptance report:

  - overall accuracy
  - per-class precision / recall / f1
  - confusion matrix
  - sample count per class

Usage:
    python -m ml.src.eval ml/artifacts/cnn.keras ml/data/raw/synth.parquet
    python -m ml.src.eval ml/artifacts/cnn.tflite ml/data/raw/synth.parquet
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix

from .train_cnn import CLASSES, LABEL_TO_IDX, load_dataset, session_stratified_split

ATP05_ACCURACY = 0.90
ATP05_PER_CLASS_RECALL = 0.80


@dataclass
class EvalReport:
    model_path: str
    dataset_path: str
    n_test: int
    accuracy: float
    per_class_recall: dict[str, float]
    confusion_matrix: list[list[int]]
    classification_report: str

    def passes_atp05(self) -> bool:
        if self.accuracy < ATP05_ACCURACY:
            return False
        return all(r >= ATP05_PER_CLASS_RECALL for r in self.per_class_recall.values())


def _predict_keras(model_path: Path, X: np.ndarray) -> np.ndarray:
    import tensorflow as tf

    model = tf.keras.models.load_model(model_path)
    probs = model.predict(X, verbose=0)
    return np.argmax(probs, axis=1)


def _predict_tflite(model_path: Path, X: np.ndarray) -> np.ndarray:
    import tensorflow as tf

    interp = tf.lite.Interpreter(model_path=str(model_path))
    interp.allocate_tensors()
    inp = interp.get_input_details()[0]
    out = interp.get_output_details()[0]

    preds = np.zeros(X.shape[0], dtype=np.int32)
    # Handle both INT8-quantized and float32 inputs.
    scale, zero_point = inp.get("quantization", (0.0, 0))
    is_int8 = inp["dtype"] == np.int8 and scale > 0
    for i, x in enumerate(X):
        x = x[None, ...].astype(np.float32)
        if is_int8:
            x = np.clip(np.round(x / scale + zero_point), -128, 127).astype(np.int8)
        interp.set_tensor(inp["index"], x)
        interp.invoke()
        y = interp.get_tensor(out["index"])[0]
        preds[i] = int(np.argmax(y))
    return preds


def run_eval(model_path: Path, dataset_path: Path, test_frac: float = 0.15, seed: int = 42) -> EvalReport:
    X, y, groups = load_dataset(dataset_path)
    _, test_mask = session_stratified_split(groups, test_frac=test_frac, seed=seed)
    Xt, yt = X[test_mask], y[test_mask]
    if len(Xt) == 0:
        raise SystemExit("test split is empty — increase dataset size or test_frac")

    if model_path.suffix == ".tflite":
        pred = _predict_tflite(model_path, Xt)
    else:
        pred = _predict_keras(model_path, Xt)

    acc = float((pred == yt).mean())
    cm = confusion_matrix(yt, pred, labels=list(range(len(CLASSES))))
    rep_text = classification_report(yt, pred, labels=list(range(len(CLASSES))), target_names=CLASSES, zero_division=0)

    per_class_recall: dict[str, float] = {}
    for idx, cls in enumerate(CLASSES):
        total = int(cm[idx].sum())
        per_class_recall[cls] = float(cm[idx, idx] / total) if total else 0.0

    return EvalReport(
        model_path=str(model_path),
        dataset_path=str(dataset_path),
        n_test=int(len(Xt)),
        accuracy=acc,
        per_class_recall=per_class_recall,
        confusion_matrix=cm.tolist(),
        classification_report=rep_text,
    )


def _format_report(r: EvalReport) -> str:
    lines = [
        f"=== Evaluation report ===",
        f"model:   {r.model_path}",
        f"dataset: {r.dataset_path}",
        f"n_test:  {r.n_test}",
        "",
        f"overall accuracy: {r.accuracy:.4f}",
        "",
        "per-class recall:",
    ]
    for cls in CLASSES:
        rec = r.per_class_recall[cls]
        gate = "OK" if rec >= ATP05_PER_CLASS_RECALL else "LOW"
        lines.append(f"  {cls:<14} {rec:.3f}  [{gate}]")
    lines += ["", "classification report:", r.classification_report]
    lines += ["", "confusion matrix (rows=actual, cols=predicted):", "  " + " ".join(f"{c:>14}" for c in CLASSES)]
    for actual, row in zip(CLASSES, r.confusion_matrix):
        lines.append(f"  {actual:<14} " + " ".join(f"{v:>14}" for v in row))
    lines += ["", f"ATP-05 gate: {'PASS' if r.passes_atp05() else 'FAIL'}"]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("model", help="Path to .keras or .tflite model")
    p.add_argument("dataset", help="Parquet with window/class_label/session_id")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    p.add_argument("--test-frac", type=float, default=0.15)
    args = p.parse_args()

    report = run_eval(Path(args.model), Path(args.dataset), test_frac=args.test_frac)
    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(_format_report(report))
    return 0 if report.passes_atp05() else 2  # non-zero exit if ATP-05 fails


if __name__ == "__main__":
    raise SystemExit(main())
