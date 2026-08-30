# Flash lamp wiring

- Use a **3.3 V relay module** or **logic-level MOSFET** — never connect 12 V to the Pi.
- Default GPIO: **BCM 17** (physical pin 11).
- Pi GPIO → module IN, Pi GND → module GND.
- 12 V PSU → lamp → switched output → 12 V GND.
- Configure `flash.gpio_pin`, `flash.active_high` in config.

Test from settings screen: **Test flash (1s)**.
