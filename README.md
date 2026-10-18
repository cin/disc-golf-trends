# disc-golf-trends

Your disc golf rounds and practice throws, from your own exports. It has three parts: a read-only
[MCP](https://modelcontextprotocol.io) server that lets Claude answer questions about your rounds, courses and
scoring trends, an offline HTML dashboard of the same data, and a [website](#website) where anyone can pick their own
CSV and see the dashboard in the browser. (Formerly `disc-golf-journal` and `udisc-mcp`. Not affiliated with UDisc or
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
git clone https://github.com/cin/disc-golf-trends.git
cd disc-golf-trends
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
| `MIN_HOLE_ROUNDS` | Optional. Rounds a hole needs before `hole_problem_report` ranks it: a whole number of 1 or more (default 3) |

The `.env` file is git-ignored. It holds only paths and a name, no secrets. The server exits at startup with a clear
message if `UDISC_CSV_DIR` or `UDISC_PLAYER` is missing or `MIN_HOLE_ROUNDS` is invalid, and on Linux/macOS if `.env`
is readable by other users (`chmod 600 .env`). A setting that goes wrong later (say the folder is deleted) fails that
one tool call, not the server.

## Register with Claude

Claude Code:

```
claude mcp add udisc -- C:\path\to\disc-golf-trends\.venv\Scripts\python C:\path\to\disc-golf-trends\udisc_mcp.py
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "udisc": {
      "command": "C:\\path\\to\\disc-golf-trends\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\disc-golf-trends\\udisc_mcp.py"]
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
| `course_stats` | Average/best/worst rounds, per-layout stats, 3 best and worst holes; `include_holes` adds every hole |
| `scoring_trends` | Score vs par by month or season, optionally per course |
| `scoring_distribution` | Share of holes at eagle or better, birdie, par, bogey, double, triple or worse; overall, by month or by season |
| `hole_problem_report` | Holes that cost the most strokes over par, with blow-up counts (a blow-up is a double bogey or worse) |
| `compare_seasons` | Two calendar years side by side |
| `throw_export_status` | TechDisc: throw count, first/last throw, export age, stale warning |
| `list_throws` | TechDisc: throws by date range, Backhand/Forehand and Hyzer/Flat, newest first |
| `throw_stats` | TechDisc: speed, distance, spin and angle averages/maxima, overall and by throw style |
| `throw_trends` | TechDisc: those numbers by month or season |

Dates (`start`, `end`) are `YYYY-MM-DD` and inclusive; anything else is rejected with a message instead of silently
returning the wrong rounds. `group_by` accepts only `month` or `season`. `list_rounds` and `list_throws` return at most
500 rows.

Example questions: "Which holes at my home course cost me the most strokes?", "How has my scoring trended each season?",
"Compare 2025 and 2026."

## Dashboard

```
.venv\Scripts\python dashboard.py        # writes dashboards\udisc-dashboard.html
```

One self-contained HTML file with three tabs, opened by double-clicking it: **Scoring** (strokes over par and round
rating by month, quarter or season, with the best and worst periods ringed; every round as a dot, with new personal
bests at a course in blue; the three costliest holes highlighted; birdies and blow-ups per round; the share of holes
at each score by season; a courses table),
**Holes** (where the strokes go on a chosen course, and a hole-by-season heatmap) and **Throws** (TechDisc speed and
distance trends). Filters at the top scope the whole page by course and date range; "Highlight season" shades one
season on the charts and dims the others without filtering anything. Every chart has a table view. Holes shows one
course at a time, so with "All courses" it asks you to pick one (and offers your most played). Throws only uses the
date range, and says so next to the greyed-out course and season controls.

**Themes** (menu at the top right, remembered in the browser): *System* follows your light or dark setting,
*Mocha* is Catppuccin Mocha, and the third entry is the opposite of your system look (Dark on a light system, Light
on a dark one). `?theme=system`, `?theme=mocha`, `?theme=dark` or `?theme=light` in the address picks one; dark or
light only applies when it is the opposite of the system look. It makes no network requests and has no animation. Re-run the command after each new export.

`--player "Name"` builds the same dashboard for another player in your export (name matched exactly, ignoring case),
written to `dashboards\udisc-dashboard-name.html`. The export only holds rounds you scored together, so that
dashboard covers those rounds, and your TechDisc throws are left out.

The file embeds real rounds, so `dashboards/` is git-ignored. Each file holds one player's rows.

## Website

**Live at <https://cin.github.io/disc-golf-trends/>.** `site/` is the same dashboard as a static web page: a visitor
picks their own UDisc and/or TechDisc CSV export and sees the charts. Nothing is uploaded. The files are read in the
browser tab, and the built page's content security policy stops the page from making network requests. It is written
in TypeScript (a port of `udisc_data.py` and `techdisc_data.py`) and draws with the same `dashboard_template.html` as
the Python dashboard, so there is one set of charts to maintain. A scorecard export includes everyone you played
with; the page asks whose rounds to show and starts with the player who has the most. "Try it with sample data" loads
made-up rounds and throws.

Working on it needs Node.js 22.12 or newer (24 recommended); the Python parts do not need Node.

```
cd site
npm install
npm run dev        # http://localhost:5173/, add ?sample to load made-up data
npm test           # unit tests, plus a check that the port gives the Python implementation's answers
npm run build      # static files in site/dist/
```

The port is held to the Python code by `tests/golden.py`: it runs every query over the fixtures (including a larger
made-up dataset) and writes `site/tests/golden.json`, and the TypeScript tests must reproduce it exactly. After
changing the Python statistics, run `.venv\Scripts\python tests\golden.py` and commit the result; a Python test fails
when the file is stale. Pushes to `main` that touch `site/`, the dashboard template or the fixtures are published to
GitHub Pages by `.github/workflows/pages.yml`.

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
cd site && npm test && npm run typecheck      # the website, needs Node.js
```

Tests use made-up data in `tests/fixtures/` (`sample.csv` and `throws.csv`, plus larger generated
`synthetic_*.csv`). Never commit your real export: `*.csv` is git-ignored except for `tests/fixtures/`.
`.github/workflows/ci.yml` runs all of the above on every push and pull request.

## License

MIT, see [LICENSE](LICENSE).
