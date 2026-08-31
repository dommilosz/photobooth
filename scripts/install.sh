#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
sudo apt-get update
sudo apt-get install -y \
  python3 python3-pip python3-venv \
  python3-opencv python3-pyqt5 python3-pyqt5.qtquick python3-pil python3-yaml \
  python3-requests python3-gpiozero python3-numpy \
  qtvirtualkeyboard-plugin qml-module-qtquick-virtualkeyboard \
  cups libcups2-dev v4l-utils

cd "$ROOT"
python3 scripts/generate_default_templates.py
python3 -m pip install -e .

sudo mkdir -p /var/lib/photobooth
sudo cp -r templates config "$ROOT/" 2>/dev/null || true

echo "Install CUPS printer via http://$(hostname -I | awk '{print $1}'):631"
echo "Enable photobooth: sudo cp systemd/photobooth.service /etc/systemd/system/"
echo "sudo systemctl enable --now photobooth"
