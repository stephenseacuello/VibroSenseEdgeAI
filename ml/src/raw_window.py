"""Binary protocol for streaming raw IMU windows over BLE.

See ADR-0004 (docs/decisions/0004-raw-window-protocol.md) for the wire format.
The encoder is used in tests and by anything that needs to feed the assembler
without real hardware; the firmware encoder is the canonical producer in C++.
"""

from __future__ import annotations

import struct
import time
from typing import Iterator

import numpy as np

HEADER_FMT = "<IBBH"  # window_seq u32 · chunk_idx u8 · total_chunks u8 · samples_in_chunk u16
HEADER_SIZE = struct.calcsize(HEADER_FMT)
assert HEADER_SIZE == 8

SAMPLES_PER_CHUNK = 32
SAMPLE_SCALE = 1000.0  # int16 = round(g * SAMPLE_SCALE); 1.0 g → 1000
INT16_MIN, INT16_MAX = -32768, 32767

INCOMPLETE_TTL_S = 5.0  # drop partially-received windows after this many seconds


def encode_window(window: np.ndarray, window_seq: int) -> list[bytes]:
    """Encode an (N, 3) float array of g-values into chunked BLE frames.

    The decoder in `WindowAssembler.push()` reverses this exactly.
    """
    if window.ndim != 2 or window.shape[1] != 3:
        raise ValueError(f"window must be (N, 3); got {window.shape}")
    n = window.shape[0]
    total_chunks = (n + SAMPLES_PER_CHUNK - 1) // SAMPLES_PER_CHUNK
    if total_chunks > 255:
        raise ValueError(f"window too large: {n} samples → {total_chunks} chunks (max 255)")

    out: list[bytes] = []
    for idx in range(total_chunks):
        start = idx * SAMPLES_PER_CHUNK
        end = min(start + SAMPLES_PER_CHUNK, n)
        samples = end - start
        scaled = np.clip(
            np.round(window[start:end] * SAMPLE_SCALE), INT16_MIN, INT16_MAX
        ).astype("<i2")
        header = struct.pack(HEADER_FMT, window_seq, idx, total_chunks, samples)
        out.append(header + scaled.tobytes(order="C"))
    return out


class WindowAssembler:
    """Reassembles chunks into complete windows.

    Push frames as they arrive via `push(frame)`. On every push that completes a
    window the method returns `(window_seq, np.ndarray (N, 3) float32 g-values)`.
    Otherwise it returns None. Incomplete windows older than `ttl_s` are
    discarded on the next `push()` call to bound memory.
    """

    def __init__(self, ttl_s: float = INCOMPLETE_TTL_S, now=time.monotonic):
        self._buf: dict[int, dict] = {}
        self._ttl_s = ttl_s
        self._now = now  # injectable for tests

    def push(self, frame: bytes) -> tuple[int, np.ndarray] | None:
        if len(frame) < HEADER_SIZE:
            return None

        window_seq, chunk_idx, total_chunks, samples = struct.unpack(
            HEADER_FMT, frame[:HEADER_SIZE]
        )
        payload = frame[HEADER_SIZE:]
        expected_payload = samples * 3 * 2
        if len(payload) != expected_payload:
            return None
        if chunk_idx >= total_chunks:
            return None

        ints = np.frombuffer(payload, dtype="<i2").reshape(samples, 3)

        # GC before touching state so a chunk arriving for a stale-but-existing
        # window_seq creates a fresh entry instead of being silently evicted.
        self._gc()

        entry = self._buf.get(window_seq)
        if entry is None or entry["total"] != total_chunks:
            entry = self._buf[window_seq] = {
                "total": total_chunks,
                "chunks": {},
                "first_seen": self._now(),
            }
        entry["chunks"][chunk_idx] = ints

        if len(entry["chunks"]) == total_chunks:
            parts = [entry["chunks"][i] for i in range(total_chunks)]
            window_int = np.concatenate(parts, axis=0)
            del self._buf[window_seq]
            return window_seq, (window_int.astype(np.float32) / SAMPLE_SCALE)
        return None

    def _gc(self) -> None:
        now = self._now()
        stale = [k for k, v in self._buf.items() if now - v["first_seen"] > self._ttl_s]
        for k in stale:
            del self._buf[k]

    def pending(self) -> int:
        return len(self._buf)


def iter_assemble(frames: list[bytes]) -> Iterator[tuple[int, np.ndarray]]:
    """Convenience: push every frame through a fresh assembler, yielding completes."""
    asm = WindowAssembler()
    for f in frames:
        result = asm.push(f)
        if result is not None:
            yield result
