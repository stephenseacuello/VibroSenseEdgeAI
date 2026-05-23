"""1D-CNN training per PROJECT_PLAN.md §10.3.

Usage:
    python -m ml.src.train_cnn path/to/dataset.parquet --out ml/artifacts/cnn.keras
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import tensorflow as tf
    from tensorflow.keras import layers
except ImportError:  # pragma: no cover
    print("tensorflow not installed; `pip install -e \".[ml]\"`", file=sys.stderr)
    raise

CLASSES = ("HEALTHY", "IMBALANCE", "LOOSENESS", "BEARING_FAULT")
LABEL_TO_IDX = {c: i for i, c in enumerate(CLASSES)}


def build_model(window_size: int = 256, channels: int = 3, n_classes: int = 4) -> tf.keras.Model:
    return tf.keras.Sequential([
        layers.Input(shape=(window_size, channels)),
        layers.Conv1D(8, 5, activation="relu", padding="same"),
        layers.MaxPool1D(2),
        layers.Conv1D(16, 5, activation="relu", padding="same"),
        layers.MaxPool1D(2),
        layers.Conv1D(32, 3, activation="relu", padding="same"),
        layers.GlobalAveragePooling1D(),
        layers.Dense(16, activation="relu"),
        layers.Dropout(0.3),
        layers.Dense(n_classes, activation="softmax"),
    ])


def load_dataset(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    df = pd.read_parquet(path)
    for col in ("window", "class_label", "session_id"):
        if col not in df.columns:
            raise ValueError(f"dataset missing column: {col}")
    # Windows are stored flat (parquet limitation); reshape to (N, 3) here.
    X = np.stack([np.asarray(w, dtype=np.float32).reshape(-1, 3) for w in df["window"]])
    y = np.array([LABEL_TO_IDX[c] for c in df["class_label"]], dtype=np.int32)
    groups = df["session_id"].to_numpy()
    return X, y, groups


def session_stratified_split(
    groups: np.ndarray, test_frac: float = 0.15, seed: int = 42
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    unique = np.unique(groups)
    rng.shuffle(unique)
    n_test = max(1, int(test_frac * len(unique)))
    test_sessions = set(unique[:n_test])
    test_mask = np.array([g in test_sessions for g in groups])
    return ~test_mask, test_mask


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("dataset")
    p.add_argument("--out", default="ml/artifacts/cnn.keras")
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--batch", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-3)
    args = p.parse_args()

    X, y, groups = load_dataset(Path(args.dataset))
    train_mask, test_mask = session_stratified_split(groups)
    X_tr, y_tr = X[train_mask], y[train_mask]
    X_te, y_te = X[test_mask], y[test_mask]

    model = build_model(window_size=X.shape[1])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(args.lr),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.summary()

    model.fit(
        X_tr,
        y_tr,
        validation_split=0.15,
        epochs=args.epochs,
        batch_size=args.batch,
        callbacks=[tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", patience=5)],
    )

    loss, acc = model.evaluate(X_te, y_te, verbose=0)
    print(f"test_loss={loss:.4f} test_acc={acc:.4f}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    model.save(out)
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
