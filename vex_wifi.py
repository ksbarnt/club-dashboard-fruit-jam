# SPDX-License-Identifier: MIT
"""WiFi (ESP32-C6 co-processor) bring-up, HTTP session, and NTP time sync.

The Fruit Jam has no native WiFi radio -- it talks to an onboard ESP32-C6
co-processor over SPI (the same "AirLift" pattern as other Adafruit boards),
so this follows the official Fruit Jam WiFi guide: ``adafruit_esp32spi`` for
the radio itself, ``adafruit_connection_manager`` for the socket pool/SSL
context, and ``adafruit_requests`` for HTTP on top of that.
"""

import time

import adafruit_connection_manager
import adafruit_requests
import board
from adafruit_esp32spi import adafruit_esp32spi
from digitalio import DigitalInOut


def connect_wifi(ssid, password, esp=None, max_attempts=10, retry_delay=2):
    """Bring up the ESP32-C6 co-processor and join ``ssid``.

    Pass an existing ``esp`` (from a prior call) to reconnect that same
    radio -- e.g. after a dropped connection -- instead of claiming the
    CS/busy/reset pins a second time, which would raise since the first
    ``ESP_SPIcontrol`` never released them.

    Returns the connected ``ESP_SPIcontrol`` instance.
    """
    if esp is None:
        esp32_cs = DigitalInOut(board.ESP_CS)
        esp32_ready = DigitalInOut(board.ESP_BUSY)
        esp32_reset = DigitalInOut(board.ESP_RESET)
        spi = board.SPI()
        esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

    attempts = 0
    while not esp.is_connected:
        attempts += 1
        try:
            esp.connect_AP(ssid, password)
        except OSError as exc:
            print("WiFi connect failed (%d/%d): %s" % (attempts, max_attempts, exc))
            if attempts >= max_attempts:
                raise
            time.sleep(retry_delay)
    return esp


def build_session(esp):
    """Build an ``adafruit_requests.Session`` (for ``VexEventsClient``) from a connected ESP."""
    pool = adafruit_connection_manager.get_radio_socketpool(esp)
    ssl_context = adafruit_connection_manager.get_radio_ssl_context(esp)
    return adafruit_requests.Session(pool, ssl_context)


def sync_time(esp, tz_offset_hours=0, retries=5, retry_delay=2):
    """Set the board's RTC via NTP so ``time.localtime()`` reflects local time.

    CircuitPython has no timezone database, so ``tz_offset_hours`` (a fixed
    hour offset from UTC, e.g. -6) is applied by the NTP client itself.
    """
    import adafruit_ntp
    import rtc

    pool = adafruit_connection_manager.get_radio_socketpool(esp)
    ntp = adafruit_ntp.NTP(pool, tz_offset=tz_offset_hours)

    last_exc = None
    for attempt in range(retries):
        try:
            rtc.RTC().datetime = ntp.datetime
            return
        except OSError as exc:
            last_exc = exc
            print("NTP sync failed (%d/%d): %s" % (attempt + 1, retries, exc))
            time.sleep(retry_delay)
    raise last_exc
