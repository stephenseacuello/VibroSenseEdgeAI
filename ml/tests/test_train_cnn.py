"""1D-CNN training smoke test — gated by TensorFlow being installed.

Trains for a small number of epochs on the synthetic dataset and asserts the
pipeline produces a saved model file. Accuracy is not gated here because the
network is intentionally tiny and the dataset small; eval gating is in
`ml/src/eval.py` against real data.
"""

from __future__ import annotations

import pytest

tf = pytest.importorskip("tensorflow")  # noqa: F841 — skip the module if TF missing


def test_build_model_shapes():
    from ml.src.train_cnn import build_model

    m = build_model(window_size=256, channels=3, n_classes=4)
    assert m.input_shape == (None, 256, 3)
    assert m.output_shape == (None, 4)


def test_train_smoke(tiny_synth_parquet, tmp_path):
    from ml.src.train_cnn import build_model, load_dataset, session_stratified_split

    X, y, groups = load_dataset(tiny_synth_parquet)
    train_mask, test_mask = session_stratified_split(groups, test_frac=0.25, seed=1)
    assert train_mask.sum() > 0 and test_mask.sum() > 0

    model = build_model(window_size=X.shape[1])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.fit(X[train_mask], y[train_mask], epochs=2, batch_size=16, verbose=0)

    out = tmp_path / "tiny.keras"
    model.save(out)
    assert out.exists() and out.stat().st_size > 0


def test_session_stratified_no_leakage(tiny_synth_parquet):
    from ml.src.train_cnn import load_dataset, session_stratified_split

    _, _, groups = load_dataset(tiny_synth_parquet)
    train_mask, test_mask = session_stratified_split(groups, test_frac=0.34, seed=7)
    train_sessions = set(groups[train_mask].tolist())
    test_sessions = set(groups[test_mask].tolist())
    assert train_sessions.isdisjoint(test_sessions), "session bled across splits"
