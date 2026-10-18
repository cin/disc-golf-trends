# disc-golf-journal

Your disc golf rounds and practice throws, from your own exports. It has two parts: a read-only
[MCP](https://modelcontextprotocol.io) server that lets Claude answer questions about your rounds, courses and
scoring trends, and an offline HTML dashboard of the same data. (Formerly `udisc-mcp`. Not affiliated with UDisc or
TechDisc.)

**No credentials and no network access.** UDisc has no public API, and its Terms prohibit scraping, so this project
never contacts UDisc or TechDisc. It only reads the CSV files their apps export. Nothing is modified.

## Get your data

In the UDisc mobile app: **You** tab → menu (top right) → **Rounds** → menu (top right) → **Export to CSV**.
Move the file into a folder of your choice. One export holds your whole history; re-export now and then to pick up
new rounds. Every `*.csv` in the folder is read and overlapping exports are de-duplicated, so you can drop new
exports next to old ones.

## Setup

Python 3.10 or newer.

```
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"      # Linux/macOS: .venv/bin/pip
copy .env.example .env                     # then edit it
```

`.env` (see `.env.example`):

| Variable | Meaning |
|---|---|
| `UDISC_CSV_DIR` | Folder holding your export(s) |
| `UDISC_PLAYER` | Your name exactly as in the `PlayerName` column |
| `TECHDISC_CSV_DIR` | Optional. Folder holding a TechDisc throw export; may be the same folder as `UDISC_CSV_DIR` (files are told apart by header). Without it the TechDisc tools report the missing setting |
| `MIN_HOLE_ROUNDS` | Optional. Rounds a hole needs before `hole_problem_report` ranks it (default 3) |

The `.env` file is git-ignored. It holds only paths and a name, no secrets. On Linux/macOS the server refuses to
start if `.env` is readable by other users (`chmod 600 .env`).

## Register with Claude

Claude Code:

```
claude mcp add udisc -- C:\path\to\disc-golf-journal\.venv\Scripts\python C:\path\to\disc-golf-journal\udisc_mcp.py
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "udisc": {
      "command": "C:\\path\\to\\disc-golf-journal\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\disc-golf-journal\\udisc_mcp.py"]
    }
  }
}
```

## Tools (all read-only)

| Tool | Answers |
|---|---|
| `export_status` | How fresh is the data? Newest round, export age, stale warning |
| `list_rounds` | Rounds by date range and course, newest first |
| `get_round` | Hole-by-hole scores vs par for one round |
| `list_courses` | Courses, layouts, rounds played, first/last played |
| `course_stats` | Average/best/worst rounds, per-layout and per-hole averages |
| `scoring_trends` | Score vs par by month or season, optionally per course |
| `hole_problem_report` | Holes that cost the most strokes over par, with blow-up counts |
| `compare_seasons` | Two calendar years side by side |
| `throw_export_status` | TechDisc: throw count, first/last throw, export age, stale warning |
| `list_throws` | TechDisc: throws by date range, Backhand/Forehand and Hyzer/Flat, newest first |
| `throw_stats` | TechDisc: speed, distance, spin and angle averages/maxima, overall and by throw style |
| `throw_trends` | TechDisc: those numbers by month or season |

Example questions: "Which holes at Gatewood cost me the most strokes?", "How has my scoring trended each season?",
"Compare 2025 and 2026."

## Dashboard

```
.venv\Scripts\python dashboard.py        # writes dashboards\udisc-dashboard.html
```

One self-contained HTML file with three tabs, opened by double-clicking it: **Scoring** (strokes over par and round
rating by month, quarter or season, with the best and worst periods ringed; every round as a dot, with new personal
bests at a course in blue; the three costliest holes highlighted; birdies and blow-ups per round; a courses table),
**Holes** (where the strokes go on a chosen course, and a hole-by-season heatmap) and **Throws** (TechDisc speed and
distance trends). Filters at the top scope the whole page by course and date range; "Highlight season" shades one
season on the charts and dims the others without filtering anything. Every chart has a table view, and it follows
your light or dark setting. It makes no network requests and has no animation. Re-run the command after each new export.

The file embeds your real rounds, so `dashboards/` is git-ignored. Only your own rows are included.

## Data notes

- The export has a `Par` row before each round's player rows. Par comes from there.
- A score of `0` means the hole was not played. Rounds with no scores are ignored, and partial rounds are left out of
  averages and trends.
- Totals are the sum of the hole scores; the file's `Total` column is ignored because it can disagree with them.
- Hole numbers are only compared within one course layout.
- The UDisc export has no throws, putts or penalty columns, so none are reported.
- TechDisc throws are practice data and are not linked to rounds (the export has no course or round column).
  Throw times come from `timeSeconds` and are shown in this computer's local time zone.
- When both exports share a folder, each loader ignores the other's files by header, and `export_status` only
  looks at scorecard files.

## Development

```
.venv\Scripts\python -m pytest -q
.venv\Scripts\ruff check .
```

Tests use made-up data in `tests/fixtures/sample.csv`. Never commit your real export: `*.csv` is git-ignored except
for `tests/fixtures/`.
