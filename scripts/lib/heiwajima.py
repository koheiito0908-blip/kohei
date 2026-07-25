"""Heiwajima (平和島, jcd=04) race data collection.

Thin orchestration layer around the `metaboatrace.scrapers` library: builds
the official page URLs for a given date/race, fetches them politely, and
merges the parsed racelist / beforeinfo / raceresult pages into one
JSON-serialisable dict per race.
"""
from __future__ import annotations

import io
from dataclasses import asdict, is_dataclass
from datetime import date
from enum import Enum
from typing import Any

from metaboatrace.models.stadium import StadiumTelCode
from metaboatrace.scrapers.official.website.exceptions import DataNotFound, RaceCanceled
from metaboatrace.scrapers.official.website.v1707.pages.race.before_information_page.location import (
    create_race_before_information_page_url,
)
from metaboatrace.scrapers.official.website.v1707.pages.race.before_information_page.scraping import (
    extract_boat_settings,
    extract_circumference_exhibition_records,
    extract_start_exhibition_records,
)
from metaboatrace.scrapers.official.website.v1707.pages.race.before_information_page.scraping import (
    extract_weather_condition as extract_before_weather_condition,
)
from metaboatrace.scrapers.official.website.v1707.pages.race.entry_page.location import (
    create_race_entry_page_url,
)
from metaboatrace.scrapers.official.website.v1707.pages.race.entry_page.scraping import (
    extract_boat_performances,
    extract_motor_performances,
    extract_race_entries,
    extract_race_information,
    extract_racer_performances,
    extract_racers,
)
from metaboatrace.scrapers.official.website.v1707.pages.race.result_page.location import (
    create_race_result_page_url,
)
from metaboatrace.scrapers.official.website.v1707.pages.race.result_page.scraping import (
    extract_race_payoffs,
    extract_race_records,
)

from .http import fetch_text

STADIUM = StadiumTelCode.HEIWAJIMA


def _to_jsonable(value: Any) -> Any:
    """Recursively convert pydantic models / dataclasses / enums to plain
    JSON-safe Python values."""
    if isinstance(value, Enum):
        return value.name
    if hasattr(value, "model_dump"):  # pydantic BaseModel
        return _to_jsonable(value.model_dump())
    if is_dataclass(value) and not isinstance(value, type):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, date):
        return value.isoformat()
    return value


def fetch_race(race_date: date, race_number: int, *, delay: float = 0.4) -> dict | None:
    """Fetch and merge one Heiwajima race across the three official pages.

    Returns None if the race simply doesn't exist for that date (used by the
    caller to know when to stop iterating race numbers for the day).
    """
    def stream(text: str) -> io.StringIO:
        return io.StringIO(text)

    entry_url = create_race_entry_page_url(race_date, STADIUM, race_number)
    entry_text = fetch_text(entry_url, delay=delay)
    try:
        entries = extract_race_entries(stream(entry_text))
    except DataNotFound:
        return None

    race_info = extract_race_information(stream(entry_text))
    racers = {r.registration_number: r for r in extract_racers(stream(entry_text))}
    racer_perf = {
        p.racer_registration_number: p
        for p in extract_racer_performances(stream(entry_text))
    }
    boat_perf = {p.number: p for p in extract_boat_performances(stream(entry_text))}
    motor_perf = {p.number: p for p in extract_motor_performances(stream(entry_text))}

    before_url = create_race_before_information_page_url(race_date, STADIUM, race_number)
    before_text = fetch_text(before_url, delay=delay)
    start_exhibition: dict[int, Any] = {}
    lap_exhibition: dict[int, Any] = {}
    boat_settings: dict[int, Any] = {}
    weather_before = None
    try:
        start_exhibition = {
            r.pit_number: r for r in extract_start_exhibition_records(stream(before_text))
        }
        lap_exhibition = {
            r.pit_number: r
            for r in extract_circumference_exhibition_records(stream(before_text))
        }
        boat_settings = {s.pit_number: s for s in extract_boat_settings(stream(before_text))}
        weather_before = extract_before_weather_condition(stream(before_text))
    except (DataNotFound, RaceCanceled):
        pass

    result_url = create_race_result_page_url(race_date, STADIUM, race_number)
    result_text = fetch_text(result_url, delay=delay)
    records: dict[int, Any] = {}
    payoffs: list[Any] = []
    is_canceled = False
    try:
        records = {r.pit_number: r for r in extract_race_records(stream(result_text))}
        payoffs = extract_race_payoffs(stream(result_text))
    except RaceCanceled:
        is_canceled = True
    except DataNotFound:
        pass  # race not finished yet (future / today's later races)

    boats = []
    for entry in entries:
        pit = entry.pit_number
        racer = racers.get(entry.racer_registration_number)
        boats.append(
            {
                "pit_number": pit,
                "racer_registration_number": entry.racer_registration_number,
                "racer_name": f"{racer.last_name}{racer.first_name}" if racer else None,
                "racer_rank": racer.current_rating.name if racer else None,
                "is_absent": entry.is_absent,
                "motor_number": entry.motor_number,
                "boat_number": entry.boat_number,
                "national_win_rate": getattr(racer_perf.get(entry.racer_registration_number), "rate_in_all_stadium", None),
                "local_win_rate": getattr(racer_perf.get(entry.racer_registration_number), "rate_in_event_going_stadium", None),
                "motor_quinella_rate": getattr(motor_perf.get(entry.motor_number), "quinella_rate", None),
                "motor_trio_rate": getattr(motor_perf.get(entry.motor_number), "trio_rate", None),
                "boat_quinella_rate": getattr(boat_perf.get(entry.boat_number), "quinella_rate", None),
                "boat_trio_rate": getattr(boat_perf.get(entry.boat_number), "trio_rate", None),
                "tilt": getattr(boat_settings.get(pit), "tilt", None),
                "exhibition_time": getattr(lap_exhibition.get(pit), "exhibition_time", None),
                "exhibition_start_time": getattr(start_exhibition.get(pit), "start_time", None),
                "exhibition_start_course": getattr(start_exhibition.get(pit), "start_course", None),
                "result_arrival": getattr(records.get(pit), "arrival", None),
                "result_start_time": getattr(records.get(pit), "start_time", None),
                "result_start_course": getattr(records.get(pit), "start_course", None),
                "result_winning_trick": _to_jsonable(getattr(records.get(pit), "winning_trick", None)),
                "result_disqualification": _to_jsonable(getattr(records.get(pit), "disqualification", None)),
            }
        )

    return _to_jsonable(
        {
            "date": race_date,
            "stadium": "HEIWAJIMA",
            "race_number": race_number,
            "title": race_info.title,
            "number_of_laps": race_info.number_of_laps,
            "deadline_at": race_info.deadline_at,
            "is_course_fixed": race_info.is_course_fixed,
            "use_stabilizer": race_info.use_stabilizer,
            "is_canceled": is_canceled,
            "has_result": bool(records),
            "weather": weather_before,
            "boats": boats,
            "trifecta_payoffs": [
                {"betting_numbers": list(p.betting_numbers), "amount": p.amount} for p in payoffs
            ],
        }
    )
