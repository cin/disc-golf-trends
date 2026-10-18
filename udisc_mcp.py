#!/usr/bin/env python3
"""Read-only MCP server (stdio) for questions about UDisc scorecard CSV exports.

Config comes from a .env file next to this script (see .env.example). No credentials are involved: the
server only reads CSV files exported from the UDisc app and never contacts UDisc or modifies anything.
"""

import os
import stat
import sys
from datetime import datetime
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

import techdisc_data as td
import udisc_data as ud

HERE = Path(__file__).resolve().parent
STALE_DAYS = 30  # export_status flags an export older than this

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

mcp = MCPServer(
    "udisc",
    instructions=(
        "Answers questions about the user's disc golf rounds from a UDisc CSV export. Scores are strokes; "
        "'to_par' is strokes over (+) or under (-) par. Call export_status first if freshness matters. "
        "Hole numbers are only comparable within one course layout. The throw_* and list_throws tools cover "
        "TechDisc practice throws (speed, distance, spin, angles), which are separate from rounds."
    ),
)

_cache = {"key": None, "rounds": None}
_throw_cache = {"key": None, "throws": None}


# ---------- config ----------


def load_env():
    env_file = HERE / ".env"
    if not env_file.exists():
        return
    if os.name == "posix" and env_file.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        sys.exit(f"{env_file} is readable by other users; run: chmod 600 .env")
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def need(name):
    v = os.environ.get(name)
    if not v:
        sys.exit(f"Missing {name} in .env")
    return v


def min_hole_rounds():
    return int(os.environ.get("MIN_HOLE_ROUNDS", "3"))


def _signature(directory):
    return tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(Path(directory).glob("*.csv")))


def rounds():
    """The configured player's rounds. Re-read whenever a CSV in the folder is added or changes."""
    directory, player = need("UDISC_CSV_DIR"), need("UDISC_PLAYER")
    key = (directory, player, _signature(directory) if Path(directory).is_dir() else None)
    if _cache["key"] != key:
        _cache["rounds"] = ud.load_rounds(directory, player=player)
        _cache["key"] = key
    return _cache["rounds"]


# ---------- tools ----------


@mcp.tool(annotations=READ_ONLY)
def export_status() -> dict:
    """How fresh the data is: newest round, newest export file, and a stale warning."""
    rs = rounds()
    directory = need("UDISC_CSV_DIR")
    exported = ud.latest_export_mtime(directory)
    last = rs[-1].start if rs else None
    now = datetime.now().astimezone()
    age = (now - exported).days if exported else None
    return {
        "player": need("UDISC_PLAYER"),
        "rounds": len(rs),
        "first_round": rs[0].start.date().isoformat() if rs else None,
        "last_round": last.date().isoformat() if last else None,
        "export_file_updated": exported.date().isoformat() if exported else None,
        "export_age_days": age,
        "stale": age is not None and age > STALE_DAYS,
        "note": "Data only includes rounds up to the last export; re-export from the UDisc app for newer rounds.",
    }


@mcp.tool(annotations=READ_ONLY)
def list_rounds(
    start: str | None = None, end: str | None = None, course: str | None = None, limit: int = 50
) -> list[dict]:
    """List rounds, newest first. start/end are YYYY-MM-DD (inclusive); course matches by substring."""
    rs = ud.filter_rounds(rounds(), start=start, end=end, course=course)
    return [ud.summarize_round(r) for r in reversed(rs)][: max(1, limit)]


@mcp.tool(annotations=READ_ONLY)
def get_round(round_id: str) -> dict:
    """Hole-by-hole scores for one round. round_id is 'YYYY-MM-DD HHMM' from list_rounds, or a date if unambiguous."""
    r, candidates = ud.find_round(rounds(), round_id)
    if r is None:
        if candidates:
            return {"error": "several rounds that day; use one of these round_ids", "round_ids": candidates}
        return {"error": f"no round matching {round_id!r}"}
    return ud.round_detail(r)


@mcp.tool(annotations=READ_ONLY)
def list_courses() -> list[dict]:
    """Courses played, with rounds played, layouts and first/last played dates."""
    return ud.list_courses(rounds())


