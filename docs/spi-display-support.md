# Planned Work: SPI Display Support

This document describes the planned work to re-add support for the original Waveshare 3.5" SPI display alongside the current RPi 7" framebuffer display.

## Background

This repo was forked from [filbot/iss-tracker](https://github.com/filbot/iss-tracker), which used a Waveshare 3.5" SPI display (320×480, ST7796S controller). It was converted to use the official Raspberry Pi 7" display (800×480, Linux framebuffer via `/dev/fb0`).

The goal of this planned work is to make both display types selectable via a `DISPLAY_TYPE` environment variable, so either hardware configuration works without code changes.

---

## Complexity: Medium (~1–2 days)

### What makes it straightforward

- `LcdDisplay` already wraps the low-level driver cleanly — `FramebufferDisplay` only exposes `display_raw(rgb565_bytes)`, so a new `SpiDisplay` class just needs the same interface
- All rendering logic (globe frames, HUD, ISS marker) is display-agnostic and untouched
- The original SPI driver code in filbot/iss-tracker is good reference material

### What adds complexity

- **Resolution difference** — SPI display is 320×480; RPi display is 800×480. Frame caches are resolution-specific.
- **Optional dependencies** — `spidev` and `rpi-lgpio` are only needed for SPI and must not be required when using the framebuffer
- **SPI is slower** — the original used partial-frame updates to compensate for SPI bandwidth limits; full frames work but will be slower

---

## Implementation Steps

### 1. New `SpiDisplay` class

**File:** `src/iss_display/display/lcd_driver.py`

Add alongside the existing `FramebufferDisplay` class. Must implement the same interface:

```python
class SpiDisplay:
    def display_raw(self, rgb565_bytes: bytes) -> None: ...
    def close(self) -> None: ...
```

Implementation:
- ST7796S initialization: hardware reset (RST pin), soft reset (`0x01`), sleep out (`0x11`), 16-bit colour mode (`0x3A` → `0x05`), display on (`0x29`)
- `display_raw`: set window (`CASET 0x2A`, `RASET 0x2B`), send MEMORY_WRITE (`0x2C`), transmit all pixel bytes
- GPIO control (DC, RST, BL pins) via `lgpio`
- SPI communication via `spidev`
- Reference: [filbot/iss-tracker lcd_driver.py](https://github.com/filbot/iss-tracker)

### 2. Config additions

**File:** `src/iss_display/config.py`

New env vars to add to the `Settings` dataclass:

| Variable | Default | Description |
|----------|---------|-------------|
| `DISPLAY_TYPE` | `framebuffer` | `"framebuffer"` or `"spi"` |
| `SPI_DC_PIN` | `24` | GPIO pin for data/command |
| `SPI_RST_PIN` | `25` | GPIO pin for reset |
| `SPI_BL_PIN` | `18` | GPIO pin for backlight |
| `SPI_SPEED_HZ` | `48000000` | SPI clock speed |

### 3. Driver factory in `LcdDisplay.__init__`

**File:** `src/iss_display/display/lcd_driver.py` (around line 131)

Replace the hardcoded `FramebufferDisplay` instantiation with:

```python
if settings.display_type == "spi":
    self.driver = SpiDisplay(settings)
else:
    self.driver = FramebufferDisplay(settings.fb_device)
```

Also update the `HARDWARE_AVAILABLE` constant (currently checks for `/dev/fb0`) to handle both cases correctly.

### 4. Optional dependencies

**File:** `pyproject.toml`

```toml
[project.optional-dependencies]
spi = ["spidev>=3.6", "rpi-lgpio>=0.6"]
```

Guard `import spidev` and `import lgpio` inside `SpiDisplay.__init__` — raise a clear `ImportError` with install instructions if missing:

```
SPI display requires additional packages. Install with:
    pip install iss-display[spi]
```

### 5. `.env.example` additions

```bash
# Display type: "framebuffer" (RPi 7" official display) or "spi" (Waveshare 3.5" SPI)
DISPLAY_TYPE=framebuffer

# SPI display GPIO pins (only used when DISPLAY_TYPE=spi)
# SPI_DC_PIN=24
# SPI_RST_PIN=25
# SPI_BL_PIN=18
# SPI_SPEED_HZ=48000000
```

### 6. Resolution

When `DISPLAY_TYPE=spi`, also set:

```bash
DISPLAY_WIDTH=480
DISPLAY_HEIGHT=320
```

The frame cache is keyed by resolution, so separate caches are maintained automatically — no code change needed here.

---

## What to skip for the initial implementation

These can be added later if needed:

- **Partial frame updates** — the original used these to compensate for SPI bandwidth limits (~48 MHz = ~48ms per full frame). Full frames work, just at a lower update rate.
- **SPI health monitoring / reinit** — the original had a 3-tier recovery system (health check → light reinit → full reinit). Add later if display freezing becomes a problem in practice.

---

## Verification

1. `DISPLAY_TYPE=framebuffer` — existing behaviour completely unchanged
2. `DISPLAY_TYPE=spi` with Waveshare display connected — globe and HUD appear on screen
3. `DISPLAY_TYPE=spi` without `spidev` installed — clear error message with install instructions
