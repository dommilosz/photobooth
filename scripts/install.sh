#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
sudo apt-get update
sudo apt-get install -y \
  python3 python3-pip python3-venv \
  python3-opencv python3-pyqt5 python3-pil python3-yaml \
  python3-requests python3-gpiozero python3-numpy \
  cups libcups2-dev v4l-utils network-manager

cd "$ROOT"
python3 scripts/generate_default_templates.py
python3 -m pip install -e .

# Wi-Fi + power actions from the System settings panel
if id -u pi >/dev/null 2>&1; then
  sudo usermod -aG netdev,video pi || true
fi
if [[ -d /etc/sudoers.d ]]; then
  echo 'pi ALL=(ALL) NOPASSWD: /bin/systemctl reboot, /bin/systemctl poweroff, /sbin/reboot, /sbin/poweroff, /usr/bin/systemctl reboot, /usr/bin/systemctl poweroff' \
    | sudo tee /etc/sudoers.d/photobooth-power >/dev/null
  sudo chmod 440 /etc/sudoers.d/photobooth-power
fi

sudo mkdir -p /var/lib/photobooth
sudo cp -r templates config "$ROOT/" 2>/dev/null || true

echo "Install CUPS printer via http://$(hostname -I | awk '{print $1}'):631"
echo "Enable photobooth: sudo cp systemd/photobooth.service /etc/systemd/system/"
echo "sudo systemctl enable --now photobooth"
