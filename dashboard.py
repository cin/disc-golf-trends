#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard of scoring, hole and TechDisc trends.

Usage: python dashboard.py [--out dashboards/udisc-dashboard.html] [--player "Name"]

Reads the same CSV exports and .env settings as the MCP server and writes one HTML file that works offline: no
network requests, no animation. The file embeds real rounds, so the default output folder (dashboards/) is
git-ignored. Only one player's rows are embedded: the configured player's, or the one named by --player.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import udisc_data as ud
import udisc_mcp as srv

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "dashboard_template.html"
DEFAULT_OUT = HERE / "dashboards" / "udisc-dashboard.html"
MIN_COURSE_ROUNDS = 4  # layouts played at least this often get their own entry in the course filter


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "player"


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
    ap.add_argument("--out", type=Path, help=f"output file (default {DEFAULT_OUT}, or one per --player)")
    ap.add_argument(
        "--player",
        help="another player in your export, matched exactly (ignoring case). Only rounds you scored together "
        "are in the export; your TechDisc throws are left out",
    )
    args = ap.parse_args(argv)
    srv.load_env()
    me = srv.need("UDISC_PLAYER")
    friend = args.player and args.player.strip().lower() != me.lower()
    if friend:
        rounds = ud.load_rounds(srv.need("UDISC_CSV_DIR"), player=args.player.strip())
        if not rounds:
            raise SystemExit(f"no rounds found for player {args.player!r}")
        throws, name = [], rounds[0].player
    else:
        rounds, name = srv.rounds(), me
        try:
            throws = srv.throws()
        except (SystemExit, FileNotFoundError):  # TECHDISC_CSV_DIR not set, or no throw export yet
            throws = []
    payload = build_payload(rounds, throws, name)
    if friend:
        payload["note"] = "only rounds scored together with you"
    out = args.out or (DEFAULT_OUT.with_name(f"udisc-dashboard-{_slug(name)}.html") if friend else DEFAULT_OUT)
    html = render(payload)
    args.out = out
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"wrote {args.out} ({len(rounds)} rounds, {len(throws)} throws)")


if __name__ == "__main__":
    main()
