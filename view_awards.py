# SPDX-License-Identifier: MIT
"""Renders the Awards dashboard: one table per program listing every award
won by a tracked team, ordered by team number -- mirrors the desktop
app's Awards Dashboard. HTML rowspan isn't available in displayio, so a
team's number (and an event's city) is drawn once, vertically centered
across the block of rows it covers, instead of repeating per row. Page
breaks only ever fall between events, never between two awards of the
same event -- so when a team's events span more than one page, its
number is drawn again on each page, centered against just the portion
of that team's rows which landed on that particular page (not the
team's full original block height).
"""

import ui_theme
from ui_widgets import fit_text, font_row_height, make_label, make_rect

_TABLES = (("VIQRC", "VIQRC"), ("V5RC", "V5RC"))
_TEAM_COL_X = 10
_EVENT_COL_X = 100
_AWARD_COL_X = 300


def build_header(group, font, width):
    """Column labels for the fixed (non-scrolling) header bar."""
    row_h = font_row_height(font)
    for label_text, x in (("Team", _TEAM_COL_X), ("Event", _EVENT_COL_X), ("Award", _AWARD_COL_X)):
        group.append(make_label(font, label_text, ui_theme.TEXT_SECONDARY, x, row_h // 2))


def build(data, font, width, viewport_height):
    row_h = font_row_height(font)
    award_col_width = width - _AWARD_COL_X - 10

    pages = []
    ops = []  # [(draw_fn, y), ...] for the in-progress page
    y = 0
    current_program_header = None  # (draw_fn, height) for the program currently being drawn
    program_drawn_this_page = False
    team_run_start_y = None  # page-local start of the open team's centering run
    team_run_slot = None  # index into ops reserved for the centered team-number label

    def flush():
        nonlocal ops, y, program_drawn_this_page
        if not ops:
            return
        snapshot = ops
        pages.append(lambda group, ops=snapshot: [fn(group, yy) for fn, yy in ops])
        ops = []
        y = 0
        program_drawn_this_page = False

    def ensure_program_header():
        nonlocal y, program_drawn_this_page
        if current_program_header is not None and not program_drawn_this_page:
            draw_fn, h = current_program_header
            ops.append((draw_fn, y))
            y += h
            program_drawn_this_page = True

    def close_team_run(number_text, accent):
        nonlocal team_run_start_y
        if team_run_start_y is None:
            return
        center_y = team_run_start_y + (y - team_run_start_y) // 2

        def draw_number(group, _y, number_text=number_text, accent=accent, center_y=center_y):
            group.append(make_label(font, number_text, accent, _TEAM_COL_X, center_y))

        ops[team_run_slot] = (draw_number, 0)
        team_run_start_y = None

    for table_key, program in _TABLES:
        teams = data.get(table_key) or []
        if not teams:
            continue
        accent = ui_theme.PROGRAM_ACCENT.get(program, ui_theme.TEXT_PRIMARY)

        def draw_program_header(group, y, program=program, accent=accent):
            group.append(make_rect(width, row_h, ui_theme.GROUP_HEADER_BG, 0, y))
            group.append(make_label(font, program, accent, 10, y + row_h // 2))

        current_program_header = (draw_program_header, row_h)
        program_drawn_this_page = False

        for team in teams:
            number_text = fit_text(team.get("number"), font, _EVENT_COL_X - _TEAM_COL_X - 10)
            events = team.get("events") or []
            last_index = len(events) - 1
            team_run_start_y = None

            for idx, event in enumerate(events):
                awards = event.get("awards") or [{"title": "(award)"}]
                event_height = len(awards) * row_h
                header_gap = 0 if program_drawn_this_page else row_h

                # An event's award rows are an atomic unit -- this is the
                # only place a page break is allowed to fall for Awards.
                if y > 0 and y + header_gap + event_height > viewport_height:
                    close_team_run(number_text, accent)
                    flush()

                ensure_program_header()

                if team_run_start_y is None:
                    team_run_start_y = y
                    team_run_slot = len(ops)
                    ops.append((None, y))  # reserved slot, patched by close_team_run()

                event_block_top = y
                for award in awards:
                    text = fit_text(award.get("title"), font, award_col_width)

                    def draw_award(group, yy, text=text):
                        group.append(
                            make_label(font, text, ui_theme.TEXT_PRIMARY, _AWARD_COL_X, yy + row_h // 2)
                        )

                    ops.append((draw_award, y))
                    y += row_h

                event_center_y = event_block_top + (y - event_block_top) // 2
                city_text = fit_text(event.get("eventLabel"), font, _AWARD_COL_X - _EVENT_COL_X - 10)

                def draw_city(group, _y, city_text=city_text, event_center_y=event_center_y):
                    group.append(
                        make_label(font, city_text, ui_theme.TEXT_SECONDARY, _EVENT_COL_X, event_center_y)
                    )

                ops.append((draw_city, 0))

                # Border line between events within a team -- stops short
                # of the Team column so it doesn't cut through the merged
                # team-number cell, which spans every event below it.
                if idx != last_index:

                    def draw_divider(group, yy):
                        group.append(
                            make_rect(width - _EVENT_COL_X, 1, ui_theme.GROUP_HEADER_BG, _EVENT_COL_X, yy)
                        )

                    ops.append((draw_divider, y))
                    y += 1

            close_team_run(number_text, accent)

            def draw_team_divider(group, yy):
                group.append(make_rect(width, 1, ui_theme.GROUP_HEADER_BG, 0, yy))

            ops.append((draw_team_divider, y))
            y += 1

    flush()

    if not pages:
        pages = [
            lambda g: g.append(
                make_label(font, "No awards recorded for the tracked teams.", ui_theme.TEXT_MUTED, 10, row_h)
            )
        ]

    return pages
