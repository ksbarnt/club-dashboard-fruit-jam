# SPDX-License-Identifier: MIT
"""Fruit Jam display (DVI/HDMI via HSTX + picodvi) and button setup."""

import board
import displayio
import framebufferio
import picodvi
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
