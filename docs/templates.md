# Custom print templates

## Requirements

- PNG with **alpha channel** at **300 DPI**
- Exact print size: 1772×1181 px (15×10 cm) or 1181×1772 px (10×15 cm)
- Photo slots = **fully transparent** rectangles (alpha = 0) or **#88a201** marker rectangles
- **Strip** templates: one **5×15 cm** strip; the app tiles two copies edge-to-edge onto a **10×15 cm** print sheet
- **Full** templates: design the entire 10×15 cm sheet
- Opaque borders/graphics between slots (≥2 px gap)
- Slots ordered top-to-bottom, left-to-right for capture sequence

## Sidecar (`my_layout.meta.yaml`)

```yaml
name: "My Event"
capture_count: 4
slot_mapping: [0, 1, 2, 3]  # one index per slot on the template PNG
sheet_mm: [100, 150]
cups_media: "Postcard"
category: strip   # or full
```

- `capture_count` — how many photos to take per session
- `slot_mapping` — one index per detected slot on the template PNG (for strip layouts this is a single column; the print sheet duplicates it side by side)
- `cups_media` — for Selphy use `Postcard` only. Do **not** use strip-half sizes like `w192h288` — CUPS will split one job into 2 pages.

## Install

1. Add `templates/my_layout.png` and `templates/my_layout.meta.yaml`
2. Settings → **Reload templates**
3. Select the new card in the layout picker

## Validate

Run slot detection:

```bash
PYTHONPATH=src python -c "
from photobooth.compose.template_registry import TemplateRegistry
from photobooth.config import load_config
r = TemplateRegistry(load_config())
s = r.load('my_layout')
print(len(s.slots), 'slots', 'valid=', s.valid, s.error)
"
```
