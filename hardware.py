# SPDX-License-Identifier: MIT
"""Fruit Jam display (DVI/HDMI via HSTX + picodvi), button, and SD card setup."""

import board
import busio
import displayio
import framebufferio
import neopixel
import picodvi
import storage
import supervisor
from digitalio import DigitalInOut, Direction, Pull

# picodvi/HSTX resolution + color depth pairings that fit in RAM; see the
# adafruit_fruitjam library's own VALID_DISPLAY_SIZES/COLOR_DEPTH_LUT for
# the same table. 640x480x8bpp gives the most screen real estate for
# tables while keeping the framebuffer (~300KB) comfortably inside PSRAM.
_VALID_SIZES = {(360, 200), (720, 400), (320, 240), (640, 480)}


def init_display(width=640, height=480, color_depth=8):
    if (width, height) not in _VALID_SIZES:
        raise ValueError("Unsupported display size %sx%s" % (width, height))

    if supervisor.runtime.display is not None:
        return supervisor.runtime.display

    displayio.release_displays()
    fb = picodvi.Framebuffer(
        width,
        height,
        clk_dp=board.CKP,
        clk_dn=board.CKN,
        red_dp=board.D0P,
        red_dn=board.D0N,
        green_dp=board.D1P,
        green_dn=board.D1N,
        blue_dp=board.D2P,
        blue_dn=board.D2N,
        color_depth=color_depth,
    )
    display = framebufferio.FramebufferDisplay(fb, auto_refresh=True)
    supervisor.runtime.display = display
    return display


def mount_sd_card(mount_point="/sd"):
    """Mount the Fruit Jam's SD card slot, if a card is present.

    Returns True if the card is now mounted at ``mount_point``, False if
    there's no card (or mounting otherwise failed) -- callers that use
    the card for optional persistence (see ``vex_cache.py``) should treat
    False as "run without a cache", not a fatal error.
    """
    try:
        cs = DigitalInOut(board.SD_CS)
        spi = busio.SPI(board.SD_SCK, board.SD_MOSI, board.SD_MISO)
        import adafruit_sdcard

        sdcard = adafruit_sdcard.SDCard(spi, cs)
        vfs = storage.VfsFat(sdcard)
        storage.mount(vfs, mount_point)
        return True
    except OSError as exc:
        print("No SD card mounted at %s: %s" % (mount_point, exc))
        return False


class Buttons(object):
    """The Fruit Jam's three front-edge buttons, active-low with pull-ups."""

    def __init__(self):
        self._pins = [DigitalInOut(pin) for pin in (board.BUTTON1, board.BUTTON2, board.BUTTON3)]
        for pin in self._pins:
            pin.direction = Direction.INPUT
            pin.pull = Pull.UP

    def pressed(self):
        """[bool, bool, bool] -- True where button N (1-indexed) is currently held."""
        return [not pin.value for pin in self._pins]


class StatusPixels(object):
    """The Fruit Jam's 5 onboard NeoPixels, used as a status strip:

    [0] WiFi connected, [1] a dashboard fetch is in progress, [2:5] each
    dashboard view's cached-data status (in dashboard_ui.VIEWS order).
    """

    OFF = (0, 0, 0)
    WIFI = (0, 0, 255)
    UPDATING = (255, 170, 0)
    GOOD = (0, 255, 0)
    STALE = (255, 0, 0)

    def __init__(self, brightness=0.2):
        self._pixels = neopixel.NeoPixel(
            board.NEOPIXEL, 5, brightness=brightness, auto_write=True
        )
        self._pixels.fill(self.OFF)

    def set_wifi(self, connected):
        self._pixels[0] = self.WIFI if connected else self.OFF

    def set_updating(self, updating):
        self._pixels[1] = self.UPDATING if updating else self.OFF

    def set_dashboard(self, index, available):
        """``available``: True (good cached data, green), False (no
        cache on the server yet, red), or None (not checked yet, off)."""
        if available is None:
            color = self.OFF
        elif available:
            color = self.GOOD
        else:
            color = self.STALE
        self._pixels[2 + index] = color
