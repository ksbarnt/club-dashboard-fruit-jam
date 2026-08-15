# SPDX-License-Identifier: MIT
"""VEX Events data-fetching layer for the three dashboards.

Ports the business logic of the desktop app's ``app/api/*.py`` modules
(active teams, world skills, awards) onto ``cpvexevents``. Two differences
from the desktop version, both forced by running on a microcontroller
instead of a desktop Python process:

* Fetches run sequentially, not fanned out across a thread pool -- there's
  one ESP32 SPI link and no ``concurrent.futures`` here.
* World skills rankings are streamed and filtered down to the tracked
  teams as they arrive (see ``_fetch_world_skills_group`` /
  ``json_stream``) rather than decoded into one big list first -- a
  single grade level's unfiltered rankings can run several megabytes of
  JSON, which does not comfortably fit as a fully-decoded list of dicts
  on top of everything else this board is holding in RAM.
"""

import gc
import json

from cpvexevents import VexEventsNotFoundError, WORLD_SKILLS_BASE_URL

from json_stream import iter_json_array_objects

PROGRAM_TABLE_KEY = {"VIQRC": "IQ", "V5RC": "V5"}

# Grade code -> pre-percent-encoded SkillsGradeLevel query value. The world
# skills endpoint's grade_level vocabulary ("Elementary", not "Elementary
# School") only has these three fixed values, so a hand-rolled percent
# encoder (which CircuitPython doesn't ship anyway) isn't needed.
_GRADE_LEVEL_QUERY = {"ES": "Elementary", "MS": "Middle%20School", "HS": "High%20School"}

WORLD_SKILLS_GROUP_ORDER = [("VIQRC", "ES"), ("VIQRC", "MS"), ("V5RC", "MS"), ("V5RC", "HS")]

_WORLD_SKILLS_HEADERS = {"Accept": "application/json"}


def team_sort_key(number):
    """Sort team numbers numerically-then-alphabetically (e.g. "2A" < "10B")."""
    number = number or ""
    i = 0
    while i < len(number) and number[i].isdigit():
        i += 1
    if i == 0:
        return (0, number)
    return (int(number[:i]), number[i:])


def world_skills_group_sort_key(program, grade):
    try:
        return WORLD_SKILLS_GROUP_ORDER.index((program, grade))
    except ValueError:
        return len(WORLD_SKILLS_GROUP_ORDER)


def today_bounds(now_struct):
    """RFC3339 start/end-of-day strings for a ``time.struct_time`` in local time."""
    date_str = "%04d-%02d-%02d" % (now_struct[0], now_struct[1], now_struct[2])
    return date_str + "T00:00:00", date_str + "T23:59:59"


def _format_event_date(start):
    """RFC3339 datetime -> "M/D" (no leading zeros, no year).

    CircuitPython has no ``datetime`` module, but RFC3339 dates always put
    the year/month/day at fixed offsets, so a plain slice + int() stands in
    for ``datetime.fromisoformat()``.
    """
    if not start or len(start) < 10:
        return None
    try:
        month = int(start[5:7])
        day = int(start[8:10])
    except ValueError:
        return None
    return "%d/%d" % (month, day)


def _format_event_label(city, start):
    date_str = _format_event_date(start)
    if city and date_str:
        return "%s %s" % (city, date_str)
    return city or date_str


def _resolve_team_id(client, program_ids, number, program_abbr):
    """Team number + program abbreviation -> numeric team id, or None."""
    program_id = program_ids.get(program_abbr)
    programs = [program_id] if program_id is not None else None
    page = client.get_teams(numbers=[number], programs=programs)
    data = page.get("data") or []
    for team in data:
        team_program = team.get("program") or {}
        if program_id is not None and team_program.get("id") == program_id:
            return team["id"]
        if team_program.get("code") == program_abbr:
            return team["id"]
    return data[0]["id"] if data and program_id is None else None


def _event_details(client, event_id):
    """{"city": ..., "start": ...} for an event, or None if not found."""
    try:
        event = client.get_event(event_id)
    except VexEventsNotFoundError:
        return None
    location = event.get("location") or {}
    return {"city": location.get("city"), "start": event.get("start")}


