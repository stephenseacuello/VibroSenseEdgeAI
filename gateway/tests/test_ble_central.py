"""Tests for the BLE-central → MQTT publisher.

We don't bring up a real BLE adapter; we drive the notify-handling logic by
recreating its closure with stub MQTT and asserting what gets published.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone


def _build_handler(published, asset_id="fan-01"):
    """Recreate ble_central.run()'s `_on_notify` against a stub MQTT publisher."""

    class StubMqtt:
        def publish(self, topic, payload, qos):
            published.append((topic, payload, qos))

    mqttc = StubMqtt()
    topic = f"pdm/{asset_id}/state"

    from ml.src.schema import StateV1

    def iso_now() -> str:
        return (
            datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )

    def _on_notify(_, data: bytearray):
        try:
            payload = json.loads(data.decode())
            payload["asset_id"] = asset_id
            payload["ts_utc"] = iso_now()
            StateV1(**payload)
            mqttc.publish(topic, json.dumps(payload), qos=0)
        except Exception:
            pass  # drop bad payloads silently

    return _on_notify


def test_valid_notify_is_published():
    pub = []
    h = _build_handler(pub)
    raw = json.dumps(
        {"schema_ver": 1, "ts_ms": 12345, "seq": 7, "state": "IMBALANCE", "confidence": 0.81}
    ).encode()

    h(0, bytearray(raw))

    assert len(pub) == 1
    topic, payload, qos = pub[0]
    assert topic == "pdm/fan-01/state"
    assert qos == 0
    msg = json.loads(payload)
    # gateway annotated:
    assert msg["asset_id"] == "fan-01"
    assert "ts_utc" in msg
    # firmware fields preserved:
    assert msg["seq"] == 7
    assert msg["state"] == "IMBALANCE"


def test_bad_state_label_dropped():
    pub = []
    h = _build_handler(pub)
    raw = json.dumps(
        {"schema_ver": 1, "ts_ms": 1, "seq": 1, "state": "NOT_A_CLASS", "confidence": 0.9}
    ).encode()

    h(0, bytearray(raw))
    assert pub == []


def test_confidence_out_of_range_dropped():
    pub = []
    h = _build_handler(pub)
    raw = json.dumps(
        {"schema_ver": 1, "ts_ms": 1, "seq": 1, "state": "HEALTHY", "confidence": 2.0}
    ).encode()

    h(0, bytearray(raw))
    assert pub == []


def test_non_json_dropped():
    pub = []
    h = _build_handler(pub)
    h(0, bytearray(b"not json"))
    assert pub == []


# SeqStats: per-asset BLE sequence gap accounting (ATP-03) -----------------

def test_seq_stats_no_gap_on_continuous():
    from gateway.ble_central import SeqStats

    s = SeqStats()
    for n in range(1, 11):
        assert s.observe(n) == 0
    assert s.received == 10
    assert s.missed == 0
    assert s.loss_rate() == 0.0


def test_seq_stats_counts_gap():
    from gateway.ble_central import SeqStats

    s = SeqStats()
    s.observe(1)
    s.observe(2)
    gap = s.observe(7)        # skipped 3, 4, 5, 6 → gap = 4
    assert gap == 4
    assert s.missed == 4
    assert s.received == 3
    # loss rate = missed / (received + missed)
    assert abs(s.loss_rate() - 4 / 7) < 1e-9


def test_seq_stats_handles_device_reboot():
    from gateway.ble_central import SeqStats

    s = SeqStats()
    for n in range(1, 6):
        s.observe(n)
    # device reboot → seq resets to 1; we treat this as a reset, not a gap
    s.observe(1)
    assert s.missed == 0
    s.observe(2)
    assert s.missed == 0
