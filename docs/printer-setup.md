# Printer setup (Canon Selphy / dye-sub)

1. Install CUPS and Gutenprint (see `scripts/install.sh`).
2. For newer Selphy models, build **selphy_print** from https://git.shaftnet.org/gitea/slp/selphy_print
3. Open `http://<pi-ip>:631` → Add printer → USB → Canon SELPHY driver.
4. Enable **borderless** in PPD settings.
5. Set default media to match your paper (15×10 cm landscape or 10×15 cm portrait).
6. Test: `lp -d Canon_SELPHY_CP1300 data/prints/test.jpg`
7. Set `print.cups_queue` in `config/default.yaml`.

**Note:** Do not send a new job while the printer is busy — Selphy can freeze.
