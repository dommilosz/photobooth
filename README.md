# Photobooth

Raspberry Pi Zero 2W photobooth with USB webcam, GPIO flash, template-based printing, and Nextcloud upload.

## Quick start (Windows dev)

```powershell
cd photobooth
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python scripts\generate_default_templates.py
python -m photobooth.main --mock --dev
```

## Quick start (Raspberry Pi)

```bash
git clone <repo> /opt/photobooth
cd /opt/photobooth
chmod +x scripts/*.sh
./scripts/install.sh
./scripts/photobooth-launch.sh
```

## Features

- Live camera preview (OpenCV / V4L2, MJPEG 640×480)
- GPIO flash lamp control (relay/MOSFET on BCM 17)
- 4 print layout templates (PNG with transparent photo slots)
- Auto slot detection from template alpha channel
- CUPS dye-sub printing (or file output in `--dev` mode)
- Nextcloud File Request upload via WebDAV
- Touch-friendly PyQt5 UI with layout picker

## CLI

```
python -m photobooth.main [--mock] [--dev] [-v]
```

- `--mock` — animated test camera (no hardware)
- `--dev` — save prints to disk, skip live Nextcloud (use mock upload unless upload enabled)

## Templates

Place `my_layout.png` + `my_layout.meta.yaml` in `templates/`. See [docs/templates.md](docs/templates.md).

## Configuration

Edit `config/default.yaml` — event name, layout mode, flash GPIO, printer queue, Nextcloud share URL.
