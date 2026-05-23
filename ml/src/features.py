"""Time-domain and frequency-domain features per PROJECT_PLAN.md §10.1.

These features feed the RandomForest baseline and (optionally) augment the CNN.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import kurtosis, skew


def time_features(x: np.ndarray) -> dict[str, float]:
    """Time-domain stats for a single 1-D channel."""
    rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
    peak = float(np.max(np.abs(x)))
    p2p = float(np.max(x) - np.min(x))
    return {
        "rms": rms,
        "peak": peak,
        "p2p": p2p,
        "kurtosis": float(kurtosis(x, bias=False)),
        "crest": peak / rms if rms > 0 else 0.0,
        "skew": float(skew(x, bias=False)),
    }


def freq_features(x: np.ndarray, fs: float, n_bins: int = 16) -> dict[str, float]:
    """Low-resolution FFT bin energies + dominant frequency."""
    n = len(x)
    spec = np.abs(np.fft.rfft(x * np.hanning(n))) / n
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    bins = np.array_split(spec, n_bins)
    out = {f"fft_bin_{i}": float(b.sum()) for i, b in enumerate(bins)}
    # skip DC when picking the dominant frequency
    dom_idx = int(np.argmax(spec[1:]) + 1)
    out["dom_freq_hz"] = float(freqs[dom_idx])
    return out


def window_features(window: np.ndarray, fs: float = 952.0) -> dict[str, float]:
    """Per-axis (ax, ay, az) feature dict for one (N, 3) window."""
    out: dict[str, float] = {}
    for axis_name, idx in (("ax", 0), ("ay", 1), ("az", 2)):
        x = np.asarray(window[:, idx], dtype=np.float32)
        for k, v in time_features(x).items():
            out[f"{axis_name}_{k}"] = v
        for k, v in freq_features(x, fs).items():
            out[f"{axis_name}_{k}"] = v
    return out
