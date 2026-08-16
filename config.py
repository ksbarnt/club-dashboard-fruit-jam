# SPDX-License-Identifier: MIT
"""Loads and validates settings.toml into a plain config object.

CircuitPython reads settings.toml automatically at boot and exposes its
values through ``os.getenv()``.
"""

import os

DEFAULT_REFRESH_INTERVAL = 300
DEFAULT_SCROLL_STEP_LINES = 1
DEFAULT_SCROLL_DELAY = 2.0
DEFAULT_SCROLL_PAUSE = 4.0
DEFAULT_DISPLAY_WIDTH = 640
DEFAULT_DISPLAY_HEIGHT = 480

# picodvi/HSTX resolution+depth pairings the hardware supports -- kept in
# sync with hardware._VALID_SIZES. Duplicated here (rather than imported)
# so validating settings.toml never has to import board/displayio.
VALID_DISPLAY_SIZES = {(360, 200), (720, 400), (320, 240), (640, 480)}


class ConfigError(Exception):
    """Raised for missing/invalid settings.toml values."""


def _get_number(key, default, cast):
    """Read an optional numeric setting.

    ``os.getenv()`` on this board hands back a plain ``str`` for values
    from settings.toml (not the int/float CircuitPython's own typed
    parsing would imply), so every numeric setting needs an explicit
    cast -- but casting unconditionally (e.g. ``float(os.getenv(...))``)
    breaks the "optional, falls back to a default" contract, since
    ``float(None)`` raises for a key that was simply left out. This
    covers both: a missing key returns ``default`` silently, while a
    present-but-unparseable value raises a clear ``ConfigError`` instead
    of a cryptic ``TypeError``/``ValueError`` deep in the UI or NTP code.
    """
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return cast(value)
    except (TypeError, ValueError):
        raise ConfigError("%s must be a number, got %r" % (key, value))


def _get_float(key, default):
    return _get_number(key, default, float)


def _get_int(key, default):
    # int(float(v)) (rather than plain int(v)) so "640.0" and 640.0 -- not
    # just "640" -- are also accepted, since the on-device string-vs-typed
    # behavior described above isn't consistent enough to rely on one form.
    return _get_number(key, default, lambda v: int(float(v)))


class Config(object):
    """Snapshot of settings.toml, validated once at boot."""

    def __init__(self):
        self.wifi_ssid = os.getenv("CIRCUITPY_WIFI_SSID")
        self.wifi_password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
        self.dashboard_url = os.getenv("DASHBOARD_URL")
        self.dashboard_api_key = os.getenv("DASHBOARD_API_KEY")
        self.event_region = os.getenv("EVENT_REGION") or ""

        self.tz_offset_hours = _get_float("TZ_OFFSET_HOURS", 0)
        self.refresh_interval = _get_float("REFRESH_INTERVAL_SECONDS", DEFAULT_REFRESH_INTERVAL)
        self.scroll_step_lines = _get_int("SCROLL_STEP_LINES", DEFAULT_SCROLL_STEP_LINES)
        self.scroll_delay = _get_float("SCROLL_DELAY_SECONDS", DEFAULT_SCROLL_DELAY)
        self.scroll_pause = _get_float("SCROLL_PAUSE_SECONDS", DEFAULT_SCROLL_PAUSE)
        self.display_width = _get_int("DISPLAY_WIDTH", DEFAULT_DISPLAY_WIDTH)
        self.display_height = _get_int("DISPLAY_HEIGHT", DEFAULT_DISPLAY_HEIGHT)

        self._validate()

    def _validate(self):
        if not self.wifi_ssid or not self.wifi_password:
            raise ConfigError(
                "CIRCUITPY_WIFI_SSID and CIRCUITPY_WIFI_PASSWORD must be set in settings.toml"
            )
        if not self.dashboard_url:
            raise ConfigError("DASHBOARD_URL must be set in settings.toml")
        if not self.dashboard_api_key:
            raise ConfigError("DASHBOARD_API_KEY must be set in settings.toml")
        if (self.display_width, self.display_height) not in VALID_DISPLAY_SIZES:
            raise ConfigError(
                "DISPLAY_WIDTH/DISPLAY_HEIGHT %sx%s is not supported; must be one of: %s"
                % (self.display_width, self.display_height, sorted(VALID_DISPLAY_SIZES))
            )
