# SPDX-License-Identifier: MIT
"""The dashboard's fixed screen shell: background, header (title + clock),
a fixed column-header bar, footer (view legend + status line), and the
auto-scrolling content area the three views render into. Only that last
area scrolls -- column headers stay put via ``set_table_header()``.
"""

import displayio
import terminalio

import ui_theme
from ui_widgets import ScrollArea, font_char_width, font_row_height, make_label, make_rect

VIEWS = ("active", "world_skills", "awards")
VIEW_TITLES = {
    "active": "Active Today",
    "world_skills": "World Skills",
    "awards": "Awards",
}
VIEW_NAV_LABELS = {
    "active": "[1] Active Today",
    "world_skills": "[2] World Skills",
    "awards": "[3] Awards",
}


class DashboardUI(object):
    def __init__(self, display, config):
        self.display = display
        self.config = config
        self.font = terminalio.FONT
        self.width = display.width
        self.height = display.height

        self.header_height = font_row_height(self.font, padding=12)
        self.footer_height = font_row_height(self.font, padding=12)
        # Column labels ("#", "Rank", ...) are identical across every
        # section within a view, so they're drawn once in a fixed bar
        # rather than repeated per section inside the scrolling content --
        # that's also what keeps them from scrolling along with the data.
        self.row_height = font_row_height(self.font)
        self.table_header_height = self.row_height
        self.viewport_height = (
            self.height - self.header_height - self.table_header_height - self.footer_height
        )

        self.root = displayio.Group()
        self.root.append(make_rect(self.width, self.height, ui_theme.SURFACE))

        # Steps SCROLL_STEP_LINES worth of table rows every scroll_delay
        # seconds -- the pixel step is computed here (not in config.py)
        # since only this layer knows the actual on-screen row height.
        step_px = max(1, config.scroll_step_lines) * self.row_height
        self.scroll = ScrollArea(
            0,
            self.header_height + self.table_header_height,
            self.viewport_height,
            step=step_px,
            delay=config.scroll_delay,
            pause=config.scroll_pause,
        )
        self.root.append(self.scroll.group)

        self.nav_labels = {}
        self._build_header()
        self._build_table_header()
        self._build_footer()

        display.root_group = self.root

    def _build_header(self):
        group = displayio.Group()
        group.append(make_rect(self.width, self.header_height, ui_theme.HEADER_BG))
        self.title_label = make_label(
            self.font, "", ui_theme.TEXT_PRIMARY, 10, self.header_height // 2
        )
        group.append(self.title_label)
        self.clock_label = make_label(
            self.font,
            "",
            ui_theme.TEXT_SECONDARY,
            self.width - 10,
            self.header_height // 2,
            anchor_point=(1.0, 0.5),
        )
        group.append(self.clock_label)
        self.root.append(group)

    def _build_table_header(self):
        self.table_header_group = displayio.Group(x=0, y=self.header_height)
        self.table_header_group.append(
            make_rect(self.width, self.table_header_height, ui_theme.COLUMN_HEADER_BG)
        )
        self.root.append(self.table_header_group)

    def _build_footer(self):
        group = displayio.Group(x=0, y=self.height - self.footer_height)
        group.append(make_rect(self.width, self.footer_height, ui_theme.FOOTER_BG))
        char_w = font_char_width(self.font)
        x = 10
        for view in VIEWS:
            text = VIEW_NAV_LABELS[view]
            lbl = make_label(self.font, text, ui_theme.TEXT_MUTED, x, self.footer_height // 2)
            group.append(lbl)
            self.nav_labels[view] = lbl
            x += (len(text) + 3) * char_w
        self.status_label = make_label(
            self.font,
            "",
            ui_theme.WARNING,
            self.width - 10,
            self.footer_height // 2,
            anchor_point=(1.0, 0.5),
        )
        group.append(self.status_label)
        self.root.append(group)

    def set_active_view(self, view):
        for key, lbl in self.nav_labels.items():
            lbl.color = ui_theme.TEXT_PRIMARY if key == view else ui_theme.TEXT_MUTED
        self.title_label.text = VIEW_TITLES.get(view, "")

    def set_clock(self, text):
        self.clock_label.text = text or ""

    def set_status(self, text):
        self.status_label.text = text or ""

    def set_table_header(self, build_header):
        """Replace the fixed column-label row. ``build_header(parent_group)``
        -- unlike ``render()``, this row never scrolls."""
        group = self.table_header_group
        while len(group) > 1:  # keep the background rect (index 0)
            group.pop()
        build_header(group)

    def render(self, build_content):
        """``build_content(parent_group) -> content_height_px``. Only this
        (the table body) scrolls -- column headers live in the fixed bar
        set via ``set_table_header()``."""
        self.scroll.set_content(build_content)

    def tick(self):
        self.scroll.tick()
