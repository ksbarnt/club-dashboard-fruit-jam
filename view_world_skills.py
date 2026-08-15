# SPDX-License-Identifier: MIT
"""Renders the World Skills dashboard: one table per program+grade
combination present among the tracked teams, sorted within each group by
regional rank -- mirrors the desktop app's World Skills Dashboard.
"""

import ui_theme
from ui_widgets import font_row_height, make_label, make_rect

_COLUMNS = [
    ("#", 70),
    ("Region Rk", 100),
    ("World Rk", 100),
    ("Overall", 90),
    ("Driver", 90),
    ("Auto", 90),
]

_GROUP_TITLES = {
    ("VIQRC", "ES"): "VIQRC - Elementary School",
    ("VIQRC", "MS"): "VIQRC - Middle School",
    ("V5RC", "MS"): "V5RC - Middle School",
    ("V5RC", "HS"): "V5RC - High School",
}


def build(group, data, font, width):
    row_h = font_row_height(font)
    y = 0

    for grp in data.get("groups") or []:
        program = grp["program"]
        accent = ui_theme.PROGRAM_ACCENT.get(program, ui_theme.TEXT_PRIMARY)
        title = _GROUP_TITLES.get((program, grp["grade"]), "%s - %s" % (program, grp["grade"]))

        group.append(make_rect(width, row_h, ui_theme.GROUP_HEADER_BG, 0, y))
        group.append(make_label(font, title, accent, 10, y + row_h // 2))
        y += row_h

        group.append(make_rect(width, row_h, ui_theme.COLUMN_HEADER_BG, 0, y))
        x = 10
        for label_text, col_w in _COLUMNS:
            group.append(make_label(font, label_text, ui_theme.TEXT_SECONDARY, x, y + row_h // 2))
            x += col_w
        y += row_h

        for team in grp.get("teams") or []:
            cells = [
                str(team.get("number") or ""),
                "--" if team.get("regionalRank") is None else str(team["regionalRank"]),
                "--" if team.get("worldRank") is None else str(team["worldRank"]),
                "--" if team.get("overallScore") is None else str(team["overallScore"]),
                "--" if team.get("driverScore") is None else str(team["driverScore"]),
                "--" if team.get("autoScore") is None else str(team["autoScore"]),
            ]
            x = 10
            for i, ((_label, col_w), value) in enumerate(zip(_COLUMNS, cells)):
                color = accent if i == 0 else ui_theme.TEXT_PRIMARY
                group.append(make_label(font, value, color, x, y + row_h // 2))
                x += col_w
            y += row_h

    if y == 0:
        group.append(
            make_label(
                font,
                "No world skills rankings found for the tracked teams.",
                ui_theme.TEXT_MUTED,
                10,
                row_h,
            )
        )
        y = row_h * 2

    return y
