#!/usr/bin/env bash
# Idempotent provisioning of a fresh dev box (macOS or Linux) for firmware work.
#
# Installs:
#   - arduino-cli (if missing)
#   - Arduino mbed_nano core
#   - ArduinoBLE, Arduino_LSM9DS1, TFLite Micro Arduino libraries
#   - Mosquitto MQTT broker (so `make demo` works locally)
#
# Use `bootstrap_pi.sh` for a Pi gateway; this is for the laptop that flashes
# the Nano and runs ad-hoc dev.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

OS="$(uname -s)"

# --- system package manager ------------------------------------------------
if [[ "$OS" == "Darwin" ]]; then
    if ! command -v brew >/dev/null 2>&1; then
        echo "Homebrew not found. Install from https://brew.sh first." >&2
        exit 1
    fi
    PKG_INSTALL="brew install"
elif [[ "$OS" == "Linux" ]]; then
    PKG_INSTALL="sudo apt-get install -y"
    sudo apt-get update
else
    echo "Unsupported OS: $OS" >&2
    exit 1
fi

# --- arduino-cli -----------------------------------------------------------
if ! command -v arduino-cli >/dev/null 2>&1; then
    echo "==> installing arduino-cli"
    $PKG_INSTALL arduino-cli
fi

echo "==> Arduino core + libraries"
arduino-cli core update-index
arduino-cli core install arduino:mbed_nano
arduino-cli lib install ArduinoBLE
arduino-cli lib install "Arduino_LSM9DS1"

echo "==> TFLite Micro for Arduino"
# Try the official examples lib first; fall back to Chirale's port.
if ! arduino-cli lib list 2>/dev/null | grep -qi "Chirale_TensorFlowLite\|TensorFlowLite"; then
    arduino-cli lib install --git-url https://github.com/tensorflow/tflite-micro-arduino-examples \
        || arduino-cli lib install "Chirale_TensorFlowLite"
fi

# --- Mosquitto (so `make demo` runs end-to-end on this machine) ------------
if ! command -v mosquitto >/dev/null 2>&1; then
    echo "==> installing Mosquitto"
    $PKG_INSTALL mosquitto
fi

# --- Python venv -----------------------------------------------------------
echo "==> Python venv + project deps"
if [[ ! -d .venv ]]; then
    python3 -m venv .venv
fi
. .venv/bin/activate
pip install -U pip
pip install -e ".[dev,hardware]"
pre-commit install || true

# --- Verify ----------------------------------------------------------------
echo
echo "==> sanity checks"
arduino-cli board list | head -20 || true
arduino-cli compile --fqbn arduino:mbed_nano:nano33ble firmware/nano33 \
    --warnings none 2>&1 | tail -5

echo
echo "==> done. Next:"
echo "    1. Plug in the Nano 33 BLE Sense"
echo "    2. arduino-cli board list   # find the port"
echo "    3. PORT=/dev/cu.usbmodemXXXX make flash"
echo "    4. make demo                # in another terminal, after Mosquitto is up"
