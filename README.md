# Club Dashboard - Fruit Jam

A CircuitPython dashboard for the [Adafruit Fruit Jam](https://www.adafruit.com/product/6200)
that mirrors the [desktop club dashboard app](../club-dashboard-desktop)'s three
views -- Active Today, World Skills, and Awards -- for a club/organization's
VEX teams throughout a competition season, driven from a
[club-dashboard-web](../club-dashboard-web) deployment's cached
`/api/external/*` data (itself fetched from events.vex.com server-side --
this device never talks to VEX directly).

Everything needed to run is in this folder: copy it onto the Fruit Jam's
`CIRCUITPY` drive as-is (see Install below), copy `settings.toml.example`
to `settings.toml` and fill it in, and reset.

## Hardware

- Adafruit Fruit Jam (RP2350B, ESP32-C6 WiFi co-processor, HSTX DVI output).
- An HDMI/DVI monitor or TV, connected via the Fruit Jam's DVI port.
- A USB-C power supply for the Fruit Jam.
- Optional: a microSD card in the Fruit Jam's SD slot, for World
  Skills/Awards caching (see "Once-a-day caching" below). The dashboard
  runs fine without one -- it just refetches that data every time it's
  viewed instead of at most once a day.

## Buttons

| Button | View |
|---|---|
| 1 | Active Today -- teams competing today, grouped by event |
| 2 | World Skills -- world skills rankings for tracked teams |
| 3 | Awards -- awards won this season, by program |

Active Today refreshes automatically every `REFRESH_INTERVAL_SECONDS` (5
minutes by default). World Skills and Awards are refetched at most once
per local calendar day instead -- see "Once-a-day caching" below --
checked whenever you switch to either view. Tables taller than the
screen page through their rows automatically, holding each page for
`PAGE_PAUSE_SECONDS` (8 seconds by default) before advancing to the
next and looping back to the first page after the last; column headers
stay fixed while only the table body paginates.

## Status LEDs

The Fruit Jam's 5 onboard NeoPixels double as an at-a-glance status
strip, left to right:

| Pixel | Meaning |
|---|---|
| 1 | Blue while WiFi is connected, off otherwise. |
| 2 | Yellow while a dashboard fetch is in progress, off otherwise. |
| 3 | Active Today: green if the last fetch found cached data on club-dashboard-web, red if it doesn't have any cached yet, off if not checked yet this boot. |
| 4 | World Skills: same green/red/off meaning as pixel 3. |
| 5 | Awards: same green/red/off meaning as pixel 3. |

Red mirrors the on-screen "No data yet" status (see "Status bar shows
'No data yet'" below) -- it means club-dashboard-web itself has no
cached data for that view yet, not a problem with this device.

## Install

1. Install **CircuitPython 10.x** on the Fruit Jam:
   <https://circuitpython.org/board/adafruit_fruit_jam/>
2. Copy the entire contents of this folder -- `code.py`, every `*.py` module
   next to it, and `lib/` -- onto the `CIRCUITPY` drive that appears,
   preserving the folder structure. `lib/` already contains every
   third-party library this project needs (see below); nothing else to
   install with `circup` or `mip`.
3. Copy `settings.toml.example` to `settings.toml` on the `CIRCUITPY`
   drive and fill it in: WiFi credentials, your club-dashboard-web URL
   and API key, and the (cosmetic) event region label. Every setting is
   documented inline in that file. `settings.toml` holds secrets, so
   it's gitignored -- only the `.example` is committed.
4. The board reloads automatically when `settings.toml` (or any other
   file) is saved. On first boot with valid settings it connects to
   WiFi, syncs the clock over NTP, and shows the Active Today view.

## Configuration

All configuration lives in `settings.toml` (copied from
`settings.toml.example`) -- see the comments in that file for the full
reference. In short:

- `CIRCUITPY_WIFI_SSID` / `CIRCUITPY_WIFI_PASSWORD` -- your network.
- `DASHBOARD_URL` -- base URL of your [club-dashboard-web](../club-dashboard-web)
  deployment (no trailing slash), reachable from the Fruit Jam's WiFi network.
- `DASHBOARD_API_KEY` -- the raw static API key club-dashboard-web was
  configured with (matches the `API_KEY_SHA256` hash in that project's
  `.env` -- pass the raw value here, not the hash).
- `EVENT_REGION` -- **display-only**: labels the World Skills view's
  regional-rank column (e.g. "Michigan Rk"). It no longer filters or
  selects any data -- team roster, season ids, and region are entirely
  controlled by club-dashboard-web's own Settings page now. Keep this in
  sync by hand if you want the label to stay accurate.
- `TZ_OFFSET_HOURS` -- CircuitPython has no timezone database, so "today"
  (for the Active Today view) is computed from a fixed UTC offset.
- Everything else (refresh interval, page dwell time, display resolution)
  has a sensible default and rarely needs changing.

## Project layout

```
code.py              Entry point: boot sequence + main loop
config.py            settings.toml -> validated Config object
hardware.py          picodvi display, button, and SD card setup
vex_wifi.py          ESP32-C6 WiFi bring-up, HTTP session, NTP time sync
vex_cache.py          SD card cache for once-a-day World Skills/Awards data
dashboard_ui.py       Screen shell: header, fixed column-header bar, footer, page area
ui_theme.py           Color palette
ui_widgets.py         Label/rect helpers + the page-advance engine
ui_pagination.py       Shared header+rows pagination helper (Active Today, World Skills)
view_active.py         Active Today table renderer
view_world_skills.py   World Skills table renderer
view_awards.py         Awards table renderer
settings.toml.example  Configuration template -- copy to settings.toml and fill in
lib/                  Vendored third-party libraries, plus dashboard_client.mpy
                       (in-house client for club-dashboard-web's external API)
                       -- everything here is pre-compiled to .mpy bytecode
sd/                   Reserved for SD card contents
```

## Once-a-day caching

World Skills and Awards each mean walking the whole roster for every
tracked team -- by far the most network/CPU work an update of this
dashboard does, and data that only meaningfully changes a few times a
season. Rather than refetching on the same timer as Active Today, each
is fetched at most once per local calendar day: the first time you
switch to that view each day it fetches and saves a copy to the SD card
(`/sd/world_skills_cache.json`, `/sd/awards_cache.json`) along with the
time it was fetched; switching to that view again the same day -- even
after a reboot -- reuses that copy instead of hitting the network again.
Without an SD card, this still works within a single boot (kept in
memory), it just can't survive a reboot, so it refetches once after
power-up. Note that "fresh" here only means fresh according to this
device's own fetch -- club-dashboard-web has its own separate cache
(see "Status bar shows 'No data yet'" below), and this device has no way
to force a refresh on that side.

## Libraries

`lib/` vendors everything this project depends on, each under its
original MIT license, plus one in-house module. Every file in `lib/`
is shipped pre-compiled to `.mpy` bytecode (built with `mpy-cross` from
the matching CircuitPython release) rather than as `.py` source, to
save flash space and speed up import at boot; the original MIT-licensed
`.py` sources remain available from each library's upstream repo:

- `dashboard_client.mpy` -- this project's own client for
  club-dashboard-web's `/api/external/*` cached-data API (not vendored
  third-party code).
- `adafruit_esp32spi`, `adafruit_bus_device` -- ESP32-C6 co-processor
  WiFi driver.
- `adafruit_connection_manager`, `adafruit_requests` -- HTTP on top of
  the WiFi radio.
- `adafruit_ntp` -- clock sync.
- `adafruit_display_text` -- on-screen text labels.
- `adafruit_sdcard` -- SD card driver, for World Skills/Awards caching.
- `neopixel`, `adafruit_pixelbuf` -- drives the onboard status LEDs (see
  "Status LEDs" above).

## Troubleshooting

- **Blank/black screen at boot**: check `DISPLAY_WIDTH`/`DISPLAY_HEIGHT`
  in `settings.toml` are a supported pair (320x240, 360x200, 640x480, or
  720x400) and that the monitor supports that resolution over DVI/HDMI.
- **"Dashboard configuration error" screen**: the message names the
  missing/invalid `settings.toml` key -- fix it and save again.
- **Status bar shows a Dashboard API error**: check `DASHBOARD_URL` is
  reachable from the Fruit Jam's WiFi network and that `DASHBOARD_API_KEY`
  matches a key club-dashboard-web recognizes -- a 401 means a bad or
  missing key.
- **Status bar shows "No data yet"**: club-dashboard-web hasn't cached
  that view yet (nobody has loaded its dashboard page in a browser to
  populate it) -- open club-dashboard-web's site once to populate it.
- **A team never shows up**: the status bar surfaces "number not found"
  warnings passed through from club-dashboard-web -- check the team
  roster on club-dashboard-web's own Settings page, not anything local
  to this device.
- **World Skills/Awards look stale**: they only refetch once per local
  calendar day (see "Once-a-day caching"). Delete
  `/sd/world_skills_cache.json` / `/sd/awards_cache.json` from the SD
  card (or just switch views on a new day) to force a refetch -- though
  note this only forces *this device* to refetch from club-dashboard-web;
  if club-dashboard-web's own cache is what's stale, see "Status bar
  shows 'No data yet'" above.
- Serial console output (`code.py`'s `print()` calls) is visible over USB
  in a serial terminal or the Mu editor's REPL if you need more detail
  than the on-screen status bar shows.

## License

This project is licensed under the [MIT License](LICENSE). The vendored
libraries in `lib/` keep their own original MIT licenses -- see the
SPDX header at the top of each library's upstream `.py` source (the
compiled `.mpy` files shipped here don't carry the header text).
