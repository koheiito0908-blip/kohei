#!/usr/bin/env python3
"""Aggregate collected Heiwajima race results into per-course (pit number)
statistics: win rate, quinella (2連対率) / trio (3連対率) rate, average start
timing and winning-trick tendencies. 平和島 has its own course/tide character
that differs from national averages, so these are computed from our own
scraped history rather than reused from the official per-racer stats.

Output: docs/data/stats/course_stats.json
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RACES_DIR = REPO_ROOT / "docs" / "data" / "races"
OUT_PATH = REPO_ROOT / "docs" / "data" / "stats" / "course_stats.json"


def main() -> None:
    race_files = sorted(RACES_DIR.glob("*.json"))
    if not race_files:
        raise SystemExit(f"no race data found in {RACES_DIR}; run collect_data.py first")

    pit_races = Counter()
    pit_win = Counter()
    pit_top2 = Counter()
    pit_top3 = Counter()
    pit_start_time_sum = defaultdict(float)
    pit_start_time_n = Counter()
    pit_winning_trick = defaultdict(Counter)
    dates_seen: list[str] = []

    for path in race_files:
        day = json.loads(path.read_text())
        if day["status"] not in ("final", "partial"):
            continue
        dates_seen.append(day["date"])
        for race in day["races"]:
            if race["is_canceled"] or not race["has_result"]:
                continue
            for boat in race["boats"]:
                pit = boat["pit_number"]
                arrival = boat["result_arrival"]
                if arrival is None:
                    continue
                pit_races[pit] += 1
                if arrival == 1:
                    pit_win[pit] += 1
                    if boat["result_winning_trick"]:
                        pit_winning_trick[pit][boat["result_winning_trick"]] += 1
                if arrival <= 2:
                    pit_top2[pit] += 1
                if arrival <= 3:
                    pit_top3[pit] += 1
                st = boat["result_start_time"]
                if st is not None:
                    pit_start_time_sum[pit] += st
                    pit_start_time_n[pit] += 1

    by_pit = {}
    for pit in range(1, 7):
        n = pit_races[pit]
        by_pit[str(pit)] = {
            "sample_races": n,
            "win_rate": round(pit_win[pit] / n, 4) if n else None,
            "quinella_rate": round(pit_top2[pit] / n, 4) if n else None,
            "trio_rate": round(pit_top3[pit] / n, 4) if n else None,
            "avg_start_time": (
                round(pit_start_time_sum[pit] / pit_start_time_n[pit], 3)
                if pit_start_time_n[pit]
                else None
            ),
            "winning_trick_share": (
                {k: round(v / pit_win[pit], 3) for k, v in pit_winning_trick[pit].items()}
                if pit_win[pit]
                else {}
            ),
        }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "stadium": "HEIWAJIMA",
                "date_range": {"from": min(dates_seen), "to": max(dates_seen)} if dates_seen else None,
                "total_races_analyzed": sum(pit_races.values()) // 6 if pit_races else 0,
                "by_pit": by_pit,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
