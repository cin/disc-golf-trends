# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`udisc-mcp` is a read-only MCP server (stdio, `mcp` 2.x `MCPServer`) over UDisc scorecard CSV exports. `README.md` is the user-facing guide; don't duplicate it here. A Scala port for comparison lives in the sibling project `udisc-mcp-scala`.

## Commands

Use the project venv (`.venv`); on Windows call `.venv\Scripts\python` directly.

```
.venv\Scripts\python -m pytest -q
.venv\Scripts\ruff check .
```

Dev dependencies are exact-pinned in `pyproject.toml`; bump deliberately.

## Architecture

- `udisc_data.py`: pure parsing and statistics, no MCP code. `load_rounds` reads every `*.csv` in a folder, pairs each player row with the round's `Par` row, and de-duplicates on (player, course, layout, start).
- `udisc_mcp.py`: `.env` loading (same hand-rolled `load_env`/`need` as grade-watch), an mtime-keyed cache of the parsed rounds, and one thin `@mcp.tool` per query.

Invariants:

- **Read-only.** No tool writes anywhere; every tool carries `readOnlyHint`. The server never contacts UDisc (its ToS prohibits scraping).
- A hole score of `0` means not played; all-zero rounds are dropped; totals are summed from holes, never read from the `Total` column.
- Hole stats are keyed by (course, layout, hole).

## Conventions

- `.env`, `*.csv` (except `tests/fixtures/`), and `fixtures/real/` are git-ignored: real exports contain other people's names. Tests use made-up data only.
- Never push to GitHub and never delete anything without the owner's explicit approval.
- The commit trailer used in this repo is `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
