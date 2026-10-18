#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard of scoring, hole and TechDisc trends.

Usage: python dashboard.py [--out dashboards/udisc-dashboard.html]

Reads the same CSV exports and .env settings as the MCP server and writes one HTML file that works offline: no
network requests, no animation. The file embeds your real rounds, so the default output folder (dashboards/) is
git-ignored. Only the configured player's rows are embedded; other players in the export are left out.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

import udisc_mcp as srv

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "dashboard_template.html"
DEFAULT_OUT = HERE / "dashboards" / "udisc-dashboard.html"
MIN_COURSE_ROUNDS = 4  # layouts played at least this often get their own entry in the course filter


def _round_payload(r):
    return {
        "i": r.round_id,
        "d": r.start.date().isoformat(),
        "c": r.course,
        "l": r.layout,
        "h": r.holes,
        "t": r.total,
        "p": r.par,
        "tp": r.to_par,
        "r": r.rating,
        "s": r.scores,
        "q": r.pars,
        "f": r.to_par is not None and len(r.played) == r.holes,
    }


def _throw_payload(t):
    return {
        "d": t.when.date().isoformat(),
        "sp": t.speed_mph,
        "di": t.distance_ft,
        "sr": t.spin_rpm,
        "la": t.launch_angle,
        "hy": t.hyzer_angle,
        "pt": t.primary_type,
        "tt": t.throw_type,
    }


def build_payload(rounds, throws, player):
    """The JSON the page renders from. Rounds are the player's only; courses lists the filterable layouts."""
    counts = Counter((r.course, r.layout) for r in rounds)
    courses = [
        {"key": f"{course}|{layout}", "course": course, "layout": layout, "n": n}
        for (course, layout), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        if n >= MIN_COURSE_ROUNDS
    ]
    return {
        "player": player,
        "through": rounds[-1].start.date().isoformat() if rounds else None,
        "rounds": [_round_payload(r) for r in rounds],
        "courses": courses,
        "throws": [_throw_payload(t) for t in throws],
    }


def render(payload, template_path=TEMPLATE):
    # "</" would end the embedding <script> tag early, so escape it
    data = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    return Path(template_path).read_text(encoding="utf-8").replace("__DATA__", data)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write the HTML dashboard.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output file (default {DEFAULT_OUT})")
    args = ap.parse_args(argv)
    srv.load_env()
    rounds = srv.rounds()
    try:
        throws = srv.throws()
    except (SystemExit, FileNotFoundError):  # TECHDISC_CSV_DIR not set, or no throw export yet
        throws = []
    html = render(build_payload(rounds, throws, srv.need("UDISC_PLAYER")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"wrote {args.out} ({len(rounds)} rounds, {len(throws)} throws)")


if __name__ == "__main__":
    main()
