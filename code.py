# SPDX-License-Identifier: MIT
"""Club Dashboard for the Adafruit Fruit Jam.

Boots the display, joins WiFi, syncs the clock, then loops: Button 1 shows
today's Active Teams, Button 2 shows World Skills, Button 3 shows Awards.
Data refreshes automatically every REFRESH_INTERVAL_SECONDS (and whenever
a view is (re)selected); tables taller than the screen scroll slowly on
their own. All configuration lives in settings.toml -- see README.md.
"""

import gc
import time

import ui_theme
import vex_data
import view_active
import view_awards
import view_world_skills
from config import Config, ConfigError
from cpvexevents import VexEventsClient, VexEventsError
from dashboard_ui import VIEWS, DashboardUI
from hardware import Buttons, init_display
from vex_wifi import build_session, connect_wifi, sync_time

TIME_SYNC_INTERVAL = 3600
BUTTON_DEBOUNCE_SECONDS = 0.25


def _fatal_screen(display, message):
    """Best-effort full-screen error display for problems that happen
    before the normal UI (e.g. bad settings.toml) can be built."""
    import displayio
    import terminalio

    from ui_widgets import make_label, make_rect

    print("FATAL:", message)
    root = displayio.Group()
    root.append(make_rect(display.width, display.height, ui_theme.SURFACE))
    root.append(
        make_label(terminalio.FONT, "Dashboard configuration error:", ui_theme.WARNING, 10, 30)
    )
    y = 60
    line = ""
    for word in str(message).split(" "):
        candidate = (line + " " + word).strip()
        if len(candidate) > 70:
            root.append(make_label(terminalio.FONT, line, ui_theme.TEXT_PRIMARY, 10, y))
            y += 20
            line = word
        else:
            line = candidate
    if line:
        root.append(make_label(terminalio.FONT, line, ui_theme.TEXT_PRIMARY, 10, y))
    display.root_group = root
    while True:
        time.sleep(1)


def _format_clock(now_struct):
    return "%02d:%02d:%02d" % (now_struct[3], now_struct[4], now_struct[5])


def main():
    try:
        config = Config()
    except ConfigError as exc:
        _fatal_screen(init_display(), exc)
        return

    display = init_display(config.display_width, config.display_height)
    ui = DashboardUI(display, config)
    ui.set_active_view("active")
    ui.set_status("Connecting to WiFi...")

    esp = connect_wifi(config.wifi_ssid, config.wifi_password)
    session = build_session(esp)

    ui.set_status("Syncing clock...")
    try:
        sync_time(esp, tz_offset_hours=config.tz_offset_hours)
    except Exception as exc:  # noqa: BLE001 - best-effort, dashboard still works without it
        print("NTP sync failed, continuing with board clock:", exc)
    last_time_sync = time.monotonic()

    client = VexEventsClient(session, token=config.api_token)
    data = vex_data.VexData(client, session)
    season_ids = {"VIQRC": config.viqrc_season_id, "V5RC": config.v5rc_season_id}

    buttons = Buttons()
    current_view = "active"
    last_refresh = {view: 0 for view in VIEWS}

    def ensure_wifi():
        if not esp.is_connected:
            ui.set_status("WiFi dropped, reconnecting...")
            connect_wifi(config.wifi_ssid, config.wifi_password, esp=esp)

    def refresh_view(view):
        ui.set_status("Loading %s..." % view.replace("_", " "))
        try:
            ensure_wifi()
            if view == "active":
                start, end = vex_data.today_bounds(time.localtime())
                result = data.fetch_active_teams(config.teams, start, end)
                ui.render(lambda g: view_active.build(g, result, ui.font, ui.width))
            elif view == "world_skills":
                result = data.fetch_world_skills(config.teams, config.event_region, season_ids)
                ui.render(lambda g: view_world_skills.build(g, result, ui.font, ui.width))
            else:
                result = data.fetch_awards(config.teams, season_ids)
                ui.render(lambda g: view_awards.build(g, result, ui.font, ui.width))

            warnings = result.get("warnings") or []
            ui.set_status(warnings[0] if warnings else "")
        except VexEventsError as exc:
            print("VEX Events API error refreshing %s: %s" % (view, exc))
            ui.set_status("VEX API error: %s" % exc)
        except Exception as exc:  # noqa: BLE001 - keep the dashboard alive on any fetch failure
            print("Error refreshing %s: %s" % (view, exc))
            ui.set_status("Error: %s" % exc)
        last_refresh[view] = time.monotonic()
        gc.collect()

    ui.set_active_view(current_view)
    refresh_view(current_view)

    last_button_states = [False, False, False]
    last_press_time = [0.0, 0.0, 0.0]
    while True:
        now = time.monotonic()

        states = buttons.pressed()
        for i, view in enumerate(VIEWS):
            newly_pressed = states[i] and not last_button_states[i]
            debounced = (now - last_press_time[i]) >= BUTTON_DEBOUNCE_SECONDS
            if newly_pressed and debounced:
                last_press_time[i] = now
                current_view = view
                ui.set_active_view(current_view)
                refresh_view(current_view)
            last_button_states[i] = states[i]

        if now - last_refresh[current_view] >= config.refresh_interval:
            refresh_view(current_view)

        if now - last_time_sync >= TIME_SYNC_INTERVAL:
            try:
                sync_time(esp, tz_offset_hours=config.tz_offset_hours)
            except Exception as exc:  # noqa: BLE001 - best-effort periodic re-sync
                print("Periodic NTP re-sync failed:", exc)
            last_time_sync = now

        ui.set_clock(_format_clock(time.localtime()))
        ui.tick()
        time.sleep(0.01)


main()
