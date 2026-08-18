# SPDX-License-Identifier: MIT
"""Pagination helper shared by the two dashboard views whose layout is
"N nested header levels, then flat rows" -- Active Today (2 levels:
program, event) and World Skills (1 level: program+grade group). Kept
separate from ui_widgets.py, which stays pure low-level displayio
primitives plus the shape-agnostic PageArea: this module is shape-aware
business logic reused by exactly those two views. Awards' merged-cell,
atomic-event-packing layout doesn't fit this "header then rows" model,
so it paginates itself directly in view_awards.py instead of using this.
"""


class SectionPager(object):
    """Packs headers and rows into pages that fit within viewport_height,
    keeping each header on the same page as its first row (never dangling
    a header alone at the bottom of a page) and reprinting every still-open
    ancestor header at the top of a page that continues a section.

    Call set_header(level, draw_fn, height) whenever a header at that
    nesting level begins or changes -- this also closes out any deeper
    levels, since a new sibling/parent header means their old children no
    longer apply. Call add_row(draw_fn, height) for each leaf row. Both
    draw_fn signatures are draw_fn(group, y). Call pages() once at the end
    for the finished list of page-draw closures.
    """

    def __init__(self, viewport_height):
        self.viewport_height = viewport_height
        self._pages = []
        self._ops = []  # [(draw_fn, y), ...] for the in-progress page
        self._y = 0
        self._stack = []  # [[level, draw_fn, height, drawn_on_this_page], ...]

    def has_content(self):
        return bool(self._pages or self._ops)

    def set_header(self, level, draw_fn, height):
        self._stack = [h for h in self._stack if h[0] < level]
        self._stack.append([level, draw_fn, height, False])

    def add_row(self, draw_fn, height):
        pending = [h for h in self._stack if not h[3]]
        needed = sum(h[2] for h in pending) + height
        if self._y > 0 and self._y + needed > self.viewport_height:
            self._flush()
            for h in self._stack:
                h[3] = False
            pending = [h for h in self._stack if not h[3]]

        for h in pending:
            self._ops.append((h[1], self._y))
            self._y += h[2]
            h[3] = True
        self._ops.append((draw_fn, self._y))
        self._y += height

    def _flush(self):
        if not self._ops:
            return
        snapshot = self._ops
        self._pages.append(lambda group, ops=snapshot: [fn(group, y) for fn, y in ops])
        self._ops = []
        self._y = 0

    def pages(self):
        self._flush()
        return self._pages or [lambda g: None]
