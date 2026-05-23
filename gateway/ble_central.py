"""BLE-central subscriber: bleak → MQTT publish.

Subscribes to the Nano's `state` characteristic, annotates each message with
`asset_id` + `ts_utc`, validates against the schema, and publishes to MQTT.
Tracks `seq` continuity per asset so dropped notifies surface as warnings —
useful for ATP-03 (BLE link reliability). Auto-reconnects on link drop.

See PROJECT_PLAN.md §12 and ATP-03 / ATP-06.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from dataclasses import dataclass
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from ml.src.schema import StateV1

# bleak imported lazily inside run() — keeps this module testable on platforms
# where the BLE stack is unavailable (e.g. CI runners without bluez).

DEVICE_NAME = os.environ.get("VIBROSENSE_DEVICE_NAME", "VibroSense-Nano")
# Must match firmware/nano33/src/ble_service.cpp and ADR-0001.
STATE_UUID = "7e5c0001-d9b7-4f12-8a6b-0a0b0c0d0e10"
ASSET_ID = os.environ.get("VIBROSENSE_ASSET_ID", "fan-01")
MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

log = logging.getLogger("ble_central")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class SeqStats:
    """Per-asset sequence-gap accounting (ATP-03)."""

    expected_next: int | None = None
    received: int = 0
    missed: int = 0

    def observe(self, seq: int) -> int:
        """Update counters for an incoming seq. Returns the gap size (0 if continuous)."""
        gap = 0
        if self.expected_next is not None and seq != self.expected_next:
            # Allow reset on a device reboot (seq jumps back to 1).
            if seq < self.expected_next:
                log.info("seq reset detected (was %s, got %s) — assuming device reboot",
                         self.expected_next, seq)
            else:
                gap = seq - self.expected_next
                self.missed += gap
                log.warning(
                    "BLE seq gap on asset: missed %d notify(s) (expected %s, got %s)",
                    gap, self.expected_next, seq,
                )
        self.received += 1
        self.expected_next = seq + 1
        return gap

    def loss_rate(self) -> float:
        total = self.received + self.missed
        return self.missed / total if total else 0.0


async def run() -> None:
    from bleak import BleakClient, BleakScanner  # lazy: see module-level note

    mqttc = mqtt.Client(client_id="ble_central",
                        callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    mqttc.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    mqttc.loop_start()

    topic = f"pdm/{ASSET_ID}/state"
    stats = SeqStats()

    async def report_stats():
        while True:
            await asyncio.sleep(60)
            if stats.received:
                log.info(
                    "ATP-03 metric: %d/%d notifies received (loss=%.3f%%)",
                    stats.received, stats.received + stats.missed, stats.loss_rate() * 100,
                )

    stats_task = asyncio.create_task(report_stats())

    while True:
        log.info("scanning for %s", DEVICE_NAME)
        device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=20)
        if device is None:
            log.warning("device not found; retrying in 5s")
            await asyncio.sleep(5)
            continue

        try:
            async with BleakClient(device) as client:
                log.info("connected to %s", device.address)

                def _on_notify(_: int, data: bytearray) -> None:
                    try:
                        payload = json.loads(data.decode())
                        payload["asset_id"] = ASSET_ID
                        payload["ts_utc"] = _iso_now()
                        StateV1(**payload)
                        stats.observe(int(payload["seq"]))
                        mqttc.publish(topic, json.dumps(payload), qos=0)
                    except Exception as exc:  # noqa: BLE001
                        log.exception("bad notify: %s", exc)

                await client.start_notify(STATE_UUID, _on_notify)
                while client.is_connected:
                    await asyncio.sleep(1)
                log.warning("BLE disconnected; will reconnect")
        except Exception as exc:  # noqa: BLE001
            log.exception("BLE session error: %s", exc)
            await asyncio.sleep(2)

    stats_task.cancel()  # unreachable; here for shape


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, loop.stop)
        except NotImplementedError:
            pass  # Windows
    try:
        loop.run_until_complete(run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
