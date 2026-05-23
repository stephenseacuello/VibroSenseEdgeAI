"""BLE-streamed raw-window capture tool.

Connects to the Nano, switches it to CAPTURE mode, subscribes to the
`raw_window` notify characteristic (ADR-0004), reassembles chunks into
complete (N, 3) IMU windows, runs the inline data-quality checks from
PROJECT_PLAN.md §9.4, and writes a parquet that the training scripts can
consume directly.

Usage:
    python -m ml.src.capture --class-label HEALTHY --operator amuszynski \
        --speed 2 --duration-s 300 --notes "workbench A, oscillation off"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .raw_window import WindowAssembler

# bleak imported lazily inside capture() — keeps quality_check importable on
# CI runners that don't have the platform BLE stack.

DEVICE_NAME = "VibroSense-Nano"
# Must match firmware/nano33/src/ble_service.cpp and ADR-0001.
MODE_UUID = "7e5c0001-d9b7-4f12-8a6b-0a0b0c0d0e11"
RAW_WINDOW_UUID = "7e5c0001-d9b7-4f12-8a6b-0a0b0c0d0e13"

OUT_DIR = Path("ml/data/raw")


@dataclass
class SessionMeta:
    session_id: str
    capture_date_utc: str
    operator: str
    asset_id: str
    class_label: str
    speed_setting: int
    ambient_notes: str
    fault_params: dict[str, Any] = field(default_factory=dict)
    sample_rate_hz: int = 952
    window_size: int = 256
    firmware_sha: str = "unknown"


def quality_check(windows: np.ndarray) -> tuple[bool, list[str]]:
    """Inline checks per PROJECT_PLAN.md §9.4.

    `windows` shape: (num_windows, window_size, 3).
    """
    issues: list[str] = []
    if windows.size == 0:
        return False, ["no data"]
    if not np.isfinite(windows).all():
        issues.append("non-finite samples present")

    gravity_mean = float(np.mean(np.abs(windows[..., 2])))
    if not (0.7 <= gravity_mean <= 1.3):
        issues.append(f"gravity-axis mean |a_z|={gravity_mean:.2f} g outside [0.7, 1.3]")

    clip_rate = float(np.mean(np.abs(windows) >= 3.95))  # LSM9DS1 default ±4g
    if clip_rate > 1e-3:
        issues.append(f"clipping rate {clip_rate:.2%} > 0.1%")

    if len(windows) < 60:  # ≈ 3 min at 256-sample windows, 952 Hz
        issues.append("session under 3 min")

    return (len(issues) == 0, issues)


async def capture(args: argparse.Namespace) -> int:
    from bleak import BleakClient, BleakScanner  # lazy: see module-level note

    print(f"scanning for {DEVICE_NAME}...", file=sys.stderr)
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=15)
    if device is None:
        print("device not found", file=sys.stderr)
        return 1

    assembler = WindowAssembler()
    windows: list[np.ndarray] = []
    window_seqs: list[int] = []

    async with BleakClient(device) as client:
        await client.write_gatt_char(MODE_UUID, bytes([1]))  # → CAPTURE

        def _on_chunk(_: int, data: bytearray) -> None:
            result = assembler.push(bytes(data))
            if result is not None:
                seq, w = result
                windows.append(w)
                window_seqs.append(seq)

        await client.start_notify(RAW_WINDOW_UUID, _on_chunk)
        deadline = time.time() + args.duration_s
        last_print = 0.0
        while time.time() < deadline:
            await asyncio.sleep(0.5)
            if time.time() - last_print > 5.0:
                print(
                    f"  captured {len(windows)} windows "
                    f"({assembler.pending()} in-flight)",
                    file=sys.stderr,
                )
                last_print = time.time()
        await client.stop_notify(RAW_WINDOW_UUID)
        await client.write_gatt_char(MODE_UUID, bytes([0]))  # back to INFER

    if not windows:
        print("no windows assembled — check firmware advertising raw_window", file=sys.stderr)
        return 1

    stacked = np.stack(windows)  # (num_windows, N, 3)
    ok, issues = quality_check(stacked)
    if not ok:
        print("data quality check FAILED:", file=sys.stderr)
        for i in issues:
            print(f"  - {i}", file=sys.stderr)
        if not args.force:
            return 2
        print("  (continuing because --force was given)", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    sid = f"{stamp}_{args.class_label}_speed-{args.speed}_{args.operator}"
    meta = SessionMeta(
        session_id=sid,
        capture_date_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        operator=args.operator,
        asset_id=args.asset_id,
        class_label=args.class_label,
        speed_setting=args.speed,
        ambient_notes=args.notes,
        fault_params=json.loads(args.fault_params) if args.fault_params else {},
        window_size=int(stacked.shape[1]),
    )
    (OUT_DIR / f"{sid}.meta.json").write_text(json.dumps(asdict(meta), indent=2))

    # Flatten each (N, 3) window to (N*3,) for parquet compatibility; readers reshape.
    df = pd.DataFrame(
        {
            "window": [w.flatten().astype(np.float32) for w in stacked],
            "class_label": [args.class_label] * len(stacked),
            "session_id": [sid] * len(stacked),
            "window_seq": window_seqs,
        }
    )
    df.to_parquet(OUT_DIR / f"{sid}.parquet")
    print(f"wrote {OUT_DIR / sid}.parquet ({len(df)} windows)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--class-label",
        required=True,
        choices=("HEALTHY", "IMBALANCE", "LOOSENESS", "BEARING_FAULT"),
    )
    p.add_argument("--operator", required=True)
    p.add_argument("--asset-id", default="fan-01")
    p.add_argument("--speed", type=int, required=True)
    p.add_argument("--duration-s", type=int, default=300)
    p.add_argument("--notes", default="")
    p.add_argument(
        "--fault-params", default="", help="JSON string, e.g. '{\"mass_g\": 1.0}'"
    )
    p.add_argument("--force", action="store_true", help="save even if quality checks fail")
    args = p.parse_args()
    return asyncio.run(capture(args))


if __name__ == "__main__":
    raise SystemExit(main())
