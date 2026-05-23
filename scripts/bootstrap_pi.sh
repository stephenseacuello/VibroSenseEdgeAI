#!/usr/bin/env bash
# Idempotent provisioning of a fresh Raspberry Pi 4 as the VibroSense gateway.
# Re-runnable; safe to invoke after pulling a new commit.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "==> apt packages"
sudo apt-get update
sudo apt-get install -y \
    git \
    python3.11 python3.11-venv python3.11-dev \
    mosquitto mosquitto-clients \
    sqlite3 \
    bluetooth bluez \
    build-essential

echo "==> Mosquitto config"
sudo cp gateway/mosquitto/mosquitto.conf /etc/mosquitto/mosquitto.conf
sudo systemctl enable --now mosquitto

echo "==> Node-RED (official Pi installer; idempotent)"
if ! command -v node-red >/dev/null 2>&1; then
    bash <(curl -sL https://raw.githubusercontent.com/node-red/linux-installers/master/deb/update-nodejs-and-nodered) \
        --confirm-install --confirm-pi
fi
sudo systemctl enable --now nodered

echo "==> Python venv"
python3.11 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"

echo "==> systemd units"
sudo cp gateway/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vibrosense-mqtt2db vibrosense-ble vibrosense-app

echo "==> done. App at http://$(hostname -I | awk '{print $1}'):5000"
