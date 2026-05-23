"""Generate a small synthetic dataset for ML pipeline testing.

Each class is given a distinct vibration signature so that the RF baseline and
the 1D-CNN can both reach respectable accuracy in tests — without needing real
hardware. The output parquet matches the schema consumed by
`ml/src/baseline_rf.py` and `ml/src/train_cnn.py`:

    columns: window (object, np.ndarray (N, 3) float32), class_label, session_id

Usage:
    python scripts/synth_dataset.py --out ml/data/raw/synth.parquet \
        --windows-per-session 20 --sessions-per-class 5
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

CLASSES = ("HEALTHY", "IMBALANCE", "LOOSENESS", "BEARING_FAULT")
WINDOW_SIZE = 256
FS = 952.0


def _gen_window(rng: np.random.Generator, label: str, t: np.ndarray) -> np.ndarray:
    """Return a (WINDOW_SIZE, 3) float32 array with a class-specific signature."""
    n = len(t)
    noise = rng.standard_normal((n, 3)).astype(np.float32) * 0.04
    base = np.zeros((n, 3), dtype=np.float32)
    base[:, 2] = 1.0  # gravity on z

    if label == "HEALTHY":
        # mild broadband noise only
        sig = noise
    elif label == "IMBALANCE":
        # strong 1× tone on x and y, 90° phase shift
        f0 = 30.0 + rng.uniform(-3, 3)
        amp = 0.4
        sig = noise.copy()
        sig[:, 0] += amp * np.sin(2 * np.pi * f0 * t).astype(np.float32)
        sig[:, 1] += amp * np.cos(2 * np.pi * f0 * t).astype(np.float32)
    elif label == "LOOSENESS":
        # broadband noise floor + sporadic impulses
        sig = noise * 3.5
        n_impulses = rng.integers(3, 8)
        for _ in range(n_impulses):
            i = int(rng.integers(0, n))
            sig[i, :2] += rng.choice([-1.0, 1.0]) * rng.uniform(0.6, 1.2)
    elif label == "BEARING_FAULT":
        # high-frequency content (~200 Hz) modulated by a low envelope
        f_hi = 200.0 + rng.uniform(-15, 15)
        f_env = 5.0 + rng.uniform(-1, 1)
        env = 0.4 * (1 + np.sin(2 * np.pi * f_env * t)).astype(np.float32)
        hf = np.sin(2 * np.pi * f_hi * t).astype(np.float32)
        sig = noise.copy()
        sig[:, 0] += env * hf
        sig[:, 1] += env * hf * 0.7
    else:  # pragma: no cover
        raise ValueError(label)

    return base + sig


def build(rng: np.random.Generator, sessions_per_class: int, windows_per_session: int) -> pd.DataFrame:
    """Build a parquet-friendly DataFrame.

    The `window` column stores **flattened** (N*3,) arrays because parquet/arrow
    cannot represent 2D arrays inside an object cell. Consumers (`load_dataset`,
    `_build_X`) reshape back to (N, 3) on read.
    """
    t = (np.arange(WINDOW_SIZE) / FS).astype(np.float32)
    rows: list[dict] = []
    for cls in CLASSES:
        for s in range(sessions_per_class):
            session_id = f"synth_{cls}_s{s:02d}"
            for w in range(windows_per_session):
                window = _gen_window(rng, cls, t)
                rows.append(
                    {
                        "window": window.flatten().astype(np.float32),
                        "class_label": cls,
                        "session_id": session_id,
                    }
                )
    return pd.DataFrame(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="ml/data/raw/synth.parquet")
    p.add_argument("--sessions-per-class", type=int, default=5)
    p.add_argument("--windows-per-session", type=int, default=20)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    rng = np.random.default_rng(args.seed)
    df = build(rng, args.sessions_per_class, args.windows_per_session)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out)
    print(f"wrote {out} ({len(df)} windows across {df['session_id'].nunique()} sessions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