@mcp.tool(annotations=READ_ONLY)
def course_stats(course: str, layout: str | None = None, include_holes: bool = False) -> dict:
    """Average, best and worst rounds, per-layout stats and the 3 best and worst holes for a course (substring match).

    include_holes adds the average for every hole; that list is long for multi-layout courses."""
    out = ud.course_stats(rounds(), course, layout, include_holes=include_holes)
    return out or {"error": f"no rounds at a course matching {course!r}"}


@mcp.tool(annotations=READ_ONLY)
def scoring_distribution(
    course: str | None = None,
    layout: str | None = None,
    start: str | None = None,
    end: str | None = None,
    group_by: str | None = None,
) -> list[dict]:
    """Share of holes scored eagle or better, birdie, par, bogey, double and triple or worse.

    start/end are YYYY-MM-DD (inclusive). group_by is omitted for one overall row, or 'month' or 'season'."""
    return ud.scoring_distribution(rounds(), course=course, layout=layout, start=start, end=end, group_by=group_by)


@mcp.tool(annotations=READ_ONLY)
def scoring_trends(course: str | None = None, layout: str | None = None, group_by: str = "month") -> list[dict]:
    """Average score vs par over time, grouped by 'month' or 'season' (calendar year); complete rounds only."""
    return ud.scoring_trends(rounds(), course=course, layout=layout, group_by=group_by)


@mcp.tool(annotations=READ_ONLY)
def hole_problem_report(
    course: str | None = None, layout: str | None = None, top_n: int = 10, min_rounds: int | None = None
) -> list[dict]:
    """Holes that have cost the most total strokes over par, with average and blow-up counts.

    A blow-up is a hole played 2 or more strokes over par (double bogey or worse)."""
    return ud.hole_problem_report(
        rounds(), course=course, layout=layout, top_n=top_n, min_rounds=min_rounds or min_hole_rounds()
    )


@mcp.tool(annotations=READ_ONLY)
def compare_seasons(year_a: int, year_b: int, course: str | None = None) -> dict:
    """Compare two calendar years: rounds, average score vs par, best/worst round and the change."""
    return ud.compare_seasons(rounds(), year_a, year_b, course=course)


def throws():
    """All TechDisc throws. Re-read whenever a CSV in the folder is added or changes."""
    directory = need("TECHDISC_CSV_DIR")
    key = (directory, _signature(directory) if Path(directory).is_dir() else None)
    if _throw_cache["key"] != key:
        _throw_cache["throws"] = td.load_throws(directory)
        _throw_cache["key"] = key
    return _throw_cache["throws"]


@mcp.tool(annotations=READ_ONLY)
def throw_export_status() -> dict:
    """How fresh the TechDisc data is: throw count, first/last throw, export file age and a stale warning."""
    ts = throws()
    exported = td.latest_export_mtime(need("TECHDISC_CSV_DIR"))
    age = (datetime.now().astimezone() - exported).days
    return {
        "throws": len(ts),
        "first_throw": ts[0].when.date().isoformat() if ts else None,
        "last_throw": ts[-1].when.date().isoformat() if ts else None,
        "export_file_updated": exported.date().isoformat(),
        "export_age_days": age,
        "stale": age > STALE_DAYS,
        "note": "Only throws up to the last TechDisc export are included.",
    }


@mcp.tool(annotations=READ_ONLY)
def list_throws(
    start: str | None = None,
    end: str | None = None,
    primary_type: str | None = None,
    throw_type: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List TechDisc throws, newest first. primary_type is Backhand/Forehand; throw_type is e.g. Hyzer/Flat."""
    ts = td.filter_throws(throws(), start=start, end=end, primary_type=primary_type, throw_type=throw_type)
    return [td.summarize_throw(t) for t in reversed(ts)][: max(1, limit)]


@mcp.tool(annotations=READ_ONLY)
def throw_stats(start: str | None = None, end: str | None = None) -> dict:
    """TechDisc averages and maxima (speed, distance, spin, angles), overall and by throw style."""
    return td.throw_stats(throws(), start=start, end=end)


@mcp.tool(annotations=READ_ONLY)
def throw_trends(
    primary_type: str | None = None, throw_type: str | None = None, group_by: str = "month"
) -> list[dict]:
    """TechDisc speed, distance and spin over time, grouped by 'month' or 'season' (calendar year)."""
    return td.throw_trends(throws(), primary_type=primary_type, throw_type=throw_type, group_by=group_by)


def main():
    load_env()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
