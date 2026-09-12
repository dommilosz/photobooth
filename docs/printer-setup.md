# Printer setup (Canon Selphy / dye-sub)

1. Install CUPS and Gutenprint (see `scripts/install.sh`).
2. For newer Selphy models, build **selphy_print** from https://git.shaftnet.org/gitea/slp/selphy_print
3. Open `http://<pi-ip>:631` → Add printer → USB → Canon SELPHY driver.
4. Enable **borderless** in PPD settings.
5. Set default media to **Postcard** (often the only size Selphy exposes).
6. Test: `lp -d Canon_SELPHY_CP1300 -o media=Postcard -o fit-to-page data/prints/test.jpg`
7. Set `print.cups_queue` in `config/default.yaml`. Templates use `cups_media: Postcard`.

**Note:** Do not send a new job while the printer is busy — Selphy can freeze.

If one sheet prints as **2 pages**, check JPEG has 300 DPI and `cups_media: Postcard` (not `w192h288`).
