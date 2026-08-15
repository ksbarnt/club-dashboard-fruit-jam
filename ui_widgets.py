# SPDX-License-Identifier: MIT
"""Low-level displayio building blocks shared by the three dashboard views:
solid-color rects, positioned labels, column-width text fitting, and the
auto-scroll engine used whenever a table is taller than its viewport.
"""

import time

import displayio
from adafruit_display_text import label


def make_rect(width, height, color, x=0, y=0):
    """A solid-color filled rectangle as a displayio.TileGrid."""
    bitmap = displayio.Bitmap(max(1, width), max(1, height), 1)
    palette = displayio.Palette(1)
    palette[0] = color
    return displayio.TileGrid(bitmap, pixel_shader=palette, x=x, y=y)


def make_label(font, text, color, x, y, anchor_point=(0.0, 0.5)):
    """A Label anchored at ``(x, y)`` -- default anchor is mid-left, i.e.
    ``y`` is a row's vertical center, not its top."""
    lbl = label.Label(font, text=text if text is not None else "", color=color)
    lbl.anchor_point = anchor_point
    lbl.anchored_position = (x, y)
    return lbl


def font_row_height(font, padding=6):
    box = font.get_bounding_box()
    return box[1] + padding


def font_char_width(font):
    box = font.get_bounding_box()
    return box[0] or 1


def fit_text(text, font, max_width_px):
    """Truncate ``text`` with an ASCII ellipsis if it won't fit in
    ``max_width_px`` -- the built-in terminal font has no Unicode "..."
    glyph, so three periods stand in for one.
    """
    text = "" if text is None else str(text)
    char_width = font_char_width(font)
    max_chars = max(1, max_width_px // char_width)
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return text[: max_chars - 3] + "..."


class ScrollArea(object):
    """A displayio Group that auto-scrolls its contents vertically when
    they're taller than the viewport: pause at the top, scroll down slowly,
    pause at the bottom, scroll back up, repeat. No-ops (stays put) when
    everything already fits.
    """

    def __init__(self, x, y, viewport_height, step=1, delay=0.04, pause=2.0):
        self.group = displayio.Group(x=x, y=y)
        self._origin_y = y
        self.viewport_height = viewport_height
        self._step = max(1, int(step))
        self._delay = delay
        self._pause = pause
        self._content_height = 0
        self._offset = 0
        self._direction = 1
        self._pause_until = None
        self._last_tick = time.monotonic()

    def set_content(self, build):
        """Clear this area and repopulate it.

        ``build(parent_group)`` should append this view's rows to
        ``parent_group`` and return the total content height in pixels.
        """
        while len(self.group) > 0:
            self.group.pop()
        self._content_height = build(self.group)
        self._offset = 0
        self._direction = 1
        self.group.y = self._origin_y
        now = time.monotonic()
        self._pause_until = now + self._pause
        self._last_tick = now

    def tick(self):
        max_scroll = self._content_height - self.viewport_height
        if max_scroll <= 0:
            if self.group.y != self._origin_y:
                self.group.y = self._origin_y
            return

        now = time.monotonic()
        if self._pause_until is not None:
            if now < self._pause_until:
                return
            self._pause_until = None
            self._last_tick = now
            return
        if now - self._last_tick < self._delay:
            return
        self._last_tick = now

        self._offset += self._step * self._direction
        if self._offset >= max_scroll:
            self._offset = max_scroll
            self._direction = -1
            self._pause_until = now + self._pause
        elif self._offset <= 0:
            self._offset = 0
            self._direction = 1
            self._pause_until = now + self._pause
        self.group.y = self._origin_y - self._offset
