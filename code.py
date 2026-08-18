# SPDX-License-Identifier: MIT
"""Club Dashboard for the Adafruit Fruit Jam.

Boots the display, joins WiFi, syncs the clock, then loops: Button 1 shows
today's Active Teams, Button 2 shows World Skills, Button 3 shows Awards.
Active Today refreshes automatically every REFRESH_INTERVAL_SECONDS;
World Skills and Awards are refetched at most once per local calendar day
(see get_daily()/vex_cache.py), checked whenever their view is selected.
Tables taller than the screen page through their rows automatically,
column headers staying fixed. All configuration lives in settings.toml
-- see README.md.
"""

import gc
import time

import ui_theme
import vex_cache
import view_active
import view_awards
import view_world_skills
from config import Config, ConfigError
from dashboard_client import DashboardClient, DashboardError, DashboardNotAvailableError
from dashboard_ui import VIEWS, DashboardUI
from hardware import Buttons, init_display, mount_sd_card
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
    mount_sd_card()  # optional -- world_skills/awards just won't persist without a card
    ui = DashboardUI(display, config)

    def set_view_header(view):
        """Column labels for the fixed header bar -- separate from
        refresh_view() since they don't depend on fetched data, only on
        which view is showing (and, for World Skills, the event region)."""
        if view == "active":
            ui.set_table_header(lambda g: view_active.build_header(g, ui.font, ui.width))
        elif view == "world_skills":
            ui.set_table_header(
                lambda g: view_world_skills.build_header(g, ui.font, ui.width, config.event_region)
            )
        else:
            ui.set_table_header(lambda g: view_awards.build_header(g, ui.font, ui.width))

    ui.set_active_view("active")
    set_view_header("active")
    ui.set_status("Connecting to WiFi...")

    esp = connect_wifi(config.wifi_ssid, config.wifi_password)
    session = build_session(esp)

    ui.set_status("Syncing clock...")
    try:
        sync_time(esp, tz_offset_hours=config.tz_offset_hours)
    except Exception as exc:  # noqa: BLE001 - best-effort, dashboard still works without it
        print("NTP sync failed, continuing with board clock:", exc)
    last_time_sync = time.monotonic()

    client = DashboardClient(session, config.dashboard_url, config.dashboard_api_key)

    buttons = Buttons()
    current_view = "active"
    last_refresh = {view: 0 for view in VIEWS}

    # In-memory copy of each once-a-day dataset for this session, seeded
    # lazily from the SD card cache the first time it's needed.
    daily_cache = {"world_skills": None, "awards": None}

    def ensure_wifi():
        if not esp.is_connected:
            ui.set_status("WiFi dropped, reconnecting...")
            connect_wifi(config.wifi_ssid, config.wifi_password, esp=esp)

    def get_daily(key, fetch_fn):
        """Fetch result for a once-a-day dataset (world_skills/awards):
        reuse today's cached copy (in memory, or on the SD card from an
        earlier boot today) if there is one, otherwise fetch fresh and
        persist it -- so this hits the network at most once per local
        calendar day no matter how often the view is switched to."""
        cached = daily_cache[key]
        if cached is None:
            cached = vex_cache.load(key)
            daily_cache[key] = cached
        if cached is not None and vex_cache.is_fresh(cached):
            return cached["data"]

        ensure_wifi()
        result = fetch_fn()
        daily_cache[key] = {"fetched_at": int(time.time()), "data": result}
        vex_cache.save(key, result)
        return result

    def refresh_view(view):
        ui.set_status("Loading %s..." % view.replace("_", " "))
        try:
            if view == "active":
                ensure_wifi()
                result = client.get_active_teams()
                ui.render(view_active.build(result, ui.font, ui.width, ui.viewport_height))
            elif view == "world_skills":
                result = get_daily("world_skills", client.get_world_skills)
                ui.render(view_world_skills.build(result, ui.font, ui.width, ui.viewport_height))
            else:
                result = get_daily("awards", client.get_awards)
                ui.render(view_awards.build(result, ui.font, ui.width, ui.viewport_height))

            warnings = result.get("warnings") or []
            ui.set_status(warnings[0] if warnings else "")
        except DashboardNotAvailableError:
            print("No cached data yet for %s" % view)
            ui.set_status("No data yet -- open the dashboard site once to populate it")
        except DashboardError as exc:
            print("Dashboard API error refreshing %s: %s" % (view, exc))
            ui.set_status("Dashboard API error: %s" % exc)
        except Exception as exc:  # noqa: BLE001 - keep the dashboard alive on any fetch failure
            print("Error refreshing %s: %s" % (view, exc))
            ui.set_status("Error: %s" % exc)
        last_refresh[view] = time.monotonic()
        gc.collect()

    ui.set_active_view(current_view)
    set_view_header(current_view)
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
                set_view_header(current_view)
                refresh_view(current_view)
            last_button_states[i] = states[i]

        # Only Active Today refreshes on a timer -- World Skills/Awards are
        # gated to once a day inside get_daily() and only checked again
        # when the user switches back to that view (button press, above).
        if current_view == "active" and now - last_refresh[current_view] >= config.refresh_interval:
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
