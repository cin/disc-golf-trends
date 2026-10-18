#!/usr/bin/env python3
"""Read-only MCP server (stdio) for questions about UDisc scorecard CSV exports.

Config comes from a .env file next to this script (see .env.example). No credentials are involved: the
server only reads CSV files exported from the UDisc app and never contacts UDisc or modifies anything.
"""

import sys
from datetime import datetime
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

import config
import techdisc_data as td
import udisc_data as ud

STALE_DAYS = 30  # export_status flags an export older than this
MAX_LIMIT = 500  # most rows a list tool returns

GroupBy = Literal["month", "season"]

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

# ---------- tools ----------


@mcp.tool(annotations=READ_ONLY)
def export_status() -> dict:
    """How fresh the data is: newest round, newest export file, and a stale warning."""
    rs = config.rounds()
    directory = config.need("UDISC_CSV_DIR")
    exported = ud.latest_export_mtime(directory)
    last = rs[-1].start if rs else None
    now = datetime.now().astimezone()
    age = (now - exported).days if exported else None
    return {
        "player": config.need("UDISC_PLAYER"),
        "rounds": len(rs),
        "first_round": rs[0].start.date().isoformat() if rs else None,
        "last_round": last.date().isoformat() if last else None,
        "export_file_updated": exported.date().isoformat() if exported else None,
        "export_age_days": age,
        "stale": age is not None and age > STALE_DAYS,
        "rounds_with_scratched_holes": sum(1 for r in rs if r.scratched),
        "rounds_with_unexplained_total_gap": sum(1 for r in rs if r.total_gap is not None),
        "note": "Data only includes rounds up to the last export; re-export from the UDisc app for newer rounds. A "
        "scratched hole is left out when UDisc's own Total shows it did not count; get_round shows which.",
    }


@mcp.tool(annotations=READ_ONLY)
def list_rounds(
    start: str | None = None, end: str | None = None, course: str | None = None, limit: int = 50
) -> list[dict]:
    """List rounds, newest first. start/end are YYYY-MM-DD (inclusive); course matches by substring."""
    rs = ud.filter_rounds(config.rounds(), start=start, end=end, course=course)
    return [ud.summarize_round(r) for r in reversed(rs)][: max(1, min(limit, MAX_LIMIT))]


@mcp.tool(annotations=READ_ONLY)
def get_round(round_id: str) -> dict:
    """Hole-by-hole scores for one round. round_id is 'YYYY-MM-DD HHMM' from list_rounds, or a date if unambiguous."""
    r, candidates = ud.find_round(config.rounds(), round_id)
    if r is None:
        if candidates:
            return {"error": "several rounds that day; use one of these round_ids", "round_ids": candidates}
        return {"error": f"no round matching {round_id!r}"}
    return ud.round_detail(r)


@mcp.tool(annotations=READ_ONLY)
def list_courses() -> list[dict]:
    """Courses played, with rounds played, layouts and first/last played dates."""
    return ud.list_courses(config.rounds())


@mcp.tool(annotations=READ_ONLY)
def course_stats(course: str, layout: str | None = None, include_holes: bool = False) -> dict:
    """Average, best and worst rounds, per-layout stats and the 3 best and worst holes for a course (substring match).

    include_holes adds the average for every hole; that list is long for multi-layout courses."""
    out = ud.course_stats(config.rounds(), course, layout, include_holes=include_holes)
    return out or {"error": f"no rounds at a course matching {course!r}"}


@mcp.tool(annotations=READ_ONLY)
def scoring_distribution(
    course: str | None = None,
    layout: str | None = None,
    start: str | None = None,
    end: str | None = None,
    group_by: GroupBy | None = None,
) -> list[dict]:
    """Share of holes scored eagle or better, birdie, par, bogey, double and triple or worse.

    start/end are YYYY-MM-DD (inclusive). group_by is omitted for one overall row, or 'month' or 'season'."""
    return ud.scoring_distribution(
        config.rounds(), course=course, layout=layout, start=start, end=end, group_by=group_by
    )


@mcp.tool(annotations=READ_ONLY)
def scoring_trends(course: str | None = None, layout: str | None = None, group_by: GroupBy = "month") -> list[dict]:
    """Average score vs par over time, grouped by 'month' or 'season' (calendar year); complete rounds only."""
    return ud.scoring_trends(config.rounds(), course=course, layout=layout, group_by=group_by)


@mcp.tool(annotations=READ_ONLY)
def hole_problem_report(
    course: str | None = None, layout: str | None = None, top_n: int = 10, min_rounds: int | None = None
) -> list[dict]:
    """Holes that have cost the most total strokes over par, with average and blow-up counts.

    A blow-up is a hole played 2 or more strokes over par (double bogey or worse)."""
    return ud.hole_problem_report(
        config.rounds(),
        course=course,
        layout=layout,
        top_n=top_n,
        min_rounds=min_rounds if min_rounds is not None else config.min_hole_rounds(),
    )


@mcp.tool(annotations=READ_ONLY)
def compare_seasons(year_a: int, year_b: int, course: str | None = None) -> dict:
    """Compare two calendar years: rounds, average score vs par, best/worst round and the change."""
    return ud.compare_seasons(config.rounds(), year_a, year_b, course=course)


@mcp.tool(annotations=READ_ONLY)
def throw_export_status() -> dict:
    """How fresh the TechDisc data is: throw count, first/last throw, export file age and a stale warning."""
    ts = config.throws()
    exported = td.latest_export_mtime(config.need("TECHDISC_CSV_DIR"))
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
    ts = td.filter_throws(config.throws(), start=start, end=end, primary_type=primary_type, throw_type=throw_type)
    return [td.summarize_throw(t) for t in reversed(ts)][: max(1, min(limit, MAX_LIMIT))]


@mcp.tool(annotations=READ_ONLY)
def throw_stats(start: str | None = None, end: str | None = None) -> dict:
    """TechDisc averages and maxima (speed, distance, spin, angles), overall and by throw style."""
    return td.throw_stats(config.throws(), start=start, end=end)


@mcp.tool(annotations=READ_ONLY)
def throw_trends(
    primary_type: str | None = None, throw_type: str | None = None, group_by: GroupBy = "month"
) -> list[dict]:
    """TechDisc speed, distance and spin over time, grouped by 'month' or 'season' (calendar year)."""
    return td.throw_trends(config.throws(), primary_type=primary_type, throw_type=throw_type, group_by=group_by)


def main():
    try:
        config.load_env()
        config.check_required()
    except config.ConfigError as e:
        sys.exit(str(e))
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
