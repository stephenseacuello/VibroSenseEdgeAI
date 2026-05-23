#!/usr/bin/env bash
# End-to-end local demo against a real Nano. Mosquitto + persistence + BLE
# central + Flask app, all on one host. For development against the synthetic
# producer, use the sister repo: ../VibroSenseEdgeAI-demo.
set -euo pipefail

cd "$(cd "$(dirname "$0")/.." && pwd)"

# 1) Mosquitto
if ! pgrep -x mosquitto > /dev/null; then
    echo "==> starting Mosquitto"
    mosquitto -c gateway/mosquitto/mosquitto.conf -d
fi

# 2) venv
if [[ ! -d .venv ]]; then
    echo "run 'make setup' first" >&2
    exit 1
fi
. .venv/bin/activate

# 3) persistence subscriber
echo "==> starting mqtt → sqlite persister"
python -m gateway.mqtt_to_sqlite &
DB_PID=$!

# 4) BLE central — requires the Nano to be flashed and in range
echo "==> starting BLE central (looking for a VibroSense-Nano)"
python -m gateway.ble_central &
PROD_PID=$!

cleanup() {
    echo
    echo "==> stopping background processes"
    kill "$DB_PID" "$PROD_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# 5) Flask app (foreground)
echo "==> starting Flask app at http://localhost:5000"
python -m app.app
