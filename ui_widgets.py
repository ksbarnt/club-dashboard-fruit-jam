# SPDX-License-Identifier: MIT
"""Low-level displayio building blocks shared by the three dashboard views:
solid-color rects, positioned labels, column-width text fitting, and the
page-advance engine used whenever a table is taller than its viewport.
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


class PageArea(object):
    """A displayio Group that shows one pre-built "page" of content at a
    time, advancing to the next on a timer and looping back to the first
    after the last -- discrete auto-advancing pages, replacing continuous
    auto-scroll. Purely a display engine: it has no concept of rows,
    headers, or sections -- each page handed to set_pages() must already
    be a self-contained draw closure guaranteed by its caller to fit
    within viewport_height. A single page is shown indefinitely without
    ever advancing (mirrors the previous scroll engine's no-op when
    content already fits).
    """

    def __init__(self, x, y, viewport_height, pause=6.0):
        self.group = displayio.Group(x=x, y=y)
        self.viewport_height = viewport_height
        self._pause = max(0.5, pause)
        self._pages = [lambda g: None]
        self._index = 0
        self._page_until = None

    def set_pages(self, pages):
        """``pages``: a list of ``draw(parent_group)`` closures, each
        already laid out to fit within viewport_height. Replaces current
        content, resets to page 0, restarts the dwell timer."""
        self._pages = pages or [lambda g: None]
        self._index = 0
        self._show_page(self._index)
        self._page_until = time.monotonic() + self._pause

    def _show_page(self, index):
        while len(self.group) > 0:
            self.group.pop()
        self._pages[index](self.group)

    def tick(self):
        if len(self._pages) <= 1:
            return
        now = time.monotonic()
        if self._page_until is None or now < self._page_until:
            return
        self._index = (self._index + 1) % len(self._pages)
        self._show_page(self._index)
        self._page_until = now + self._pause
