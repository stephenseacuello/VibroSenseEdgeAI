"""Tests for the per-session parquet merger."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.src.merge_sessions import merge


def _make_session(path: Path, n_rows: int, label: str, sid: str) -> None:
    df = pd.DataFrame(
        {
            "window": [np.random.randn(256 * 3).astype(np.float32) for _ in range(n_rows)],
            "class_label": [label] * n_rows,
            "session_id": [sid] * n_rows,
        }
    )
    df.to_parquet(path)


def test_merges_multiple_sessions(tmp_path):
    src = tmp_path / "raw"
    src.mkdir()
    _make_session(src / "s_healthy.parquet",   5, "HEALTHY",   "ses-h")
    _make_session(src / "s_imbalance.parquet", 6, "IMBALANCE", "ses-i")

    out = tmp_path / "processed" / "dataset.parquet"
    man = tmp_path / "processed" / "manifest.json"
    manifest = merge(src, out, man)

    assert out.exists()
    assert man.exists()
    assert manifest["rows_total"] == 11
    assert manifest["session_count"] == 2
    assert manifest["class_counts"] == {"HEALTHY": 5, "IMBALANCE": 6}
    assert len(manifest["manifest_sha"]) == 64


def test_manifest_sha_is_stable_across_runs(tmp_path):
    src = tmp_path / "raw"
    src.mkdir()
    _make_session(src / "a.parquet", 3, "HEALTHY", "a")
    _make_session(src / "b.parquet", 3, "IMBALANCE", "b")

    m1 = merge(src, tmp_path / "out1.parquet", tmp_path / "man1.json")
    m2 = merge(src, tmp_path / "out2.parquet", tmp_path / "man2.json")
    assert m1["manifest_sha"] == m2["manifest_sha"]


def test_rejects_session_missing_required_columns(tmp_path):
    src = tmp_path / "raw"
    src.mkdir()
    pd.DataFrame({"window": [np.zeros(3, dtype=np.float32)]}).to_parquet(src / "bad.parquet")

    with pytest.raises(SystemExit):
        merge(src, tmp_path / "out.parquet", tmp_path / "man.json")


def test_no_sessions_is_an_error(tmp_path):
    src = tmp_path / "raw"
    src.mkdir()
    with pytest.raises(SystemExit):
        merge(src, tmp_path / "out.parquet", tmp_path / "man.json")


def test_merged_dataset_is_loadable(tmp_path):
    src = tmp_path / "raw"
    src.mkdir()
    _make_session(src / "s1.parquet", 4, "HEALTHY", "s1")
    _make_session(src / "s2.parquet", 4, "BEARING_FAULT", "s2")

    out = tmp_path / "dataset.parquet"
    merge(src, out, tmp_path / "manifest.json")

    loaded = pd.read_parquet(out)
    assert len(loaded) == 8
    assert set(loaded["class_label"]) == {"HEALTHY", "BEARING_FAULT"}
    # window column round-trips as flat float arrays
    first = np.asarray(loaded["window"].iloc[0])
    assert first.dtype == np.float32
    assert first.size == 256 * 3