def _fetch_team_event_detail(client, team_id, event_id):
    event_rank = None
    try:
        page = client.get_team_rankings(team_id, events=[event_id])
        rankings = page.get("data") or []
        if rankings:
            event_rank = rankings[0].get("rank")
    except VexEventsNotFoundError:
        pass

    skills_rank = None
    driver_score = driver_attempts = None
    auto_score = auto_attempts = None
    try:
        page = client.get_team_skills(team_id, events=[event_id])
        for skill in page.get("data") or []:
            if skill.get("rank") is not None:
                skills_rank = skill.get("rank")
            skill_type = skill.get("type")
            if skill_type == "driver":
                driver_score = skill.get("score")
                driver_attempts = skill.get("attempts")
            elif skill_type == "programming":
                auto_score = skill.get("score")
                auto_attempts = skill.get("attempts")
    except VexEventsNotFoundError:
        pass

    return {
        "eventRank": event_rank,
        "skillsRank": skills_rank,
        "driverScore": driver_score,
        "driverAttempts": driver_attempts,
        "autoScore": auto_score,
        "autoAttempts": auto_attempts,
    }


class VexData(object):
    """Fetch + shape data for the three dashboards from one VexEventsClient.

    Team-id and event-detail lookups are cached for the life of this object
    (they're effectively immutable), matching the desktop app's TTL cache
    for the same lookups -- there's just one "session" here, so a plain
    dict is enough.
    """

    def __init__(self, client, session):
        self._client = client
        self._session = session
        self._program_ids = None
        self._team_id_cache = {}
        self._event_cache = {}

    def _program_id_map(self):
        if self._program_ids is None:
            mapping = {}
            for program in self._client.iter_programs():
                abbr = program.get("abbr")
                if abbr:
                    mapping[abbr] = program["id"]
            self._program_ids = mapping
        return self._program_ids

    def resolve_team_id(self, number, program_abbr):
        key = (number, program_abbr)
        if key not in self._team_id_cache:
            self._team_id_cache[key] = _resolve_team_id(
                self._client, self._program_id_map(), number, program_abbr
            )
        return self._team_id_cache[key]

    def event_details(self, event_id):
        if event_id not in self._event_cache:
            self._event_cache[event_id] = _event_details(self._client, event_id)
        return self._event_cache[event_id]

    # -- Active Teams dashboard ------------------------------------------

    def fetch_active_teams(self, teams_cfg, today_start, today_end):
        warnings = []
        groups = {"IQ": {}, "V5": {}}

        for team_cfg in teams_cfg:
            table_key = PROGRAM_TABLE_KEY.get(team_cfg["program"])
            if table_key is None:
                continue

            team_id = self.resolve_team_id(team_cfg["number"], team_cfg["program"])
            if team_id is None:
                warnings.append(
                    "Team %s (%s): number not found" % (team_cfg["number"], team_cfg["program"])
                )
                continue

            page = self._client.get_team_events(team_id, start=today_start, end=today_end)
            events = page.get("data") or []
            for event in events:
                detail = _fetch_team_event_detail(self._client, team_id, event["id"])
                event_id = event["id"]
                bucket = groups[table_key].setdefault(
                    event_id, {"eventId": event_id, "eventName": event.get("name"), "teams": []}
                )
                row = {"number": team_cfg["number"]}
                row.update(detail)
                bucket["teams"].append(row)
            gc.collect()

        def _finalize(table_key):
            event_groups = list(groups[table_key].values())
            event_groups.sort(key=lambda g: g["eventName"] or "")
            for g in event_groups:
                g["teams"].sort(
                    key=lambda t: (
                        t["eventRank"] is None,
                        t["eventRank"] if t["eventRank"] is not None else 0,
                    )
                )
            return event_groups

        return {"IQ": _finalize("IQ"), "V5": _finalize("V5"), "warnings": warnings}

    # -- Awards dashboard --------------------------------------------------

    def fetch_awards(self, teams_cfg, season_ids):
        warnings = []
        buckets = {"VIQRC": [], "V5RC": []}

        for team_cfg in teams_cfg:
            bucket = buckets.get(team_cfg["program"])
            if bucket is None:
                continue

            team_id = self.resolve_team_id(team_cfg["number"], team_cfg["program"])
            if team_id is None:
                warnings.append(
                    "Team %s (%s): number not found" % (team_cfg["number"], team_cfg["program"])
                )
                continue

            season_id = season_ids.get(team_cfg["program"])
            if season_id is None:
                continue

            page = self._client.get_team_awards(team_id, seasons=[season_id])
            team_awards = page.get("data") or []
            if not team_awards:
                continue

            by_event = {}
            for award in team_awards:
                event_id = (award.get("event") or {}).get("id")
                by_event.setdefault(event_id, []).append(award)

            events_out = []
            for event_id, award_list in by_event.items():
                award_list.sort(key=lambda a: a.get("order") if a.get("order") is not None else 0)
                info = self.event_details(event_id) if event_id is not None else None
                info = info or {}
                events_out.append(
                    {
                        "eventId": event_id,
                        "eventLabel": _format_event_label(info.get("city"), info.get("start")),
                        "_start": info.get("start") or "",
                        "awards": [{"title": a.get("title"), "order": a.get("order")} for a in award_list],
                    }
                )
            events_out.sort(key=lambda e: e["_start"])
            for event_out in events_out:
                event_out.pop("_start", None)

            bucket.append({"number": team_cfg["number"], "events": events_out})
            gc.collect()

        for key in buckets:
            buckets[key].sort(key=lambda t: team_sort_key(t["number"]))

        return {"VIQRC": buckets["VIQRC"], "V5RC": buckets["V5RC"], "warnings": warnings}

    # -- World Skills dashboard --------------------------------------------

    def _fetch_world_skills_group(self, season_id, grade_query, wanted_numbers, event_region):
        """Stream one season/grade's world skills rankings, keeping only
        rows for ``wanted_numbers`` while tallying each row's 1-based
        position within ``event_region`` as it goes (the API already
        returns rows in ascending world-rank order, so a running counter
        gives each matched team's regional rank without a second pass).
        """
        url = "%s/seasons/%s/skills?grade_level=%s" % (WORLD_SKILLS_BASE_URL, season_id, grade_query)
        resp = self._session.get(url, headers=_WORLD_SKILLS_HEADERS, timeout=25)
        results = {}
        remaining = set(wanted_numbers)
        region_rank = 0
        count = 0
        try:
            for raw in iter_json_array_objects(resp.iter_content(chunk_size=512)):
                count += 1
                try:
                    entry = json.loads(raw)
                except ValueError:
                    continue

                team_info = entry.get("team") or {}
                in_region = bool(event_region) and team_info.get("eventRegion") == event_region
                if in_region:
                    region_rank += 1

                number = team_info.get("team")
                if number in remaining:
                    scores = entry.get("scores") or {}
                    results[number] = {
                        "number": number,
                        "regionalRank": region_rank if in_region else None,
                        "worldRank": entry.get("rank"),
                        "overallScore": scores.get("score"),
                        "driverScore": scores.get("driver"),
                        "autoScore": scores.get("programming"),
                    }
                    remaining.discard(number)

                if count % 200 == 0:
                    gc.collect()
        finally:
            resp.close()
        return results

    def fetch_world_skills(self, teams_cfg, event_region, season_ids):
        combos = {}
        for team_cfg in teams_cfg:
            key = (team_cfg["program"], team_cfg["grade"])
            combos.setdefault(key, []).append(team_cfg)

        groups = []
        for (program, grade), members in combos.items():
            season_id = season_ids.get(program)
            grade_query = _GRADE_LEVEL_QUERY.get(grade)
            if season_id is None or grade_query is None:
                continue

            wanted = set(m["number"] for m in members)
            matches = self._fetch_world_skills_group(season_id, grade_query, wanted, event_region)
            gc.collect()

            rows = [matches[m["number"]] for m in members if m["number"] in matches]
            if rows:
                rows.sort(key=lambda r: (r["regionalRank"] is None, r["regionalRank"] or 0))
                groups.append({"program": program, "grade": grade, "teams": rows})

        groups.sort(key=lambda g: world_skills_group_sort_key(g["program"], g["grade"]))
        return {"groups": groups}
