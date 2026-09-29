# Flash lamp wiring

## GPIO (default)

- Use a **3.3 V relay module** or **logic-level MOSFET** — never connect 12 V to the Pi.
- Default GPIO: **BCM 17** (physical pin 11).
- Pi GPIO → module IN, Pi GND → module GND.
- 12 V PSU → lamp → switched output → 12 V GND.
- Config:

```yaml
flash:
  enabled: true
  backend: gpio
  gpio_pin: 17
  active_high: true
```

## USB serial controller

Lamp is an external USB serial device. Photobooth sends ASCII lines:

- On / fire: `D <power>\n` (e.g. `D 100\n`)
- Off: `D 0\n`

```yaml
flash:
  enabled: true
  backend: serial
  serial_port: /dev/ttyUSB0   # or /dev/ttyACM0, COM3 on Windows
  serial_baud: 115200
  power: 100                  # value sent while lamp is on
  off_power: 0
  warmup_ms: 100
  duration_ms: 3000
  safety_ms: 5000
```

Find the port:

```bash
ls -l /dev/ttyUSB* /dev/ttyACM*
# user must be in dialout:  sudo usermod -aG dialout $USER
```

Put machine-specific port in `config/local.yaml` so git pull does not reset it.

Test from settings screen: **Test flash (1s)**.
