"""Bridge schema-validation tests. The bridge thread itself runs forever, so we
exercise the validators directly — that's where the contract is enforced."""

from __future__ import annotations

import json

from app.mqtt_bridge import validate_alarm, validate_payload, validate_state


def test_valid_payload_passes_through():
    msg = {
        "schema_ver": 1,
        "asset_id": "fan-01",
        "ts_utc": "2026-07-15T14:30:00.000Z",
        "seq": 7,
        "state": "IMBALANCE",
        "confidence": 0.81,
    }
    out = validate_payload(json.dumps(msg).encode())
    assert out is not None
    assert out["state"] == "IMBALANCE"


def test_bad_class_label_dropped():
    msg = {
        "schema_ver": 1,
        "seq": 1,
        "state": "NOT_A_CLASS",
        "confidence": 0.9,
    }
    assert validate_payload(json.dumps(msg).encode()) is None


def test_confidence_out_of_range_dropped():
    msg = {
        "schema_ver": 1,
        "seq": 1,
        "state": "HEALTHY",
        "confidence": 1.5,
    }
    assert validate_payload(json.dumps(msg).encode()) is None


def test_non_json_dropped():
    assert validate_payload(b"this is not json") is None


def test_missing_required_field_dropped():
    msg = {"schema_ver": 1, "state": "HEALTHY", "confidence": 0.5}  # no seq
    assert validate_payload(json.dumps(msg).encode()) is None


def test_validate_payload_alias_for_state():
    """validate_payload kept as an alias of validate_state for back-compat."""
    assert validate_payload is validate_state


# Alarm validation ---------------------------------------------------------

def test_valid_alarm_passes():
    msg = {
        "schema_ver": 1,
        "asset_id": "fan-01",
        "ts_utc": "2026-07-15T14:30:01Z",
        "from": "HEALTHY",
        "to": "IMBALANCE",
        "confidence": 0.91,
    }
    out = validate_alarm(json.dumps(msg).encode())
    assert out is not None
    assert out["to"] == "IMBALANCE"


def test_alarm_first_transition_with_null_from():
    msg = {
        "schema_ver": 1,
        "asset_id": "fan-01",
        "ts_utc": "2026-07-15T14:30:00Z",
        "from": None,
        "to": "HEALTHY",
        "confidence": 0.7,
    }
    out = validate_alarm(json.dumps(msg).encode())
    assert out is not None


def test_alarm_bad_to_state_dropped():
    msg = {
        "schema_ver": 1,
        "asset_id": "fan-01",
        "ts_utc": "2026-07-15T14:30:01Z",
        "from": "HEALTHY",
        "to": "WAT",
        "confidence": 0.91,
    }
    assert validate_alarm(json.dumps(msg).encode()) is None


def test_alarm_missing_to_dropped():
    msg = {
        "schema_ver": 1,
        "asset_id": "fan-01",
        "ts_utc": "2026-07-15T14:30:01Z",
        "from": "HEALTHY",
        "confidence": 0.91,
    }
    assert validate_alarm(json.dumps(msg).encode()) is None
