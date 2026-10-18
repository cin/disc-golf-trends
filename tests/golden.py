"""Golden results that pin the TypeScript port (site/) to this Python implementation.

`python tests/golden.py` rewrites the synthetic CSVs in tests/fixtures/ and site/tests/golden.json. The site's
vitest suite loads the same CSVs and must reproduce every value here; tests/test_golden.py fails if the committed
files are out of date, so a change to the Python statistics cannot silently leave the port behind.

All data is made up. Throw times sit around midday UTC and the local-time `when` field is left out, so the results
do not depend on the machine's time zone.
"""

import json
import random
import shutil
import sys
import tempfile
from pathlib import Path

import dashboard
import techdisc_data as td
import udisc_data as ud

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN = ROOT / "site" / "tests" / "golden.json"
SYNTHETIC_SCORECARDS = FIXTURES / "synthetic_scorecards.csv"
SYNTHETIC_THROWS = FIXTURES / "synthetic_throws.csv"

HEADER = "PlayerName,CourseName,LayoutName,StartDate,EndDate,Total,+/-,RoundRating," + ",".join(
    f"Hole{i}" for i in range(1, 22)
)
THROW_HEADER = (
    "id,time,timeSeconds,speedMph,speedKmh,advanceRatio,spinRpm,launchAngle,noseAngle,hyzerAngle,wobbleAngle,"
    "distanceFeet,distanceMeters,throwType,primaryThrowType,tags,notes"
)
PLAYERS = ["Alex", "Sam", "Jo Ñandú", "O'Brien, Pat"]
LAYOUTS = [
    ("Pine Hollow", "Main", 9),
    ("Oak Ridge", "Short", 6),
    ("Big Lake", "Blue, Long", 18),
    ("Straße Park", "Main", 12),
]
OFFSETS = ["-0400", "-0500", "+0100", "+0530"]


def q(value):
    """CSV-quote a field the way the UDisc export does when it needs it."""
    return f'"{value.replace(chr(34), chr(34) * 2)}"' if any(c in value for c in ',"\n') else value


def synthetic_scorecards():
    rng = random.Random(20261018)
    pars = {(c, lay): [rng.choice([3, 3, 3, 4, 4, 5]) for _ in range(n)] for c, lay, n in LAYOUTS}
    lines = [HEADER]
    for k in range(140):
        course, layout, n = LAYOUTS[rng.choice([0, 0, 0, 1, 1, 2, 3])]
        year, month, day = rng.choice([2024, 2025, 2026]), rng.randint(1, 12), rng.randint(1, 28)
        hour, minute, off = rng.randint(7, 19), rng.choice([0, 15, 30, 45]), rng.choice(OFFSETS)
        start = f"{year}-{month:02d}-{day:02d} {hour:02d}{minute:02d}{off}"
        end = f"{year}-{month:02d}-{day:02d} {hour + 1:02d}{minute:02d}{off}"
        par = pars[(course, layout)]

        def cells(values):
            return ",".join(str(v) if v is not None else "" for v in (values + [None] * 21)[:21])

        if k % 17 != 5:  # a few rounds have no Par row, so their par is unknown
            lines.append(f"Par,{q(course)},{q(layout)},{start},{end},{sum(par)},,,{cells(par)}")
        for player in rng.sample(PLAYERS, rng.randint(1, 3)):
            scores = [max(1, p + rng.choice([-2, -1, -1, 0, 0, 0, 1, 1, 2, 3, 4])) for p in par]
            if rng.random() < 0.15:  # quit early: the rest are unplayed zeros
                cut = rng.randint(1, n - 1)
                scores = scores[:cut] + [0] * (n - cut)
            if rng.random() < 0.04:
                scores = [0] * n
            rating = "" if rng.random() < 0.3 else str(rng.randint(600, 1000))
            lines.append(f"{q(player)},{q(course)},{q(layout)},{start},{end},99,0,{rating},{cells(scores)}")
        if k % 23 == 0:  # an overlapping export repeats the same round
            lines.append(lines[-1])
    return "\n".join(lines) + "\n"


def synthetic_throws():
    rng = random.Random(20261019)
    lines = [THROW_HEADER]
    base = 1_760_000_000  # 2025-10-09, around midday UTC after adding the offsets below
    for k in range(300):
        seconds = base - base % 86400 + 43200 + rng.randint(0, 200) * 86400 + rng.randint(-7200, 7200)
        style = rng.choice(
            [("Hyzer", "Backhand"), ("Flat", "Backhand"), ("Flat", "Forehand"), ("Anhyzer", "Forehand"), ("", "")]
        )

        def num(lo, hi, places=2):
            return "" if rng.random() < 0.05 else f"{rng.uniform(lo, hi):.{places}f}"

        speed = num(30, 55)
        tags = rng.choice(["", "warmup", "wind, left", '"quoted" tag'])
        notes = rng.choice(["", "felt good", "line one\nline two"])
        row = [
            str(1_000_000 + k),
            '"1/1/2026, 12:00:00 PM UTC"',
            f"{seconds}.0",
            speed,
            "",
            num(20, 35),
            num(500, 1000, 1),
            num(0, 15),
            num(-3, 3),
            num(-10, 10),
            num(2, 9),
            num(120, 330),
            "",
            style[0],
            style[1],
            q(tags),
            q(notes),
        ]
        lines.append(",".join(row))
        if k % 40 == 0:
            lines.append(lines[-1])
    return "\n".join(lines) + "\n"


