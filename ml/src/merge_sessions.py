"""Merge per-session capture parquets into a single training dataset + manifest.

Each capture session lives in `ml/data/raw/{session_id}.parquet`. Training
scripts (`train_cnn.py`, `baseline_rf.py`, `eval.py`) consume a single parquet,
so this tool concatenates the per-session files and writes a JSON manifest
that pins the dataset SHA — that SHA goes into every experiment-log entry
per PROJECT_PLAN.md §10.5.

Usage:
    python -m ml.src.merge_sessions
    python -m ml.src.merge_sessions --src ml/data/raw --out ml/data/processed/dataset.parquet
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

REQUIRED_COLS = ("window", "class_label", "session_id")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def merge(src_dir: Path, out_path: Path, manifest_path: Path) -> dict:
    parquets = sorted(src_dir.glob("*.parquet"))
    if not parquets:
        raise SystemExit(f"no .parquet files in {src_dir}")

    dfs: list[pd.DataFrame] = []
    sessions: list[dict] = []
    for pq in parquets:
        df = pd.read_parquet(pq)
        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            raise SystemExit(f"{pq.name} missing required columns: {missing}")
        sessions.append(
            {
                "session": pq.name,
                "rows": int(len(df)),
                "classes": sorted(df["class_label"].unique().tolist()),
                "sha256": file_sha256(pq),
            }
        )
        dfs.append(df)

    merged = pd.concat(dfs, ignore_index=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out_path)

    # Combined manifest SHA derives from the per-session SHAs (sorted),
    # so the dataset SHA is stable regardless of FS ordering.
    sha_blob = "\n".join(s["sha256"] for s in sorted(sessions, key=lambda s: s["session"]))
    manifest = {
        "dataset": str(out_path),
        "rows_total": int(len(merged)),
        "class_counts": {
            str(k): int(v) for k, v in merged["class_label"].value_counts().items()
        },
        "session_count": len(sessions),
        "sessions": sessions,
        "manifest_sha": hashlib.sha256(sha_blob.encode()).hexdigest(),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--src", default="ml/data/raw", help="dir of session parquets")
    p.add_argument("--out", default="ml/data/processed/dataset.parquet")
    p.add_argument("--manifest", default="ml/data/processed/manifest.json")
    args = p.parse_args()

    manifest = merge(Path(args.src), Path(args.out), Path(args.manifest))
    print(f"merged {manifest['session_count']} sessions "
          f"({manifest['rows_total']} rows) → {args.out}")
    print(f"manifest_sha: {manifest['manifest_sha']}")
    print(f"class counts: {manifest['class_counts']}")
    if len(manifest["class_counts"]) < 4:
        print("WARNING: not all 4 classes present; training will fail or be skewed.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
