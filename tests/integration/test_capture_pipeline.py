"""End-to-end loopback test for the data-capture pipeline.

Exercises ADR-0004 (raw_window protocol) all the way through to the RF baseline,
without any hardware:

    synth windows  ──encode_window──▶  binary frames
                                         │
                                         ▼
                                   WindowAssembler
                                         │
                                         ▼
                              parquet (training format)
                                         │
                                         ▼
                              _build_X (features) + RF
                                         │
                                         ▼
                              accuracy on held-out split

This is the canonical "the protocol round-trips and the trained model still
works on round-tripped data" check.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit

from ml.src.baseline_rf import _build_X
from ml.src.raw_window import WindowAssembler, encode_window
from scripts.synth_dataset import build as build_synth


@pytest.fixture(scope="module")
def loopback_df(tmp_path_factory) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    src = build_synth(rng, sessions_per_class=3, windows_per_session=8)

    asm = WindowAssembler()
    received: list[dict] = []
    for i, row in src.iterrows():
        win_2d = np.asarray(row["window"], dtype=np.float32).reshape(-1, 3)
        for frame in encode_window(win_2d, window_seq=int(i) + 1):
            result = asm.push(frame)
            if result is not None:
                _seq, w = result
                received.append(
                    {
                        "window": w.flatten().astype(np.float32),
                        "class_label": row["class_label"],
                        "session_id": row["session_id"],
                    }
                )

    df = pd.DataFrame(received)
    # Round-trip via parquet so we exercise the read path used by load_dataset/_build_X.
    p = tmp_path_factory.mktemp("loop") / "loopback.parquet"
    df.to_parquet(p)
    return pd.read_parquet(p)


def test_all_windows_round_trip(loopback_df):
    expected = 4 * 3 * 8  # classes × sessions × windows
    assert len(loopback_df) == expected


def test_loopback_preserves_window_shape(loopback_df):
    first = np.asarray(loopback_df["window"].iloc[0], dtype=np.float32).reshape(-1, 3)
    assert first.shape == (256, 3)


def test_loopback_quantization_within_tolerance(loopback_df):
    # Original synth values, re-derived deterministically from the same seed.
    rng = np.random.default_rng(0)
    src = build_synth(rng, sessions_per_class=3, windows_per_session=8)

    for orig, recv in zip(src["window"], loopback_df["window"]):
        a = np.asarray(orig, dtype=np.float32).reshape(-1, 3)
        b = np.asarray(recv, dtype=np.float32).reshape(-1, 3)
        # int16 scale=1000 → max error ~ 5e-4 g
        assert np.max(np.abs(a - b)) < 2e-3


def test_rf_still_separates_after_loopback(loopback_df):
    X = _build_X(loopback_df)
    y = loopback_df["class_label"].to_numpy()
    groups = loopback_df["session_id"].to_numpy()

    train_idx, test_idx = next(
        GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42).split(X, y, groups=groups)
    )
    clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=1)
    clf.fit(X.iloc[train_idx], y[train_idx])
    acc = float(np.mean(clf.predict(X.iloc[test_idx]) == y[test_idx]))

    # The int16 round-trip loses very little; RF accuracy should stay well above chance.
    assert acc >= 0.80, f"accuracy after loopback was {acc:.3f}"
