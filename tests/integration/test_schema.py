"""Schema-conformance tests. See PROJECT_PLAN.md §14 and ATP-04."""

from __future__ import annotations

import pytest

from ml.src.schema import StateV1


def test_state_v1_round_trip():
    payload = {
        "schema_ver": 1,
        "asset_id": "fan-01",
        "ts_utc": "2026-07-15T14:30:00.123Z",
        "seq": 42,
        "state": "IMBALANCE",
        "confidence": 0.91,
    }
    obj = StateV1(**payload)
    assert obj.state == "IMBALANCE"
    assert obj.confidence == 0.91


def test_state_v1_rejects_bad_class():
    with pytest.raises(Exception):
        StateV1(schema_ver=1, seq=1, state="NOT_A_CLASS", confidence=0.9)


def test_state_v1_rejects_confidence_above_one():
    with pytest.raises(Exception):
        StateV1(schema_ver=1, seq=1, state="HEALTHY", confidence=1.5)


def test_state_v1_rejects_negative_confidence():
    with pytest.raises(Exception):
        StateV1(schema_ver=1, seq=1, state="HEALTHY", confidence=-0.1)


def test_state_v1_rejects_negative_seq():
    with pytest.raises(Exception):
        StateV1(schema_ver=1, seq=-1, state="HEALTHY", confidence=0.5)
