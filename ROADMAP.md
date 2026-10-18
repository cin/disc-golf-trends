# Roadmap and side quests

Ideas that are not built yet, and known gaps. None of them blocks the current server or the website.

## Data quality: scratched holes

When a hole is scratched ("-" in the UDisc app), the export still holds a placeholder score in that hole's column but
leaves it out of the file's `Total`. The loader now uses `Total` as a cross-check (see `_reconcile_total` in
`udisc_data.py`, ported in `site/src/udisc.ts`): if the hole sum exceeds `Total` by exactly one hole's score, that hole
is dropped. What it does not do yet:

- **Several scratched holes in one round.** The gap is then the sum of two or more scores, which no single hole
  explains, so it is reported (`total_gap`) but nothing is dropped. Trying subsets of holes is possible, but the
  more holes could fit, the more likely a wrong guess; probably only worth it when exactly one subset fits.
- **Ambiguous gaps.** If several holes have the score that equals the gap (a gap of 3 with four 3s), nothing is dropped.
  A small local corrections file (round and hole, read-only like the exports) would let the owner say which hole it
  was. The read-only invariant allows reading it.
- **Where the flags show.** `get_round` shows `scratched_holes` and `total_gap`, `export_status` counts them and the
  website prints a note. `list_rounds` and the Python dashboard do not mention them; a marker in `list_rounds` and a
  line in the dashboard subtitle would close that.

## More questions the server could answer

- **Birdies (and eagles, aces) by hole.** `hole_stats` has averages, best, worst and blow-up counts but no birdie
  counts, so "how many birdies on each hole of this course" needs a script today. Add `birdies`, `eagles_or_better`
  (and an ace count) to `hole_stats`, `course_stats(include_holes=True)` and the Holes tab tables, then port them and
  regenerate `site/tests/golden.json`.
- **Aces.** A tool or a field for "when and where were my aces" falls out of the same change.

## Training: distance and control

TechDisc speed and distance trends (Throws tab of the dashboard) show whether practice or training is paying off in
distance and control. The ideas below are not built yet, and are only meaningful once there are several months of
throws:

- **Consistency ("control")**: spread (standard deviation) of hyzer, nose and launch angle and of distance, within a
  throw style such as backhand hyzer, by month. Needs a throw-style filter on the Throws tab.
- **Training log**: if you keep one (dates, sessions), overlay it on speed and distance trends. Needs a data file.
- **Speed to distance**: scatter of speed against distance per throw, to see whether added speed turns into distance.

## Side quest: on-course throw tracking (Apple Watch and friends)

Goal: capture throw speed, angle and similar numbers while playing a round, and feed them to this server as another
read-only CSV source (Python first, like TechDisc; the website would need a TypeScript loader too).

What is known (from App Store listings and UDisc help and forum pages; accuracy and current status unverified):

- **Arm Speed Analyzer** (Apple Watch): throw speed and acceleration from the watch accelerometer. Measures the arm,
  not the disc. Speed only, no spin or angles. Open question: can it export its data?
- **RipReader** (iPhone camera, phone on the ground): speed and spin. Not a watch app.
- **TechDisc** (sensor disc): speed, spin, launch, hyzer, nose and wobble angles. Already supported here. One disc
  only, and its data is not linked to rounds.
- **UDisc on the watch**: Apple Watch scoring is a Pro feature. A forum reply says full-stats throw tracking arrived
  on Pixel/WearOS in 2025; Apple Watch is not mentioned. Check the current app.
- **Tracked-shot rounds**: the UDisc scorecard CSV has only per-hole scores, so shot locations and distances are not
  visible to this server. UDisc's staff have said on the forum that practice data (throws, putting) has no CSV export
  and that it is not on the near-term roadmap, and a forum thread reports that league Full Stats are not in the
  scorecard CSV either. Re-check the app's export menu now and then.

Next steps when picking this up:

1. Find out whether Arm Speed Analyzer (or any watch app) can export throws; get a sample file.
2. Check the UDisc app for any new export of tracked shots.
3. If a file exists, look at its columns first, then add a small loader next to `techdisc_data.py` (and a port in
   `site/src/`, covered by `tests/golden.py`, if the website should show it).

Linking practice or on-course throws to rounds would have to go by date. That needs more throws than a first
TechDisc export usually holds.

## Website

The site at https://cin.github.io/disc-golf-trends/ works and is tested against the Python implementation, but:

- **No automated browser test.** The page logic (`site/src/app.ts`) and the sample-data path are unit tested. The real
  file input, drag and drop, tab switching, the course dropdown and the minimizing setup cards were checked by driving
  the built page in headless Edge over the DevTools protocol, but that script is not in the repo. A Playwright test
  that picks the fixture files, switches tabs and changes the course dropdown would keep it checked. It would have
  caught a real bug: inside the site's `about:srcdoc` frame `history.replaceState` throws, so the tabs looked stuck
  until something else re-rendered (now guarded, with a template test).
- **Not tried with a screen reader.** The page uses native `<details>`, labelled controls, a live status region and
  no animation, but it has only been checked in a browser engine, not with assistive technology.
- **TechDisc export instructions.** The page says how to export from UDisc but only describes the TechDisc file by its
  columns: searches turned up nothing from TechDisc on exporting, so the app's steps are unconfirmed. Add them once
  known (ask TechDisc, or check the app and its support site).
- **Throws only for the main player.** A scorecard export lists co-players, but a TechDisc export has no player name,
  so the page shows throws only for the player with the most rounds.
- **Python and TypeScript differences.** A few deliberate ones are listed in `CLAUDE.md`. If a visitor's file hits one,
  bring the two back in line (probably by making Python as strict as the port, e.g. rejecting `nan` in throw columns).
- **Small polish.** No favicon or social preview image.

## Housekeeping

- **The Scala port is behind.** `disc-golf-journal-scala` (a separate sibling project) only covers the round tools and
  was not updated for the later Python changes: `include_holes`, `scoring_distribution`, input validation and the
  scratched-hole rule, and it lacks `best_round` in `scoring_trends`. Check it before using it as a comparison.
- **Dependency updates.** Everything is exact-pinned (Python, npm and the GitHub Actions), so nothing updates by
  itself. Dependabot for `pip`, `npm` and `github-actions` would open the bump PRs; CI would then show whether each
  one is safe.
