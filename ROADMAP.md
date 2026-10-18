# Roadmap and side quests

Ideas that are not built yet. None of them blocks the current server.

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
read-only CSV source (Python only, like TechDisc).

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
3. If a file exists, look at its columns first, then add a small loader next to `techdisc_data.py`.

Linking practice or on-course throws to rounds would have to go by date. That needs more throws than a first
TechDisc export usually holds.
