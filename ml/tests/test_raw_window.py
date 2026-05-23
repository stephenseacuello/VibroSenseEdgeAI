"""Round-trip tests for the raw_window binary protocol (ADR-0004)."""

from __future__ import annotations

import random

import numpy as np
import pytest

from ml.src.raw_window import (
    HEADER_SIZE,
    SAMPLES_PER_CHUNK,
    WindowAssembler,
    encode_window,
    iter_assemble,
)


def _make_window(n: int = 256, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    w = rng.standard_normal((n, 3)).astype(np.float32) * 0.5
    w[:, 2] += 1.0  # gravity on z
    return w


def test_round_trip_256_window():
    w = _make_window()
    frames = encode_window(w, window_seq=42)
    assert len(frames) == 256 // SAMPLES_PER_CHUNK == 8

    asm = WindowAssembler()
    out = None
    for f in frames:
        out = asm.push(f)
    assert out is not None
    seq, w2 = out
    assert seq == 42
    assert w2.shape == w.shape
    # int16 scaling round-trip: tolerance ~ 1/SAMPLE_SCALE
    assert np.max(np.abs(w - w2)) < 2e-3


def test_round_trip_non_multiple_window():
    # 200 samples is not a multiple of 32 → last chunk smaller
    w = _make_window(n=200, seed=1)
    frames = encode_window(w, window_seq=7)
    expected_chunks = (200 + SAMPLES_PER_CHUNK - 1) // SAMPLES_PER_CHUNK  # 7
    assert len(frames) == expected_chunks

    completes = list(iter_assemble(frames))
    assert len(completes) == 1
    seq, w2 = completes[0]
    assert seq == 7
    assert w2.shape == (200, 3)


def test_chunks_arrive_out_of_order():
    w = _make_window()
    frames = encode_window(w, window_seq=99)
    shuffled = frames[:]
    random.Random(0).shuffle(shuffled)

    completes = list(iter_assemble(shuffled))
    assert len(completes) == 1
    seq, w2 = completes[0]
    assert seq == 99
    assert np.max(np.abs(w - w2)) < 2e-3


def test_interleaved_two_windows():
    a = _make_window(seed=2)
    b = _make_window(seed=3)
    fa = encode_window(a, window_seq=10)
    fb = encode_window(b, window_seq=11)
    # Interleave a's odd chunks and b's even chunks
    interleaved = []
    for i in range(max(len(fa), len(fb))):
        if i < len(fa):
            interleaved.append(fa[i])
        if i < len(fb):
            interleaved.append(fb[i])

    completes = dict(iter_assemble(interleaved))
    assert set(completes.keys()) == {10, 11}
    assert np.max(np.abs(a - completes[10])) < 2e-3
    assert np.max(np.abs(b - completes[11])) < 2e-3


def test_truncated_frame_returns_none():
    asm = WindowAssembler()
    assert asm.push(b"") is None
    assert asm.push(b"\x00" * (HEADER_SIZE - 1)) is None


def test_payload_length_mismatch_dropped():
    w = _make_window()
    frames = encode_window(w, window_seq=1)
    # corrupt one frame's payload length
    bad = frames[0][:-2]  # drop two bytes
    asm = WindowAssembler()
    assert asm.push(bad) is None  # rejected
    # The remaining good frames cannot complete the window
    for f in frames[1:]:
        assert asm.push(f) is None


def test_incomplete_windows_garbage_collected():
    # Inject a fake clock so we can time-travel past the TTL.
    t = [0.0]
    asm = WindowAssembler(ttl_s=1.0, now=lambda: t[0])

    w = _make_window()
    frames = encode_window(w, window_seq=5)

    # Push only the first 2 chunks → incomplete
    asm.push(frames[0])
    asm.push(frames[1])
    assert asm.pending() == 1

    # Advance past TTL and push something unrelated; GC runs.
    t[0] = 2.0
    asm.push(frames[0])  # this re-creates the entry (first_seen=2.0)
    # The stale entry from the old window_seq=5 is gone, but a new one is back.
    # Push one more chunk for the new lifetime and verify still pending.
    assert asm.pending() == 1
    t[0] = 4.0
    asm.push(frames[2])  # creates an entry too; first_seen = 4.0; old one GC'd
    # The previous entry (first_seen=2.0) is now stale (>1s old) → GC'd
    assert asm.pending() == 1


def test_oversized_window_rejected():
    # > 255 chunks not representable in total_chunks u8
    big = np.zeros((SAMPLES_PER_CHUNK * 256, 3), dtype=np.float32)
    with pytest.raises(ValueError):
        encode_window(big, window_seq=0)


def test_wrong_shape_rejected():
    with pytest.raises(ValueError):
        encode_window(np.zeros((256, 6), dtype=np.float32), window_seq=0)
    with pytest.raises(ValueError):
        encode_window(np.zeros(256, dtype=np.float32), window_seq=0)


def test_clipping_at_int16_range():
    # Values beyond ±32.767 g (impossible in practice) should clip safely.
    w = np.full((SAMPLES_PER_CHUNK, 3), 100.0, dtype=np.float32)
    frames = encode_window(w, window_seq=0)
    completes = list(iter_assemble(frames))
    assert len(completes) == 1
    _, w2 = completes[0]
    # 32767 / 1000 = 32.767
    assert np.allclose(w2, 32.767, atol=1e-3)
