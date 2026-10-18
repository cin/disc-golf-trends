# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`disc-golf-journal` (formerly `udisc-mcp`) turns the owner's own UDisc scorecard and TechDisc throw CSV exports into answers and charts: a read-only MCP server (stdio, `mcp` 2.x `MCPServer`, registered under the name `udisc`) and an offline HTML dashboard. It is not affiliated with UDisc or TechDisc. `README.md` is the user-facing guide; don't duplicate it here. A Scala port of the MCP server for comparison lives in the sibling project `disc-golf-journal-scala`. The module names `udisc_data.py` and `udisc_mcp.py` are kept on purpose: they are the UDisc-specific parts.

## Commands

Use the project venv (`.venv`); on Windows call `.venv\Scripts\python` directly.

```
.venv\Scripts\python -m pytest -q
.venv\Scripts\ruff check .
```

Dev dependencies are exact-pinned in `pyproject.toml`; bump deliberately.

## Architecture

- `udisc_data.py`: pure parsing and statistics, no MCP code. `load_rounds` reads every `*.csv` in a folder, pairs each player row with the round's `Par` row, and de-duplicates on (player, course, layout, start).
- `techdisc_data.py`: same idea for TechDisc throw exports (one row per throw, de-duplicated on `id`, `timeSeconds` for time). Python only; the Scala port does not have it.
- `dashboard.py` + `dashboard_template.html`: generates a self-contained offline HTML dashboard (`dashboards/`, git-ignored). Python builds a JSON payload (player's rows only); the template renders inline SVG charts with plain JS, no libraries or network. Keep it free of animation and flashing (accessibility), set text with `textContent` only (tests enforce no `innerHTML`/`transition`/`animation`), and follow the dataviz palette (blue/orange, diverging blue-red heatmap). To check rendering: `msedge --headless=new --screenshot=...` against the generated file (`?theme=dark|light`, `#scoring|#holes|#throws`).
- `config.py`: `.env` loading (same hand-rolled `load_env`/`need` as grade-watch) and the mtime-keyed caches of parsed rounds and throws, shared by the server and the dashboard. It raises `ConfigError` and never exits, so a bad setting fails one tool call, not the server; `udisc_mcp.main()` calls `check_required()` once at startup and exits there.
- `common.py`: helpers shared by both data modules (`check_day` validates `start`/`end` dates).
- `site/`: the browser version (Vite + TypeScript, static, deployed to GitHub Pages by `.github/workflows/pages.yml`). `src/udisc.ts` and `src/techdisc.ts` are ports of the two data modules and keep their snake_case result keys; `src/payload.ts` ports `build_payload`/`render`; `src/app.ts` is the DOM-free page logic and `src/main.ts` the wiring. It reuses `dashboard_template.html` unchanged, filling it into an iframe (`srcdoc`), so chart changes happen once. Visitors' files never leave the tab: the build injects a CSP with `connect-src 'none'`, so keep it that way (no fetches, no analytics, no external scripts or fonts).
- Parity: `tests/golden.py` writes `site/tests/golden.json` (and the synthetic fixtures `tests/fixtures/synthetic_*.csv`) from the Python code; `site/tests/golden.test.ts` must reproduce it exactly, and `tests/test_golden.py` fails when it is stale. After changing any statistic or loader rule in Python, run `.venv\Scripts\python tests\golden.py`, port the change, and commit both. Python's `round()` and `statistics.mean` differ from JavaScript's (ties to even; exact mean rounded once), so use `pyRound` and `mean` from `site/src/common.ts`, never `Math.round` or a naive sum, in the port. Node is needed for `site/` (`cd site && npm test`).
- `udisc_mcp.py`: one thin `@mcp.tool` per query. `group_by` is a `Literal` so the schema rejects bad values; list tools clamp `limit` to `MAX_LIMIT`.
- Every top-level module must be listed in `py-modules` in `pyproject.toml` (a test checks). Install with `pip install -e .`: `.env` and the dashboard template are found relative to the checkout.

Invariants:

- **Read-only.** No tool writes anywhere; every tool carries `readOnlyHint`. The server never contacts UDisc (its ToS prohibits scraping).
- A hole score of `0` means not played; all-zero rounds are dropped; totals are summed from holes, never read from the `Total` column.
- Hole stats are keyed by (course, layout, hole).
- Both exports may share one folder: files are identified by header (`PlayerName`+`StartDate` vs `speedMph`), never by name. `export_status` must not count the throw file's mtime.

## Conventions

- `.env`, `*.csv` (except `tests/fixtures/`), and `fixtures/real/` are git-ignored: real exports contain other people's names. Tests use made-up data only.
- Never push to GitHub and never delete anything without the owner's explicit approval.
- The commit trailer used in this repo is `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
