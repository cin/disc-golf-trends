# Roadmap and side quests

Ideas that are not built yet. None of them blocks the current server or the website.

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

What is known (from App Store listings and UDisc forum posts; accuracy and current status unverified):

- **Arm Speed Analyzer** (Apple Watch): throw speed and acceleration from the watch accelerometer. Measures the arm,
  not the disc. Speed only, no spin or angles. Open question: can it export its data?
- **RipReader** (iPhone camera, phone on the ground): speed and spin. Not a watch app.
- **TechDisc** (sensor disc): speed, spin, launch, hyzer, nose and wobble angles. Already supported here. One disc
  only, and its data is not linked to rounds.
- **UDisc on the watch**: Apple Watch scoring is a Pro feature. A forum reply says full-stats throw tracking arrived
  on Pixel/WearOS in 2025; Apple Watch is not mentioned. Check the current app.
- **Tracked-shot rounds**: the UDisc scorecard CSV has only per-hole scores, so shot locations and distances are not
  visible to this server. A forum request for an export exists; no sign it was built. Re-check the app's export menu.

Next steps when picking this up:

1. Find out whether Arm Speed Analyzer (or any watch app) can export throws; get a sample file.
2. Check the UDisc app for any new export of tracked shots.
3. If a file exists, look at its columns first, then add a small loader next to `techdisc_data.py` (and a port in
   `site/src/`, covered by `tests/golden.py`, if the website should show it).

Linking practice or on-course throws to rounds would have to go by date. That needs more throws than a first
TechDisc export usually holds.

## Website

The site at https://cin.github.io/disc-golf-trends/ works and is tested against the Python implementation, but:

- **No automated browser test.** The file picker and drag and drop have only been checked by hand; the sample-data
  button and the page logic (`site/src/app.ts`) are tested. A Playwright test that picks the fixture files would close
  the gap.
- **TechDisc export instructions.** The page says how to export from UDisc but only describes the TechDisc file by its
  columns, because the app's export steps have not been confirmed. Add them once known.
- **Throws only for the main player.** A scorecard export lists co-players, but a TechDisc export has no player name,
  so the page shows throws only for the player with the most rounds.
- **Python and TypeScript differences.** A few deliberate ones are listed in `CLAUDE.md`. If a visitor's file hits one,
  bring the two back in line (probably by making Python as strict as the port, e.g. rejecting `nan` in throw columns).
