"""Settings from .env and the mtime-keyed caches of parsed exports, shared by the MCP server and the dashboard.

Nothing here exits the process: a missing or bad setting raises ConfigError, so a tool call fails with a message
instead of taking the server down. `udisc_mcp.main()` calls `check_required()` once at startup to fail fast.
"""

import os
import stat
from pathlib import Path

import techdisc_data as td
import udisc_data as ud

HERE = Path(__file__).resolve().parent
REQUIRED = ("UDISC_CSV_DIR", "UDISC_PLAYER")

_cache = {"key": None, "rounds": None}
_throw_cache = {"key": None, "throws": None}


class ConfigError(Exception):
    """A setting is missing or invalid."""


def load_env():
    env_file = HERE / ".env"
    if not env_file.exists():
        return
    if os.name == "posix" and env_file.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ConfigError(f"{env_file} is readable by other users; run: chmod 600 .env")
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def need(name):
    v = os.environ.get(name)
    if not v:
        raise ConfigError(f"Missing {name} in .env")
    return v


def check_required():
    """Raise ConfigError for the first missing required setting, or a bad optional one."""
    for name in REQUIRED:
        need(name)
    min_hole_rounds()


def min_hole_rounds():
    raw = os.environ.get("MIN_HOLE_ROUNDS", "3")
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise ConfigError(f"MIN_HOLE_ROUNDS must be a whole number of 1 or more, got {raw!r}")
    return value


def clear_caches():
    _cache.update(key=None, rounds=None)
    _throw_cache.update(key=None, throws=None)


def _signature(directory):
    """Name, mtime and size of each CSV; a file that vanishes mid-scan is skipped."""
    out = []
    for p in sorted(Path(directory).glob("*.csv")):
        try:
            st = p.stat()
        except FileNotFoundError:
            continue
        out.append((p.name, st.st_mtime_ns, st.st_size))
    return tuple(out)


def rounds():
    """The configured player's rounds. Re-read whenever a CSV in the folder is added or changes."""
    directory, player = need("UDISC_CSV_DIR"), need("UDISC_PLAYER")
    key = (directory, player, _signature(directory) if Path(directory).is_dir() else None)
    if _cache["key"] != key:
        _cache["rounds"] = ud.load_rounds(directory, player=player)
        _cache["key"] = key
    return _cache["rounds"]


def throws():
    """All TechDisc throws. Re-read whenever a CSV in the folder is added or changes."""
    directory = need("TECHDISC_CSV_DIR")
    key = (directory, _signature(directory) if Path(directory).is_dir() else None)
    if _throw_cache["key"] != key:
        _throw_cache["throws"] = td.load_throws(directory)
        _throw_cache["key"] = key
    return _throw_cache["throws"]
