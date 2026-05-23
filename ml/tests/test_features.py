import numpy as np

from ml.src.features import freq_features, time_features, window_features


def test_time_features_constant_signal():
    x = np.ones(256, dtype=np.float32)
    f = time_features(x)
    assert f["rms"] == 1.0
    assert f["peak"] == 1.0
    assert f["p2p"] == 0.0


def test_freq_features_locates_known_sine():
    fs = 1000.0
    n = 1024
    t = np.arange(n) / fs
    x = np.sin(2 * np.pi * 50.0 * t).astype(np.float32)
    f = freq_features(x, fs)
    assert 40 <= f["dom_freq_hz"] <= 60


def test_window_features_covers_all_axes():
    w = np.random.randn(256, 3).astype(np.float32)
    f = window_features(w)
    assert any(k.startswith("ax_") for k in f)
    assert any(k.startswith("ay_") for k in f)
    assert any(k.startswith("az_") for k in f)
    # one of the FFT bin features for ax should exist
    assert "ax_fft_bin_0" in f
