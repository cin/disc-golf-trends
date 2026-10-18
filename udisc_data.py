"""Parse UDisc scorecard CSV exports and compute scoring statistics.

Pure functions over plain data, no MCP or network code, so everything here is testable with fixture CSVs.

Export layout (one row per player per round, preceded by a "Par" pseudo-player row for the same round):
PlayerName,CourseName,LayoutName,StartDate,EndDate,Total,+/-,RoundRating,Hole1..HoleN
Dates look like "2026-10-17 1735-0400".
"""

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean

PAR_PLAYER = "Par"
BLOWUP_OVER_PAR = 2  # a hole this many strokes over par (or worse) counts as a blow-up


@dataclass
class Round:
    player: str
    course: str
    layout: str
    start: datetime
    end: datetime | None
    scores: list[int | None]
    pars: list[int | None]
    rating: int | None = None

    @property
    def round_id(self):
        return self.start.strftime("%Y-%m-%d %H%M")

    @property
    def holes(self):
        return len(self.scores)

    @property
    def played(self):
        """Hole numbers (1-based) that have a score."""
        return [i + 1 for i, s in enumerate(self.scores) if s is not None]

    @property
    def total(self):
        """Sum of the scored holes. The file's Total column is ignored: it can disagree with the hole scores."""
        done = [s for s in self.scores if s is not None]
        return sum(done) if done else None

    @property
    def par(self):
        """Par for the holes that were actually scored; None if par is unknown for any of them."""
        pars = [p for p, s in zip(self.pars, self.scores, strict=False) if s is not None]
        if not pars or any(p is None for p in pars):
            return None
        return sum(pars)

    @property
    def to_par(self):
        par, total = self.par, self.total
        if par is None or total is None:
            return None
        return total - par


def parse_date(raw):
    """Parse "2026-10-17 1735-0400"; returns None for blank or unparseable values."""
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d %H%M%z")
    except (ValueError, AttributeError):
        return None


def _to_int(raw):
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def _to_score(raw):
    """A hole score; the export writes 0 for a hole that was not played, which is treated as no score."""
    value = _to_int(raw)
    return value if value else None


def _hole_columns(fieldnames):
    holes = [c for c in fieldnames if c.startswith("Hole") and c[4:].isdigit()]
    return sorted(holes, key=lambda c: int(c[4:]))


def _trim(values):
    """Drop trailing blanks: the export always has 21 hole columns, but layouts have fewer holes."""
    out = list(values)
    while out and out[-1] is None:
        out.pop()
    return out


