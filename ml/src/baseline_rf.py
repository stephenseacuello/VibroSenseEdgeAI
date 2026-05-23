"""RandomForest baseline. Sanity-checks feature separability before committing to a CNN.

Usage:
    python -m ml.src.baseline_rf path/to/dataset.parquet
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit

from .features import window_features


def _build_X(df: pd.DataFrame) -> pd.DataFrame:
    # Windows are stored flat (parquet limitation); reshape back to (N, 3) here.
    return pd.DataFrame(
        [window_features(np.asarray(w, dtype=np.float32).reshape(-1, 3)) for w in df["window"]]
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("dataset", help="Parquet with columns: window, class_label, session_id")
    p.add_argument("--test-size", type=float, default=0.15)
    p.add_argument("--n-estimators", type=int, default=300)
    args = p.parse_args()

    df = pd.read_parquet(args.dataset)
    for col in ("window", "class_label", "session_id"):
        if col not in df.columns:
            print(f"missing required column: {col}", file=sys.stderr)
            return 1

    X = _build_X(df)
    y = df["class_label"].values
    groups = df["session_id"].values

    gss = GroupShuffleSplit(n_splits=1, test_size=args.test_size, random_state=42)
    train_idx, test_idx = next(gss.split(X, y, groups=groups))

    clf = RandomForestClassifier(n_estimators=args.n_estimators, random_state=42, n_jobs=-1)
    clf.fit(X.iloc[train_idx], y[train_idx])
    pred = clf.predict(X.iloc[test_idx])

    print(classification_report(y[test_idx], pred))
    print("Confusion matrix:")
    print(confusion_matrix(y[test_idx], pred))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
