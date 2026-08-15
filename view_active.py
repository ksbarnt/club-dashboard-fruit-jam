# SPDX-License-Identifier: MIT
"""Renders the Active Today dashboard: one table per program (IQ/V5) that
has teams competing today, grouped by event and ordered by rank within
each event -- mirrors the desktop app's Active Teams Dashboard.
"""

import ui_theme
from ui_widgets import fit_text, font_row_height, make_label, make_rect

_COLUMNS = [
    ("#", 70),
    ("Rank", 60),
    ("Skills Rk", 90),
    ("Driver", 140),
    ("Auto", 140),
]
_TABLES = (("IQ", "VIQRC"), ("V5", "V5RC"))


def _score_cell(score, attempts):
    score_txt = "--" if score is None else str(score)
    attempts_txt = 0 if attempts is None else attempts
    return "%s (%s/3)" % (score_txt, attempts_txt)


def build_header(group, font, width):
    """Column labels for the fixed (non-scrolling) header bar."""
    row_h = font_row_height(font)
    x = 10
    for label_text, col_w in _COLUMNS:
        group.append(make_label(font, label_text, ui_theme.TEXT_SECONDARY, x, row_h // 2))
        x += col_w


def build(group, data, font, width):
    row_h = font_row_height(font)
    y = 0

    for table_key, program in _TABLES:
        event_groups = data.get(table_key) or []
        if not event_groups:
            continue
        accent = ui_theme.PROGRAM_ACCENT.get(program, ui_theme.TEXT_PRIMARY)

        group.append(make_rect(width, row_h, ui_theme.GROUP_HEADER_BG, 0, y))
        group.append(make_label(font, program, accent, 10, y + row_h // 2))
        y += row_h

        for event_group in event_groups:
            group.append(make_rect(width, row_h, ui_theme.GROUP_HEADER_BG, 0, y))
            name = fit_text(event_group.get("eventName") or "(unnamed event)", font, width - 20)
            group.append(make_label(font, name, ui_theme.TEXT_PRIMARY, 10, y + row_h // 2))
            y += row_h

            for team in event_group.get("teams") or []:
                cells = [
                    str(team.get("number") or ""),
                    "--" if team.get("eventRank") is None else str(team["eventRank"]),
                    "--" if team.get("skillsRank") is None else str(team["skillsRank"]),
                    _score_cell(team.get("driverScore"), team.get("driverAttempts")),
                    _score_cell(team.get("autoScore"), team.get("autoAttempts")),
                ]
                x = 10
                for i, ((_label, col_w), value) in enumerate(zip(_COLUMNS, cells)):
                    color = accent if i == 0 else ui_theme.TEXT_PRIMARY
                    group.append(make_label(font, value, color, x, y + row_h // 2))
                    x += col_w
                y += row_h

    if y == 0:
        group.append(
            make_label(font, "No tracked teams have events today.", ui_theme.TEXT_MUTED, 10, row_h)
        )
        y = row_h * 2

    return y
