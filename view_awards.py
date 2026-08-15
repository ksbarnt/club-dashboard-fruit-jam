# SPDX-License-Identifier: MIT
"""Renders the Awards dashboard: one table per program listing every award
won by a tracked team, ordered by team number -- mirrors the desktop
app's Awards Dashboard. HTML rowspan isn't available in displayio, so a
team's number (and an event's city) is drawn once, vertically centered
across the block of rows it covers, instead of repeating per row.
"""

import ui_theme
from ui_widgets import fit_text, font_row_height, make_label, make_rect

_TABLES = (("VIQRC", "VIQRC"), ("V5RC", "V5RC"))
_TEAM_COL_X = 10
_EVENT_COL_X = 100
_AWARD_COL_X = 300


def _award_row_count(team):
    total = sum(len(event.get("awards") or []) for event in team.get("events") or [])
    return total or 1


def build(group, data, font, width):
    row_h = font_row_height(font)
    y = 0
    award_col_width = width - _AWARD_COL_X - 10

    for table_key, program in _TABLES:
        teams = data.get(table_key) or []
        if not teams:
            continue
        accent = ui_theme.PROGRAM_ACCENT.get(program, ui_theme.TEXT_PRIMARY)

        group.append(make_rect(width, row_h, ui_theme.GROUP_HEADER_BG, 0, y))
        group.append(make_label(font, program, accent, 10, y + row_h // 2))
        y += row_h

        group.append(make_rect(width, row_h, ui_theme.COLUMN_HEADER_BG, 0, y))
        for label_text, x in (("Team", _TEAM_COL_X), ("Event", _EVENT_COL_X), ("Award", _AWARD_COL_X)):
            group.append(make_label(font, label_text, ui_theme.TEXT_SECONDARY, x, y + row_h // 2))
        y += row_h

        for team in teams:
            team_block_top = y
            team_block_height = _award_row_count(team) * row_h

            for event in team.get("events") or []:
                awards = event.get("awards") or [{"title": "(award)"}]
                event_block_top = y

                for award in awards:
                    text = fit_text(award.get("title"), font, award_col_width)
                    group.append(
                        make_label(font, text, ui_theme.TEXT_PRIMARY, _AWARD_COL_X, y + row_h // 2)
                    )
                    y += row_h

                event_block_height = y - event_block_top
                city_text = fit_text(
                    event.get("eventLabel"), font, _AWARD_COL_X - _EVENT_COL_X - 10
                )
                group.append(
                    make_label(
                        font,
                        city_text,
                        ui_theme.TEXT_SECONDARY,
                        _EVENT_COL_X,
                        event_block_top + event_block_height // 2,
                    )
                )

            number_text = fit_text(team.get("number"), font, _EVENT_COL_X - _TEAM_COL_X - 10)
            group.append(
                make_label(
                    font,
                    number_text,
                    accent,
                    _TEAM_COL_X,
                    team_block_top + team_block_height // 2,
                )
            )

            group.append(make_rect(width, 1, ui_theme.GROUP_HEADER_BG, 0, y))
            y += 1

    if y == 0:
        group.append(
            make_label(font, "No awards recorded for the tracked teams.", ui_theme.TEXT_MUTED, 10, row_h)
        )
        y = row_h * 2

    return y
