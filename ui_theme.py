# SPDX-License-Identifier: MIT
"""Dashboard color theme.

A dark surface with a validated categorical pair for program identity:
VIQRC blue / V5RC red pass CVD-safe adjacent-pair separation (worst-case
deltaE 19.2 protan / 31.4 tritan, well above the 8.0 target) and >=3:1
contrast against this surface, checked with the dataviz skill's palette
validator rather than picked by eye.
"""

SURFACE = 0x1A1A19
HEADER_BG = 0x0D0D0D
FOOTER_BG = 0x0D0D0D
GROUP_HEADER_BG = 0x2C2C2A
COLUMN_HEADER_BG = 0x252523

TEXT_PRIMARY = 0xFFFFFF
TEXT_SECONDARY = 0xC3C2B7
TEXT_MUTED = 0x898781

VIQRC_ACCENT = 0x3987E5
V5RC_ACCENT = 0xE66767

WARNING = 0xFAB219

PROGRAM_ACCENT = {"VIQRC": VIQRC_ACCENT, "V5RC": V5RC_ACCENT}
