#!/usr/bin/env python3
"""Collect Heiwajima (平和島) race data from the BOAT RACE official site.

Usage:
    python scripts/collect_data.py --start 2025-07-25 --end 2026-07-25
    python scripts/collect_data.py --date 2026-07-25   # single day

Writes one JSON file per date to docs/data/races/YYYY-MM-DD.json. A day
already saved with status "final" (all races finished, date in the past) is
skipped on re-runs, so backfills are resumable / safe to re-trigger.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib.heiwajima import fetch_race  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / "data" / "races"


def collect_day(day: date, *, delay: float) -> dict:
    races = []
    for race_number in range(1, 13):
        race = fetch_race(day, race_number, delay=delay)
        if race is None:
            break
        races.append(race)

    all_final = bool(races) and all(r["has_result"] or r["is_canceled"] for r in races)
    status = "final" if (all_final and day < date.today()) else (
        "no_racing" if not races else "partial"
    )
    return {
        "date": day.isoformat(),
        "stadium": "HEIWAJIMA",
        "status": status,
        "collected_at": datetime.utcnow().isoformat() + "Z",
        "races": races,
    }


def already_final(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    return data.get("status") in ("final", "no_racing")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="single date, YYYY-MM-DD")
    parser.add_argument("--start", help="range start date, YYYY-MM-DD")
    parser.add_argument("--end", help="range end date, YYYY-MM-DD (default: today)")
    parser.add_argument("--delay", type=float, default=0.4, help="seconds between HTTP requests")
    parser.add_argument("--force", action="store_true", help="re-fetch even already-final days")
    args = parser.parse_args()

    if args.date:
        start = end = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        end = (
            datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else date.today()
        )
        start = (
            datetime.strptime(args.start, "%Y-%m-%d").date()
            if args.start
            else end - timedelta(days=365)
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    day = start
    while day <= end:
        out_path = OUT_DIR / f"{day.isoformat()}.json"
        if not args.force and already_final(out_path):
            print(f"skip {day} (already final)")
            day += timedelta(days=1)
            continue

        print(f"collecting {day} ...", flush=True)
        result = collect_day(day, delay=args.delay)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"  -> {result['status']}, {len(result['races'])} races")
        day += timedelta(days=1)


if __name__ == "__main__":
    main()