def _folder(*paths):
    tmp = Path(tempfile.mkdtemp())
    for p in paths:
        shutil.copy(p, tmp / p.name)
    return tmp


def _calls(dataset, rounds, throws):
    """Every query the site ports, over one dataset."""
    out = {"players": sorted({r.player for r in rounds})}
    out["rounds"] = [ud.round_detail(r) for r in rounds]
    out["list_courses"] = ud.list_courses(rounds)
    out["hole_stats"] = ud.hole_stats(rounds)
    out["hole_stats_min3"] = ud.hole_stats(rounds, min_rounds=3)
    out["course_stats"] = {
        c["course"]: ud.course_stats(rounds, c["course"], include_holes=True) for c in out["list_courses"]
    }
    out["course_stats_layout"] = ud.course_stats(rounds, "big", layout="blue")
    out["course_stats_none"] = ud.course_stats(rounds, "Nowhere")
    out["filter"] = {
        "since": [ud.summarize_round(r) for r in ud.filter_rounds(rounds, start="2025-06-01")],
        "window": [
            ud.summarize_round(r) for r in ud.filter_rounds(rounds, start="2025-01-01", end="2025-12-31", course="oak")
        ],
        "layout": [ud.summarize_round(r) for r in ud.filter_rounds(rounds, layout="main")],
        "casefold": [ud.summarize_round(r) for r in ud.filter_rounds(rounds, course="STRASSE")],
    }
    out["trends"] = {
        f"{g}:{c}": ud.scoring_trends(rounds, course=c, group_by=g)
        for g in ("month", "season")
        for c in (None, "Pine Hollow")
    }
    out["distribution"] = {
        "all": ud.scoring_distribution(rounds),
        "season": ud.scoring_distribution(rounds, group_by="season"),
        "month_course": ud.scoring_distribution(
            rounds, course="Pine", group_by="month", start="2025-03-01", end="2026-02-28"
        ),
        "none": ud.scoring_distribution(rounds, course="Nowhere"),
    }
    out["problems"] = {
        "default": ud.hole_problem_report(rounds),
        "min1_top5": ud.hole_problem_report(rounds, top_n=5, min_rounds=1),
        "course": ud.hole_problem_report(rounds, course="Big Lake", min_rounds=2),
    }
    out["compare"] = {
        "plain": ud.compare_seasons(rounds, 2024, 2025),
        "course": ud.compare_seasons(rounds, 2025, 2026, course="Pine"),
        "missing": ud.compare_seasons(rounds, 2025, 1999),
    }
    middle = rounds[len(rounds) // 2]
    days = [r.start.date().isoformat() for r in rounds]
    shared = next((d for d in days if days.count(d) > 1), None)  # a date with several rounds, if any
    out["find_round"] = {
        "exact": ud.find_round(rounds, middle.round_id)[0].round_id,
        "by_day": [r and r.round_id for r in [ud.find_round(rounds, middle.start.date().isoformat())[0]]],
        "shared_day": list(ud.find_round(rounds, shared)[1]) if shared else None,
        "missing": ud.find_round(rounds, "1999-01-01")[1],
    }
    out["payload"] = dashboard.build_payload(rounds, throws, rounds[0].player if rounds else "")
    out["throws"] = _throw_calls(throws)
    return out


def _throw_calls(throws):
    def summary(ts):
        return [{k: v for k, v in td.summarize_throw(t).items() if k != "when"} for t in ts]

    return {
        "all": summary(throws),
        "filter": {
            "backhand": summary(td.filter_throws(throws, primary_type="backhand")),
            "flat_since": summary(td.filter_throws(throws, throw_type="FLAT", start="2026-01-01")),
            "window": summary(td.filter_throws(throws, start="2025-12-01", end="2026-02-28")),
        },
        "stats": td.throw_stats(throws),
        "stats_window": td.throw_stats(throws, start="2026-01-01", end="2026-03-31"),
        "stats_empty": td.throw_stats(throws, start="2099-01-01"),
        "trends": {
            "month": td.throw_trends(throws, group_by="month"),
            "season": td.throw_trends(throws, group_by="season"),
            "backhand": td.throw_trends(throws, primary_type="Backhand", throw_type="Hyzer"),
        },
    }


def build():
    """The golden results, as plain JSON data."""
    scorecards = {
        "sample": (FIXTURES / "sample.csv", FIXTURES / "throws.csv", "Alex"),
        "synthetic": (SYNTHETIC_SCORECARDS, SYNTHETIC_THROWS, "Alex"),
    }
    out = {}
    for name, (cards, throw_file, player) in scorecards.items():
        folder = _folder(cards, throw_file)
        everyone = ud.load_rounds(folder)
        throws = td.load_throws(folder)
        entry = _calls(name, ud.load_rounds(folder, player=player), throws)
        entry["everyone"] = [ud.summarize_round(r) | {"player": r.player} for r in everyone]
        out[name] = entry
        shutil.rmtree(folder)
    return json.loads(json.dumps(out))


def main():
    SYNTHETIC_SCORECARDS.write_text(synthetic_scorecards(), encoding="utf-8", newline="\n")
    SYNTHETIC_THROWS.write_text(synthetic_throws(), encoding="utf-8", newline="\n")
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(
        json.dumps(build(), separators=(",", ":"), ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {SYNTHETIC_SCORECARDS.name}, {SYNTHETIC_THROWS.name} and {GOLDEN.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
