# SPDX-License-Identifier: MIT
"""Loads and validates settings.toml into a plain config object.

CircuitPython reads settings.toml automatically at boot and exposes its
values through ``os.getenv()``. Unlike the desktop app (which keeps its
settings, including an arbitrary-length team list, in the browser's local
storage as JSON), settings.toml only holds flat scalars -- so the team list
is encoded as a single comma-separated string of ``number:program:grade``
triplets and parsed here.
"""

import os

DEFAULT_REFRESH_INTERVAL = 300
DEFAULT_SCROLL_STEP = 1
DEFAULT_SCROLL_DELAY = 0.04
DEFAULT_SCROLL_PAUSE = 2.0
DEFAULT_DISPLAY_WIDTH = 640
DEFAULT_DISPLAY_HEIGHT = 480

# Program abbreviation -> valid grade codes, mirrors the desktop app's
# Settings view (grade choices depend on the selected program).
PROGRAM_GRADES = {
    "VIQRC": ("ES", "MS"),
    "V5RC": ("MS", "HS"),
}

# picodvi/HSTX resolution+depth pairings the hardware supports -- kept in
# sync with hardware._VALID_SIZES. Duplicated here (rather than imported)
# so validating settings.toml never has to import board/displayio.
VALID_DISPLAY_SIZES = {(360, 200), (720, 400), (320, 240), (640, 480)}


class ConfigError(Exception):
    """Raised for missing/invalid settings.toml values."""


def _parse_teams(raw):
    teams = []
    if not raw:
        return teams
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(":")
        if len(parts) != 3:
            raise ConfigError(
                "TEAMS entry %r must be in number:program:grade form" % chunk
            )
        number, program, grade = (p.strip() for p in parts)
        program = program.upper()
        grade = grade.upper()
        if program not in PROGRAM_GRADES:
            raise ConfigError("TEAMS entry %r has unknown program %r" % (chunk, program))
        if grade not in PROGRAM_GRADES[program]:
            raise ConfigError(
                "TEAMS entry %r has invalid grade %r for %s" % (chunk, grade, program)
            )
        teams.append({"number": number, "program": program, "grade": grade})
    return teams


class Config(object):
    """Snapshot of settings.toml, validated once at boot."""

    def __init__(self):
        self.wifi_ssid = os.getenv("CIRCUITPY_WIFI_SSID")
        self.wifi_password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
        self.api_token = os.getenv("VEX_API_TOKEN")
        self.event_region = os.getenv("EVENT_REGION") or ""
        self.viqrc_season_id = os.getenv("VIQRC_SEASON_ID") or None
        self.v5rc_season_id = os.getenv("V5RC_SEASON_ID") or None
        self.teams = _parse_teams(os.getenv("TEAMS"))

        tz = float(os.getenv("TZ_OFFSET_HOURS"))
        self.tz_offset_hours = tz if tz is not None else 0

        self.refresh_interval = float(os.getenv("REFRESH_INTERVAL_SECONDS")) or DEFAULT_REFRESH_INTERVAL
        self.scroll_step = float(os.getenv("SCROLL_STEP_PIXELS")) or DEFAULT_SCROLL_STEP

        scroll_delay = float(os.getenv("SCROLL_DELAY_SECONDS"))
        self.scroll_delay = scroll_delay if scroll_delay is not None else DEFAULT_SCROLL_DELAY

        scroll_pause = float(os.getenv("SCROLL_PAUSE_SECONDS"))
        self.scroll_pause = scroll_pause if scroll_pause is not None else DEFAULT_SCROLL_PAUSE

        self.display_width = int(os.getenv("DISPLAY_WIDTH")) or DEFAULT_DISPLAY_WIDTH
        self.display_height = int(os.getenv("DISPLAY_HEIGHT")) or DEFAULT_DISPLAY_HEIGHT

        self._validate()

    def _validate(self):
        if not self.wifi_ssid or not self.wifi_password:
            raise ConfigError(
                "CIRCUITPY_WIFI_SSID and CIRCUITPY_WIFI_PASSWORD must be set in settings.toml"
            )
        if not self.api_token:
            raise ConfigError("VEX_API_TOKEN must be set in settings.toml")
        if not self.teams:
            raise ConfigError("TEAMS must list at least one team in settings.toml")
        if not self.viqrc_season_id and not self.v5rc_season_id:
            raise ConfigError(
                "At least one of VIQRC_SEASON_ID / V5RC_SEASON_ID must be set in settings.toml"
            )
        if (self.display_width, self.display_height) not in VALID_DISPLAY_SIZES:
            raise ConfigError(
                "DISPLAY_WIDTH/DISPLAY_HEIGHT %sx%s is not supported; must be one of: %s"
                % (self.display_width, self.display_height, sorted(VALID_DISPLAY_SIZES))
            )

    def season_id_for(self, program):
        return self.viqrc_season_id if program == "VIQRC" else self.v5rc_season_id
