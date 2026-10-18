import os
import shutil
import time
from pathlib import Path

import pytest

import techdisc_data as td
import udisc_data as ud
import udisc_mcp as srv

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def td_dir(tmp_path):
    shutil.copy(FIXTURES / "throws.csv", tmp_path / "throws.csv")
    return tmp_path


@pytest.fixture
def mixed_dir(td_dir):
    """One folder holding both a throw export and a UDisc scorecard export, like the real setup."""
    shutil.copy(FIXTURES / "sample.csv", td_dir / "scorecards.csv")
    return td_dir


def test_load_throws_sorted_and_parsed(td_dir):
    ts = td.load_throws(td_dir)
    assert len(ts) == 7
    assert [t.when for t in ts] == sorted(t.when for t in ts)
    first = ts[0]
    assert (first.primary_type, first.throw_type) == ("Backhand", "Hyzer")
    assert (first.speed_mph, first.distance_ft, first.spin_rpm) == (45.0, 200.0, 800.0)
    assert ts[2].notes == "warmup"


def test_duplicate_exports_deduplicated(td_dir):
    shutil.copy(FIXTURES / "throws.csv", td_dir / "older.csv")
    assert len(td.load_throws(td_dir)) == 7


def test_files_told_apart_by_header(mixed_dir):
    assert [p.name for p in td.throw_files(mixed_dir)] == ["throws.csv"]
    assert [p.name for p in ud.scorecard_files(mixed_dir)] == ["scorecards.csv"]
    assert len(td.load_throws(mixed_dir)) == 7
    assert len(ud.load_rounds(mixed_dir, player="alex")) == 5


def test_loaders_reject_missing_or_wrong_files(td_dir, tmp_path_factory):
    with pytest.raises(FileNotFoundError):
        ud.load_rounds(td_dir)  # only a throw export in the folder
    with pytest.raises(FileNotFoundError):
        td.load_throws(td_dir / "nope")
    only_scorecards = tmp_path_factory.mktemp("scorecards")
    shutil.copy(FIXTURES / "sample.csv", only_scorecards / "scorecards.csv")
    with pytest.raises(FileNotFoundError):
        td.load_throws(only_scorecards)


def test_filter_throws(td_dir):
    ts = td.load_throws(td_dir)
    assert len(td.filter_throws(ts, primary_type="backhand")) == 4
    assert len(td.filter_throws(ts, throw_type="FLAT")) == 4
    assert len(td.filter_throws(ts, start="2026-06-01")) == 4
    assert len(td.filter_throws(ts, end="2026-05-31", primary_type="Forehand")) == 1


def test_throw_stats_overall_and_by_style(td_dir):
    stats = td.throw_stats(td.load_throws(td_dir))
    assert stats["overall"]["throws"] == 7
    assert stats["overall"]["max_speed_mph"] == 49.0
    assert stats["overall"]["max_distance_ft"] == 240.0
    assert stats["overall"]["avg_speed_mph"] == round((45 + 47 + 40 + 49 + 44 + 42 + 44) / 7, 2)
    styles = {(s["primary_type"], s["throw_type"]): s for s in stats["by_style"]}
    assert styles[("Backhand", "Hyzer")]["throws"] == 3
    assert styles[("Backhand", "Hyzer")]["avg_distance_ft"] == 220.0
    assert styles[("Forehand", "Flat")]["throws"] == 3
    assert stats["by_style"][0]["throws"] == 3  # most-thrown first


def test_throw_stats_date_range_and_empty(td_dir):
    ts = td.load_throws(td_dir)
    assert td.throw_stats(ts, start="2026-06-01")["overall"]["throws"] == 4
    empty = td.throw_stats(ts, start="2030-01-01")
    assert empty["overall"]["throws"] == 0
    assert empty["overall"]["avg_speed_mph"] is None
    assert empty["first_throw"] is None


def test_throw_trends_by_month_and_season(td_dir):
    ts = td.load_throws(td_dir)
    months = td.throw_trends(ts, group_by="month")
    assert [(m["period"], m["throws"]) for m in months] == [("2026-05", 3), ("2026-06", 4)]
    assert months[0]["avg_speed_mph"] == round((45 + 47 + 40) / 3, 2)
    assert td.throw_trends(ts, primary_type="Backhand", group_by="season")[0]["throws"] == 4
    with pytest.raises(ValueError):
        td.throw_trends(ts, group_by="week")


# ---------- server layer ----------


@pytest.fixture
def configured(mixed_dir, monkeypatch):
    monkeypatch.setenv("UDISC_CSV_DIR", str(mixed_dir))
    monkeypatch.setenv("TECHDISC_CSV_DIR", str(mixed_dir))
    monkeypatch.setenv("UDISC_PLAYER", "Alex")
    srv._cache.update(key=None, rounds=None)
    srv._throw_cache.update(key=None, throws=None)
    return mixed_dir


def test_throw_tools_return_data(configured):
    listed = srv.list_throws(limit=2)
    assert listed[0]["when"] > listed[1]["when"]
    assert srv.throw_stats()["overall"]["throws"] == 7
    assert len(srv.throw_trends(group_by="month")) == 2
    status = srv.throw_export_status()
    assert status["throws"] == 7


def test_export_status_ignores_throw_file(configured):
    """A fresh throws.csv must not make the scorecard export look fresh."""
    old = time.time() - 90 * 86400
    os.utime(configured / "scorecards.csv", (old, old))
    assert srv.export_status()["stale"] is True
    assert srv.throw_export_status()["stale"] is False


def test_throw_tools_need_setting(monkeypatch):
    monkeypatch.delenv("TECHDISC_CSV_DIR", raising=False)
    with pytest.raises(SystemExit):
        srv.throws()
