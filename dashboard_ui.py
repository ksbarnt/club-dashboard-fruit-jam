# SPDX-License-Identifier: MIT
"""The dashboard's fixed screen shell: background, header (title + clock),
footer (view legend + status line), and the auto-scrolling content area
the three views render into.
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
        self.viewport_height = self.height - self.header_height - self.footer_height

        self.root = displayio.Group()
        self.root.append(make_rect(self.width, self.height, ui_theme.SURFACE))

        self.scroll = ScrollArea(
            0,
            self.header_height,
            self.viewport_height,
            step=config.scroll_step,
            delay=config.scroll_delay,
            pause=config.scroll_pause,
        )
        self.root.append(self.scroll.group)

        self.nav_labels = {}
        self._build_header()
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

    def _build_footer(self):
        group = displayio.Group()
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

    def render(self, build_content):
        """``build_content(parent_group) -> content_height_px``"""
        self.scroll.set_content(build_content)

    def tick(self):
        self.scroll.tick()