def read_csv_rows(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = _hole_columns(reader.fieldnames or [])
        for row in reader:
            yield row, cols


def is_scorecard_export(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        header = next(csv.reader(f), [])
    return "PlayerName" in header and "StartDate" in header


def scorecard_files(csv_dir):
    """The UDisc scorecard exports in csv_dir. Other CSVs (e.g. a TechDisc throw export) are ignored by header."""
    directory = Path(csv_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"UDISC_CSV_DIR is not a folder: {directory}")
    files = [p for p in sorted(directory.glob("*.csv")) if is_scorecard_export(p)]
    if not files:
        raise FileNotFoundError(f"No UDisc scorecard CSVs in {directory}")
    return files


def load_rounds(csv_dir, player=None):
    """Load every *.csv under csv_dir. Returns rounds sorted by start time (oldest first).

    Rounds are de-duplicated on (player, course, layout, start), so overlapping exports are harmless.
    If `player` is given (case-insensitive), only that player's rounds are returned."""
    files = scorecard_files(csv_dir)
    par_rows = {}
    player_rows = {}
    for path in files:
        for row, cols in read_csv_rows(path):
            start = parse_date(row.get("StartDate", ""))
            if start is None:
                continue
            values = [_to_score(row.get(c, "")) for c in cols]
            key = (row["CourseName"], row["LayoutName"], start)
            if row["PlayerName"] == PAR_PLAYER:
                par_rows[key] = values
            elif any(v is not None for v in values):  # skip abandoned rounds with no scores at all
                player_rows[(row["PlayerName"], *key)] = (row, values)
    rounds = []
    for (name, course, layout, start), (row, values) in player_rows.items():
        if player and name.casefold() != player.casefold():
            continue
        pars = par_rows.get((course, layout, start), [])
        holes = max(len(_trim(values)), len(_trim(pars)))
        scores = (values + [None] * holes)[:holes]
        pars = (pars + [None] * holes)[:holes]
        rounds.append(
            Round(
                player=name,
                course=course,
                layout=layout,
                start=start,
                end=parse_date(row.get("EndDate", "")),
                scores=scores,
                pars=pars,
                rating=_to_int(row.get("RoundRating", "")),
            )
        )
    rounds.sort(key=lambda r: (r.start, r.player))
    return rounds


def latest_export_mtime(csv_dir):
    """Newest modification time among the CSVs, as an aware datetime (local zone)."""
    return max(datetime.fromtimestamp(p.stat().st_mtime).astimezone() for p in scorecard_files(csv_dir))


# ---------- queries ----------


def _same(a, b):
    return a.casefold() == b.casefold()


def filter_rounds(rounds, start=None, end=None, course=None, layout=None):
    """start/end are ISO dates (YYYY-MM-DD), inclusive. course/layout match case-insensitively by substring."""
    out = []
    for r in rounds:
        day = r.start.date().isoformat()
        if start and day < start:
            continue
        if end and day > end:
            continue
        if course and course.casefold() not in r.course.casefold():
            continue
        if layout and layout.casefold() not in r.layout.casefold():
            continue
        out.append(r)
    return out


def summarize_round(r):
    return {
        "round_id": r.round_id,
        "date": r.start.date().isoformat(),
        "course": r.course,
        "layout": r.layout,
        "holes": r.holes,
        "total": r.total,
        "par": r.par,
        "to_par": r.to_par,
        "rating": r.rating,
        "holes_scored": len(r.played),
    }


def round_detail(r):
    out = summarize_round(r)
    out["player"] = r.player
    out["start"] = r.start.isoformat()
    out["end"] = r.end.isoformat() if r.end else None
    out["holes_detail"] = [
        {"hole": i + 1, "par": p, "score": s, "to_par": (s - p) if s is not None and p is not None else None}
        for i, (p, s) in enumerate(zip(r.pars, r.scores, strict=True))
    ]
    return out


def find_round(rounds, round_id):
    """Match a round_id ("2026-10-17 1735") or a bare date ("2026-10-17").

    Returns (round, []) on a match, or (None, candidate_ids) when a date matches several rounds."""
    exact = [r for r in rounds if r.round_id == round_id]
    if exact:
        return exact[0], []
    by_day = [r for r in rounds if r.start.date().isoformat() == round_id]
    if len(by_day) == 1:
        return by_day[0], []
    return None, [r.round_id for r in by_day]


def list_courses(rounds):
    groups = defaultdict(list)
    for r in rounds:
        groups[r.course].append(r)
    out = []
    for course, rs in groups.items():
        layouts = sorted({r.layout for r in rs})
        out.append(
            {
                "course": course,
                "rounds": len(rs),
                "layouts": layouts,
                "first_played": rs[0].start.date().isoformat(),
                "last_played": rs[-1].start.date().isoformat(),
            }
        )
    out.sort(key=lambda c: (-c["rounds"], c["course"]))
    return out


def _round_stats(rs):
    scored = [r for r in rs if r.to_par is not None]
    full = [r for r in scored if len(r.played) == r.holes]  # best/worst only make sense for complete rounds
    best = min(full, key=lambda r: r.to_par, default=None)
    worst = max(full, key=lambda r: r.to_par, default=None)
    ratings = [r.rating for r in rs if r.rating is not None]
    return {
        "rounds": len(rs),
        "avg_total": round(mean(r.total for r in full), 2) if full else None,
        "avg_to_par": round(mean(r.to_par for r in full), 2) if full else None,
        "best": summarize_round(best) if best else None,
        "worst": summarize_round(worst) if worst else None,
        "avg_rating": round(mean(ratings)) if ratings else None,
    }


def hole_stats(rounds, min_rounds=1):
    """Per (course, layout, hole) averages. Holes are only comparable within one layout."""
    cells = defaultdict(list)
    for r in rounds:
        for i, (p, s) in enumerate(zip(r.pars, r.scores, strict=True)):
            if s is not None and p is not None:
                cells[(r.course, r.layout, i + 1)].append((p, s))
    out = []
    for (course, layout, hole), vals in cells.items():
        if len(vals) < min_rounds:
            continue
        over = [s - p for p, s in vals]
        out.append(
            {
                "course": course,
                "layout": layout,
                "hole": hole,
                "par": vals[-1][0],
                "rounds": len(vals),
                "avg_score": round(mean(s for _, s in vals), 2),
                "avg_to_par": round(mean(over), 2),
                "total_strokes_over_par": sum(over),
                "best": min(s for _, s in vals),
                "worst": max(s for _, s in vals),
                "blowups": sum(1 for o in over if o >= BLOWUP_OVER_PAR),
            }
        )
    return out


def course_stats(rounds, course, layout=None, include_holes=False):
    """Round stats for a course. The full per-hole list is large, so it is only added on request."""
    rs = filter_rounds(rounds, course=course, layout=layout)
    if not rs:
        return None
    holes = sorted(hole_stats(rs), key=lambda h: (h["course"], h["layout"], h["hole"]))
    out = {"course": course, **_round_stats(rs)}
    by_layout = defaultdict(list)
    for r in rs:
        by_layout[(r.course, r.layout)].append(r)
    out["layouts"] = [
        {"course": c, "layout": lay, **_round_stats(lrs)} for (c, lay), lrs in sorted(by_layout.items())
    ]
    scored = [h for h in holes if h["rounds"] >= 2]
    out["best_holes"] = sorted(scored, key=lambda h: h["avg_to_par"])[:3]
    out["worst_holes"] = sorted(scored, key=lambda h: -h["avg_to_par"])[:3]
    if include_holes:
        out["holes"] = holes
    return out


def _bucket(r, group_by):
    if group_by == "season":
        return str(r.start.year)
    if group_by == "month":
        return r.start.strftime("%Y-%m")
    raise ValueError("group_by must be 'month' or 'season'")


def scoring_trends(rounds, course=None, layout=None, group_by="month"):
    """Average score vs par per period. Only complete rounds with known par are averaged."""
    rs = [r for r in filter_rounds(rounds, course=course, layout=layout) if r.to_par is not None]
    rs = [r for r in rs if len(r.played) == r.holes]
    buckets = defaultdict(list)
    for r in rs:
        buckets[_bucket(r, group_by)].append(r)
    out = []
    for period in sorted(buckets):
        brs = buckets[period]
        ratings = [r.rating for r in brs if r.rating is not None]
        best = min(brs, key=lambda r: r.to_par)  # earliest round wins a tie
        out.append(
            {
                "period": period,
                "rounds": len(brs),
                "avg_to_par": round(mean(r.to_par for r in brs), 2),
                "best_to_par": best.to_par,
                "best_round": {
                    "round_id": best.round_id,
                    "date": best.start.date().isoformat(),
                    "course": best.course,
                    "layout": best.layout,
                },
                "avg_rating": round(mean(ratings)) if ratings else None,
            }
        )
    return out


SCORE_KINDS = ("eagle_or_better", "birdie", "par", "bogey", "double", "triple_or_worse")


def _score_kind(over):
    if over <= -2:
        return "eagle_or_better"
    if over >= 3:
        return "triple_or_worse"
    return SCORE_KINDS[over + 2]


def scoring_distribution(rounds, course=None, layout=None, start=None, end=None, group_by=None):
    """How holes were scored relative to par, as counts and percentages of holes played.

    Counts every scored hole with a known par, including holes from partial rounds. group_by is None (one row),
    'month' or 'season'.
    """
    buckets = defaultdict(lambda: dict.fromkeys(SCORE_KINDS, 0))
    for r in filter_rounds(rounds, start=start, end=end, course=course, layout=layout):
        period = "all" if group_by is None else _bucket(r, group_by)
        for p, s in zip(r.pars, r.scores, strict=True):
            if s is not None and p is not None:
                buckets[period][_score_kind(s - p)] += 1
    out = []
    for period in sorted(buckets):
        counts = buckets[period]
        holes = sum(counts.values())
        out.append(
            {
                "period": period,
                "holes": holes,
                "counts": counts,
                "percent": {k: round(100 * v / holes, 1) for k, v in counts.items()},
            }
        )
    return out


def hole_problem_report(rounds, course=None, layout=None, top_n=10, min_rounds=3):
    """Holes ranked by total strokes lost to par (not per-round average), so frequently played holes count."""
    rs = filter_rounds(rounds, course=course, layout=layout)
    stats = hole_stats(rs, min_rounds=min_rounds)
    stats.sort(key=lambda h: (-h["total_strokes_over_par"], -h["avg_to_par"]))
    return stats[:top_n]


def compare_seasons(rounds, year_a, year_b, course=None):
    def season(year):
        rs = [r for r in filter_rounds(rounds, course=course) if r.start.year == year]
        return {"year": year, **_round_stats(rs)}

    a, b = season(year_a), season(year_b)
    delta = None
    if a["avg_to_par"] is not None and b["avg_to_par"] is not None:
        delta = round(b["avg_to_par"] - a["avg_to_par"], 2)
    return {"a": a, "b": b, "avg_to_par_change": delta}
