"""Parse TechDisc throw exports and compute throw statistics.

Pure functions over plain data, no MCP or network code, so everything here is testable with fixture CSVs.

Export layout (one row per throw):
id,time,timeSeconds,speedMph,speedKmh,advanceRatio,spinRpm,launchAngle,noseAngle,hyzerAngle,wobbleAngle,
distanceFeet,distanceMeters,throwType,primaryThrowType,tags,notes
The `time` column is display text ("6/6/2026, 11:53:57 AM EDT"); `timeSeconds` (epoch) is used instead and shown in
the computer's local time zone.

The folder may also hold UDisc scorecard exports. Files are told apart by header, so each loader ignores the other's.
"""

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean

MARKER_COLUMN = "speedMph"  # present in throw exports, absent from UDisc scorecards


@dataclass
class Throw:
    throw_id: str
    when: datetime
    speed_mph: float | None
    spin_rpm: float | None
    advance_ratio: float | None
    launch_angle: float | None
    nose_angle: float | None
    hyzer_angle: float | None
    wobble_angle: float | None
    distance_ft: float | None
    throw_type: str
    primary_type: str
    tags: str
    notes: str


def _to_float(raw):
    try:
        return float(str(raw).strip())
    except ValueError:
        return None


def is_throw_export(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        header = next(csv.reader(f), [])
    return MARKER_COLUMN in header


def throw_files(csv_dir):
    directory = Path(csv_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"TECHDISC_CSV_DIR is not a folder: {directory}")
    files = [p for p in sorted(directory.glob("*.csv")) if is_throw_export(p)]
    if not files:
        raise FileNotFoundError(f"No TechDisc throw exports (CSV with a {MARKER_COLUMN} column) in {directory}")
    return files


def load_throws(csv_dir):
    """Load every TechDisc export under csv_dir, oldest first. Throws are de-duplicated on their id."""
    found = {}
    for path in throw_files(csv_dir):
        with path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                seconds = _to_float(row.get("timeSeconds", ""))
                if seconds is None or not row.get("id"):
                    continue
                found[row["id"]] = Throw(
                    throw_id=row["id"],
                    when=datetime.fromtimestamp(seconds).astimezone(),
                    speed_mph=_to_float(row.get("speedMph", "")),
                    spin_rpm=_to_float(row.get("spinRpm", "")),
                    advance_ratio=_to_float(row.get("advanceRatio", "")),
                    launch_angle=_to_float(row.get("launchAngle", "")),
                    nose_angle=_to_float(row.get("noseAngle", "")),
                    hyzer_angle=_to_float(row.get("hyzerAngle", "")),
                    wobble_angle=_to_float(row.get("wobbleAngle", "")),
                    distance_ft=_to_float(row.get("distanceFeet", "")),
                    throw_type=row.get("throwType", "").strip(),
                    primary_type=row.get("primaryThrowType", "").strip(),
                    tags=row.get("tags", "").strip(),
                    notes=row.get("notes", "").strip(),
                )
    return sorted(found.values(), key=lambda t: (t.when, t.throw_id))


def latest_export_mtime(csv_dir):
    """Newest modification time among the throw exports, as an aware datetime (local zone)."""
    return max(datetime.fromtimestamp(p.stat().st_mtime).astimezone() for p in throw_files(csv_dir))


# ---------- queries ----------


def _r(x, places=2):
    return None if x is None else round(x, places)


def _avg(values):
    vals = [v for v in values if v is not None]
    return round(mean(vals), 2) if vals else None


def _extreme(values, fn):
    vals = [v for v in values if v is not None]
    return fn(vals) if vals else None


def filter_throws(throws, start=None, end=None, primary_type=None, throw_type=None):
    """start/end are ISO dates (YYYY-MM-DD), inclusive. Types match case-insensitively (exact)."""
    out = []
    for t in throws:
        day = t.when.date().isoformat()
        if start and day < start:
            continue
        if end and day > end:
            continue
        if primary_type and t.primary_type.casefold() != primary_type.casefold():
            continue
        if throw_type and t.throw_type.casefold() != throw_type.casefold():
            continue
        out.append(t)
    return out


def summarize_throw(t):
    return {
        "throw_id": t.throw_id,
        "when": t.when.isoformat(timespec="seconds"),
        "primary_type": t.primary_type,
        "throw_type": t.throw_type,
        "speed_mph": t.speed_mph,
        "distance_ft": t.distance_ft,
        "spin_rpm": t.spin_rpm,
        "launch_angle": t.launch_angle,
        "hyzer_angle": t.hyzer_angle,
        "nose_angle": t.nose_angle,
        "wobble_angle": t.wobble_angle,
        "advance_ratio": t.advance_ratio,
        "tags": t.tags,
        "notes": t.notes,
    }


def _stats(ts):
    return {
        "throws": len(ts),
        "avg_speed_mph": _avg(t.speed_mph for t in ts),
        "max_speed_mph": _extreme((t.speed_mph for t in ts), max),
        "avg_distance_ft": _avg(t.distance_ft for t in ts),
        "max_distance_ft": _extreme((t.distance_ft for t in ts), max),
        "avg_spin_rpm": _avg(t.spin_rpm for t in ts),
        "avg_launch_angle": _avg(t.launch_angle for t in ts),
        "avg_hyzer_angle": _avg(t.hyzer_angle for t in ts),
        "avg_wobble_angle": _avg(t.wobble_angle for t in ts),
        "avg_advance_ratio": _avg(t.advance_ratio for t in ts),
    }


def throw_stats(throws, start=None, end=None):
    """Overall stats plus a breakdown by (primary_type, throw_type), most-thrown first."""
    ts = filter_throws(throws, start=start, end=end)
    groups = defaultdict(list)
    for t in ts:
        groups[(t.primary_type, t.throw_type)].append(t)
    by_style = [
        {"primary_type": primary, "throw_type": kind, **_stats(group)} for (primary, kind), group in groups.items()
    ]
    by_style.sort(key=lambda g: (-g["throws"], g["primary_type"], g["throw_type"]))
    return {
        "first_throw": ts[0].when.date().isoformat() if ts else None,
        "last_throw": ts[-1].when.date().isoformat() if ts else None,
        "overall": _stats(ts),
        "by_style": by_style,
    }


def _bucket(t, group_by):
    if group_by == "season":
        return str(t.when.year)
    if group_by == "month":
        return t.when.strftime("%Y-%m")
    raise ValueError("group_by must be 'month' or 'season'")


def throw_trends(throws, primary_type=None, throw_type=None, group_by="month"):
    """Speed, distance and spin per period, oldest first."""
    ts = filter_throws(throws, primary_type=primary_type, throw_type=throw_type)
    buckets = defaultdict(list)
    for t in ts:
        buckets[_bucket(t, group_by)].append(t)
    return [{"period": period, **_stats(buckets[period])} for period in sorted(buckets)]
