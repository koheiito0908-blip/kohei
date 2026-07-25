#!/usr/bin/env python3
"""Score and rank Heiwajima races for a given day (default: today, JST) using
a simple weighted, statistics-based model — no machine learning:

  - course (pit number) advantage  : our own 1-year Heiwajima course_stats.json
  - racer local (当地) win rate     : published on the official racelist page
  - racer national (全国) win rate  : published on the official racelist page
  - motor 2-連対率 (quinella rate)  : published on the official racelist page
  - boat 2-連対率 (quinella rate)   : published on the official racelist page
  - exhibition lap time / start ST : published shortly before the race, used
                                      opportunistically when already available

Each metric is min-max normalised across the 6 boats *within a race* (only
relative ranking matters), then combined with fixed weights. Weights for
metrics missing in a given race (e.g. no exhibition data yet) are dropped and
the rest re-normalised to sum to 1, so predictions still work early in the
day and simply sharpen as more official data becomes available.

For races that haven't run yet, per-boat scores are also converted into a
3連単 (trifecta) win-probability distribution via a Plackett-Luce model, and
combined with the live official odds to rank combinations by *expected
value* (probability x payout), not just predicted finishing order — see
`value_bets` in the output. Odds are only published shortly before a race,
so this list is empty until then.

Output: docs/data/predictions/YYYY-MM-DD.json and predictions/latest.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collect_data import OUT_DIR as RACES_DIR  # noqa: E402
from collect_data import collect_day  # noqa: E402
from lib.heiwajima import fetch_trifecta_odds  # noqa: E402

# Plackett-Luce "sharpness": how strongly score differences translate into
# win-probability differences. Purely a modelling choice, not fitted to data.
STRENGTH_TEMPERATURE = 5.0
VALUE_BETS_TOP_N = 5

REPO_ROOT = Path(__file__).resolve().parent.parent
STATS_PATH = REPO_ROOT / "docs" / "data" / "stats" / "course_stats.json"
PRED_DIR = REPO_ROOT / "docs" / "data" / "predictions"

# metric name -> (weight, higher_is_better)
WEIGHTS = {
    "course_advantage": (0.30, True),
    "local_win_rate": (0.20, True),
    "national_win_rate": (0.15, True),
    "motor_quinella_rate": (0.20, True),
    "boat_quinella_rate": (0.05, True),
    "exhibition_time": (0.05, False),
    "exhibition_start_time": (0.05, False),
}

JST = timezone(timedelta(hours=9))


def load_course_stats() -> dict:
    if not STATS_PATH.exists():
        return {}
    return json.loads(STATS_PATH.read_text()).get("by_pit", {})


def normalize(values: dict[int, float], higher_is_better: bool) -> dict[int, float]:
    present = {k: v for k, v in values.items() if v is not None}
    if len(present) < 2:
        return {k: 0.5 for k in present}
    lo, hi = min(present.values()), max(present.values())
    if hi == lo:
        return {k: 0.5 for k in present}
    out = {}
    for k, v in present.items():
        n = (v - lo) / (hi - lo)
        out[k] = n if higher_is_better else 1 - n
    return out


def score_race(race: dict, course_stats: dict) -> dict:
    boats = [b for b in race["boats"] if not b["is_absent"]]
    if not boats:
        return race | {"predictions": []}

    raw: dict[str, dict[int, float]] = {
        "course_advantage": {
            b["pit_number"]: course_stats.get(str(b["pit_number"]), {}).get("win_rate")
            for b in boats
        },
        "local_win_rate": {b["pit_number"]: b["local_win_rate"] for b in boats},
        "national_win_rate": {b["pit_number"]: b["national_win_rate"] for b in boats},
        "motor_quinella_rate": {b["pit_number"]: b["motor_quinella_rate"] for b in boats},
        "boat_quinella_rate": {b["pit_number"]: b["boat_quinella_rate"] for b in boats},
        "exhibition_time": {b["pit_number"]: b["exhibition_time"] for b in boats},
        "exhibition_start_time": {b["pit_number"]: b["exhibition_start_time"] for b in boats},
    }

    normed = {name: normalize(vals, WEIGHTS[name][1]) for name, vals in raw.items()}
    used_weight = sum(
        WEIGHTS[name][0] for name, vals in normed.items() if vals
    ) or 1.0

    scores: dict[int, float] = {}
    for b in boats:
        pit = b["pit_number"]
        total = 0.0
        for name, vals in normed.items():
            if pit in vals:
                total += (WEIGHTS[name][0] / used_weight) * vals[pit]
        scores[pit] = round(total, 4)

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    rank_by_pit = {pit: i + 1 for i, (pit, _) in enumerate(ranked)}

    gap = (ranked[0][1] - ranked[1][1]) if len(ranked) >= 2 else 0
    confidence = "高" if gap >= 0.15 else "中" if gap >= 0.07 else "低"

    predictions = []
    for b in race["boats"]:
        pit = b["pit_number"]
        predictions.append(
            {
                "pit_number": pit,
                "racer_name": b["racer_name"],
                "racer_rank": b["racer_rank"],
                "motor_number": b["motor_number"],
                "is_absent": b["is_absent"],
                "score": scores.get(pit),
                "predicted_rank": rank_by_pit.get(pit),
            }
        )
    predictions.sort(key=lambda p: (p["predicted_rank"] is None, p["predicted_rank"]))

    return {
        "race_number": race["race_number"],
        "title": race["title"],
        "deadline_at": race["deadline_at"],
        "is_canceled": race["is_canceled"],
        "has_result": race["has_result"],
        "confidence": confidence if not race["is_canceled"] else None,
        "predictions": predictions,
    }


def trifecta_probabilities(scores: dict[int, float]) -> dict[tuple[int, int, int], float]:
    """Plackett-Luce model: convert per-boat strength scores into a
    probability for every ordered (1st, 2nd, 3rd) finish among the boats."""
    if len(scores) < 3:
        return {}
    strength = {pit: math.exp(STRENGTH_TEMPERATURE * s) for pit, s in scores.items()}
    total = sum(strength.values())

    probs = {}
    for i, j, k in itertools.permutations(scores.keys(), 3):
        remaining_after_i = total - strength[i]
        remaining_after_ij = remaining_after_i - strength[j]
        if remaining_after_i <= 0 or remaining_after_ij <= 0:
            continue
        probs[(i, j, k)] = (
            (strength[i] / total)
            * (strength[j] / remaining_after_i)
            * (strength[k] / remaining_after_ij)
        )
    return probs


def compute_value_bets(
    scores: dict[int, float], odds: dict[tuple[int, int, int], float] | None
) -> list[dict]:
    """Rank 3連単 combinations by expected value (win probability x payout),
    not just by predicted finishing order. EV > 1 means the model thinks the
    combo is under-priced relative to its estimated win probability; most
    combos will still be < 1 since the track keeps ~25% of the pool."""
    if not odds:
        return []
    probs = trifecta_probabilities(scores)
    bets = []
    for combo, prob in probs.items():
        ratio = odds.get(combo)
        if ratio is None:
            continue
        bets.append(
            {
                "combo": list(combo),
                "probability": round(prob, 4),
                "odds": ratio,
                "expected_value": round(prob * ratio, 3),
            }
        )
    bets.sort(key=lambda b: b["expected_value"], reverse=True)
    return bets[:VALUE_BETS_TOP_N]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="YYYY-MM-DD, default: today in JST")
    parser.add_argument("--delay", type=float, default=0.4)
    parser.add_argument("--refresh", action="store_true", help="re-fetch race data even if cached")
    args = parser.parse_args()

    target = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date
        else datetime.now(JST).date()
    )

    races_path = RACES_DIR / f"{target.isoformat()}.json"
    if args.refresh or not races_path.exists():
        day_data = collect_day(target, delay=args.delay)
        RACES_DIR.mkdir(parents=True, exist_ok=True)
        races_path.write_text(json.dumps(day_data, ensure_ascii=False, indent=2))
    else:
        day_data = json.loads(races_path.read_text())

    course_stats = load_course_stats()
    scored_races = []
    for r in day_data["races"]:
        scored = score_race(r, course_stats)
        scored["value_bets"] = []
        if not scored["is_canceled"] and not scored["has_result"]:
            scores = {
                p["pit_number"]: p["score"]
                for p in scored["predictions"]
                if not p["is_absent"] and p["score"] is not None
            }
            odds = fetch_trifecta_odds(target, scored["race_number"], delay=args.delay)
            scored["value_bets"] = compute_value_bets(scores, odds)
        scored_races.append(scored)

    output = {
        "date": target.isoformat(),
        "stadium": "HEIWAJIMA",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": day_data["status"],
        "races": scored_races,
    }

    PRED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PRED_DIR / f"{target.isoformat()}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    (PRED_DIR / "latest.json").write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"wrote {out_path} ({len(scored_races)} races, status={day_data['status']})")


if __name__ == "__main__":
    main()
