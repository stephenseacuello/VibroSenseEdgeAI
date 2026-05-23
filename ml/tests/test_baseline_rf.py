"""End-to-end RandomForest baseline test against the synthetic dataset."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit

from ml.src.baseline_rf import _build_X


def test_rf_separates_synthetic_classes(synth_df):
    X = _build_X(synth_df)
    y = synth_df["class_label"].to_numpy()
    groups = synth_df["session_id"].to_numpy()

    train_idx, test_idx = next(
        GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42).split(X, y, groups=groups)
    )

    clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=1)
    clf.fit(X.iloc[train_idx], y[train_idx])
    pred = clf.predict(X.iloc[test_idx])
    acc = float(np.mean(pred == y[test_idx]))

    # Synthetic signatures are designed to be separable; a generous floor avoids flakiness.
    assert acc >= 0.85, f"RF accuracy on synthetic was {acc:.3f}"


def test_feature_matrix_has_no_nans(synth_df):
    X = _build_X(synth_df)
    assert not X.isna().any().any()
    # At least 90% of features should have non-zero variance across the dataset.
    # (A handful of features — e.g. az_dom_freq_hz where the only signal is gravity
    # plus low-amplitude noise — can be constant on synthetic data without issue.)
    has_variance = (X.var(numeric_only=True) > 0).mean()
    assert has_variance >= 0.90, f"only {has_variance:.0%} of features varied"
