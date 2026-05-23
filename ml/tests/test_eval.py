"""Eval-script tests. Gated by TensorFlow."""

from __future__ import annotations

import pytest

tf = pytest.importorskip("tensorflow")


def _train_and_save(parquet, out_path, epochs: int = 8):
    """Train just enough that the synthetic dataset is separable."""
    import numpy as np
    from ml.src.train_cnn import build_model, load_dataset

    X, y, _g = load_dataset(parquet)
    model = build_model(window_size=X.shape[1])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-2),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.fit(X, y, epochs=epochs, batch_size=16, verbose=0)
    model.save(out_path)


def test_eval_report_structure(synth_parquet, tmp_path):
    from ml.src.eval import run_eval

    model_path = tmp_path / "m.keras"
    _train_and_save(synth_parquet, model_path, epochs=8)

    report = run_eval(model_path, synth_parquet)
    assert report.n_test > 0
    assert 0.0 <= report.accuracy <= 1.0
    assert set(report.per_class_recall) == {"HEALTHY", "IMBALANCE", "LOOSENESS", "BEARING_FAULT"}
    # 4×4 confusion matrix
    assert len(report.confusion_matrix) == 4
    assert all(len(row) == 4 for row in report.confusion_matrix)


def test_atp05_gate_logic_on_perfect_predictions(synth_parquet, monkeypatch, tmp_path):
    """If predictions are perfect, ATP-05 should pass."""
    import numpy as np
    from ml.src import eval as eval_mod

    model_path = tmp_path / "m.keras"
    _train_and_save(synth_parquet, model_path, epochs=1)

    # Monkey-patch the Keras prediction to return the ground truth, so we
    # exercise the report-and-gate pathway independent of model quality.
    def fake_predict_keras(_model_path, X):
        # We can't return labels here directly; instead patch run_eval's inner pred.
        # Easier: patch with the test split's actual labels via the helper.
        raise NotImplementedError

    # Instead, monkey-patch `_predict_keras` to return the matching ys for the test split.
    from ml.src.train_cnn import load_dataset, session_stratified_split

    X, y, groups = load_dataset(synth_parquet)
    _, test_mask = session_stratified_split(groups, test_frac=0.15, seed=42)
    yt = y[test_mask]

    monkeypatch.setattr(eval_mod, "_predict_keras", lambda mp, X: yt)

    report = eval_mod.run_eval(model_path, synth_parquet)
    assert report.accuracy == 1.0
    assert report.passes_atp05() is True
