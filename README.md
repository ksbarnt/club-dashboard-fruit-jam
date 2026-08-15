# Club Dashboard - Fruit Jam

A CircuitPython dashboard for the [Adafruit Fruit Jam](https://www.adafruit.com/product/6200)
that mirrors the [desktop club dashboard app](../club-dashboard-desktop)'s three
views -- Active Today, World Skills, and Awards -- for a club/organization's
VEX teams throughout a competition season, driven straight from
events.vex.com via [`cpvexevents`](https://github.com/ksbarnt/cpvexevents).

Everything needed to run is in this folder: copy it onto the Fruit Jam's
`CIRCUITPY` drive as-is (see Install below), copy `settings.toml.example`
to `settings.toml` and fill it in, and reset.

## Hardware

- Adafruit Fruit Jam (RP2350B, ESP32-C6 WiFi co-processor, HSTX DVI output).
- An HDMI/DVI monitor or TV, connected via the Fruit Jam's DVI port.
- A USB-C power supply for the Fruit Jam.

## Buttons

| Button | View |
|---|---|
| 1 | Active Today -- teams competing today, grouped by event |
| 2 | World Skills -- world skills rankings for tracked teams |
| 3 | Awards -- awards won this season, by program |

The current view refreshes automatically every `REFRESH_INTERVAL_SECONDS`
(5 minutes by default) and whenever you switch to it. Tables taller than
the screen scroll slowly on their own, pausing at the top and bottom of
each pass.

## Install

1. Install **CircuitPython 10.x** on the Fruit Jam:
   <https://circuitpython.org/board/adafruit_fruit_jam/>
2. Copy the entire contents of this folder -- `code.py`, every `*.py` module
   next to it, and `lib/` -- onto the `CIRCUITPY` drive that appears,
   preserving the folder structure. `lib/` already contains every
   third-party library this project needs (see below); nothing else to
   install with `circup` or `mip`.
3. Copy `settings.toml.example` to `settings.toml` on the `CIRCUITPY`
   drive and fill it in: WiFi credentials, your VEX Events API token,
   event region, season ids, and the list of teams to track. Every
   setting is documented inline in that file. `settings.toml` holds
   secrets, so it's gitignored -- only the `.example` is committed.
4. The board reloads automatically when `settings.toml` (or any other
   file) is saved. On first boot with valid settings it connects to
   WiFi, syncs the clock over NTP, and shows the Active Today view.

## Configuration

All configuration lives in `settings.toml` (copied from
`settings.toml.example`) -- see the comments in that file for the full
reference. In short:

- `CIRCUITPY_WIFI_SSID` / `CIRCUITPY_WIFI_PASSWORD` -- your network.
- `VEX_API_TOKEN` -- a bearer token from your events.vex.com account
  (My Account -> Developer / API Settings -> Generate Token).
- `EVENT_REGION`, `VIQRC_SEASON_ID`, `V5RC_SEASON_ID` -- same settings as
  the desktop app's Settings view.
- `TEAMS` -- `number:program:grade` triplets, comma-separated, e.g.
  `"1234A:V5RC:HS,5678B:VIQRC:MS"`. Any number of teams is supported.
- `TZ_OFFSET_HOURS` -- CircuitPython has no timezone database, so "today"
  (for the Active Today view) is computed from a fixed UTC offset.
- Everything else (refresh interval, scroll speed, display resolution)
  has a sensible default and rarely needs changing.

## Project layout

```
code.py              Entry point: boot sequence + main loop
config.py            settings.toml -> validated Config object
hardware.py          picodvi display + button setup
vex_wifi.py          ESP32-C6 WiFi bring-up, HTTP session, NTP time sync
vex_data.py          Fetches + shapes data for the three dashboards
json_stream.py        Streaming JSON parser (see "World Skills memory use" below)
dashboard_ui.py       Screen shell: header, fixed column-header bar, footer, scroll area
ui_theme.py           Color palette
ui_widgets.py         Label/rect helpers + the auto-scroll engine
view_active.py         Active Today table renderer
view_world_skills.py   World Skills table renderer
view_awards.py         Awards table renderer
settings.toml.example  Configuration template -- copy to settings.toml and fill in
lib/                  Vendored third-party CircuitPython libraries
sd/                   Reserved for SD card contents
```

## World Skills memory use

The world skills rankings endpoint is unauthenticated, unpaginated, and
returns *every* team in a season/grade level in one response -- several
megabytes of JSON for a busy grade level. That's too large to decode into
one big list of dicts on a microcontroller alongside everything else the
board is holding in RAM. `vex_data.py` streams that response through
`json_stream.py` and keeps only the rows for your tracked teams as they
arrive, computing each one's regional rank from a running counter in the
same pass, rather than ever materializing the full list.

## Libraries

`lib/` vendors everything this project depends on, each under its
original MIT license (see the SPDX header at the top of each file):

- [`cpvexevents`](https://github.com/ksbarnt/cpvexevents) -- the VEX
  Events API client this dashboard is built on.
- `adafruit_esp32spi`, `adafruit_bus_device` -- ESP32-C6 co-processor
  WiFi driver.
- `adafruit_connection_manager`, `adafruit_requests` -- HTTP on top of
  the WiFi radio.
- `adafruit_ntp` -- clock sync.
- `adafruit_display_text` -- on-screen text labels.

## Troubleshooting

- **Blank/black screen at boot**: check `DISPLAY_WIDTH`/`DISPLAY_HEIGHT`
  in `settings.toml` are a supported pair (320x240, 360x200, 640x480, or
  720x400) and that the monitor supports that resolution over DVI/HDMI.
- **"Dashboard configuration error" screen**: the message names the
  missing/invalid `settings.toml` key -- fix it and save again.
- **Status bar shows a VEX API error**: double check `VEX_API_TOKEN` and
  that `VIQRC_SEASON_ID`/`V5RC_SEASON_ID` are real season ids for the
  program(s) you're tracking.
- **A team never shows up**: the status bar surfaces "number not found"
  warnings -- check the team number and program in `TEAMS` match what
  events.vex.com has on record.
- Serial console output (`code.py`'s `print()` calls) is visible over USB
  in a serial terminal or the Mu editor's REPL if you need more detail
  than the on-screen status bar shows.

## License

This project is licensed under the [MIT License](LICENSE). The vendored
libraries in `lib/` keep their own original MIT licenses (see the SPDX
header at the top of each file).
