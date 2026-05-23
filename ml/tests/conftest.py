"""Shared ML test fixtures — synthetic dataset on demand."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from scripts.synth_dataset import build


@pytest.fixture(scope="session")
def synth_df():
    """Reasonably-sized synthetic dataset for pipeline tests (~400 windows)."""
    rng = np.random.default_rng(42)
    return build(rng, sessions_per_class=5, windows_per_session=20)


@pytest.fixture(scope="session")
def synth_parquet(tmp_path_factory, synth_df):
    out = tmp_path_factory.mktemp("ml") / "synth.parquet"
    synth_df.to_parquet(out)
    return out


@pytest.fixture(scope="session")
def tiny_synth_parquet(tmp_path_factory):
    """Even smaller dataset for CNN tests where wall-clock matters."""
    from scripts.synth_dataset import build as _b

    rng = np.random.default_rng(0)
    df = _b(rng, sessions_per_class=3, windows_per_session=8)
    out = tmp_path_factory.mktemp("ml-tiny") / "synth.parquet"
    df.to_parquet(out)
    return out
