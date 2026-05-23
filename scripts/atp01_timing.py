"""ATP-01 — on-device inference latency measurement.

Reads `infer_us=NNNN` lines from the Nano serial port and reports
p50/p95/p99 latency in milliseconds. Pass/fail against the 250 ms p95 gate
from PROJECT_PLAN.md §2.2 (AC-2).

Requires the firmware to be built with -DDEBUG_TIMING=1:

    arduino-cli compile --fqbn arduino:mbed_nano:nano33ble firmware/nano33 \\
        --build-property "build.extra_flags=-DDEBUG_TIMING=1"

Usage:
    python scripts/atp01_timing.py --port /dev/cu.usbmodem14101 --duration-s 60
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from statistics import mean

try:
    import serial  # pyserial
except ImportError:
    print(
        "pyserial not installed. Run: pip install -e \".[hardware]\"\n"
        "(or: pip install pyserial)",
        file=sys.stderr,
    )
    raise SystemExit(1)

PATTERN = re.compile(r"infer_us=(\d+)")


def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    k = max(0, min(len(s) - 1, int(round(p / 100 * (len(s) - 1)))))
    return s[k]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="serial port, e.g. /dev/cu.usbmodem14101")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--duration-s", type=int, default=60)
    ap.add_argument("--target-ms", type=float, default=250.0, help="ATP-01 p95 target")
    args = ap.parse_args()

    samples_ms: list[float] = []
    print(f"reading from {args.port} for {args.duration_s} s ...", file=sys.stderr)
    try:
        with serial.Serial(args.port, args.baud, timeout=1) as ser:
            deadline = time.time() + args.duration_s
            while time.time() < deadline:
                line = ser.readline().decode(errors="ignore").strip()
                m = PATTERN.search(line)
                if m:
                    samples_ms.append(int(m.group(1)) / 1000.0)
    except serial.SerialException as exc:
        print(f"serial error: {exc}", file=sys.stderr)
        return 2

    if not samples_ms:
        print(
            "no `infer_us=` lines seen. Did you flash with -DDEBUG_TIMING=1?",
            file=sys.stderr,
        )
        return 1

    p50 = percentile(samples_ms, 50)
    p95 = percentile(samples_ms, 95)
    p99 = percentile(samples_ms, 99)
    print(f"N={len(samples_ms)}  min={min(samples_ms):.1f}ms  "
          f"mean={mean(samples_ms):.1f}ms  median={p50:.1f}ms")
    print(f"p95={p95:.1f}ms  p99={p99:.1f}ms  max={max(samples_ms):.1f}ms")
    verdict = "PASS" if p95 < args.target_ms else "FAIL"
    print(f"ATP-01 gate: p95 < {args.target_ms:.0f} ms — {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
