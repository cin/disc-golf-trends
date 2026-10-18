import shutil
from pathlib import Path

import pytest

import udisc_data as ud
import udisc_mcp as srv

FIXTURE = Path(__file__).parent / "fixtures" / "sample.csv"


@pytest.fixture
def csv_dir(tmp_path):
    shutil.copy(FIXTURE, tmp_path / "sample.csv")
    return tmp_path


@pytest.fixture
def alex(csv_dir):
    return ud.load_rounds(csv_dir, player="alex")


def test_fixture_rows_have_29_columns():
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        assert len(line.split(",")) == 29


def test_parse_date_with_offset():
    d = ud.parse_date("2026-10-17 1735-0400")
    assert (d.year, d.month, d.day, d.hour, d.minute) == (2026, 10, 17, 17, 35)
    assert d.utcoffset().total_seconds() == -4 * 3600
    assert ud.parse_date("") is None
    assert ud.parse_date("garbage") is None


def test_load_filters_player_case_insensitively_and_skips_par_rows(csv_dir):
    assert len(ud.load_rounds(csv_dir, player="ALEX")) == 5
    assert len(ud.load_rounds(csv_dir, player="sam")) == 1
    assert {r.player for r in ud.load_rounds(csv_dir)} == {"Alex", "Sam"}


def test_trailing_blank_hole_columns_trimmed(alex):
    by_course = {r.course: r.holes for r in alex}
    assert by_course == {"Pine Hollow": 9, "Oak Ridge": 6}


def test_to_par_uses_par_row(alex):
    assert [r.to_par for r in alex] == [3, 0, 2, 2, 0]


def test_partial_round_uses_only_scored_holes(alex):
    partial = alex[-1]
    assert partial.holes == 9
    assert partial.played == [1, 2, 3, 4]
    assert (partial.total, partial.par, partial.to_par) == (13, 13, 0)


def test_zero_means_unplayed_and_empty_rounds_are_dropped(tmp_path):
    header = FIXTURE.read_text(encoding="utf-8").splitlines()[0]
    pad = "," * 18  # 3 hole columns used, 18 empty
    lines = [
        header,
        f"Par,Test,Main,2026-01-01 1000-0400,2026-01-01 1100-0400,9,,,3,3,3{pad}",
        # the file's Total (99) disagrees with the holes; hole 3 was not played (0)
        f"Alex,Test,Main,2026-01-01 1000-0400,2026-01-01 1100-0400,99,0,,3,4,0{pad}",
        f"Par,Test,Main,2026-01-02 1000-0400,2026-01-02 1100-0400,9,,,3,3,3{pad}",
        f"Alex,Test,Main,2026-01-02 1000-0400,2026-01-02 1100-0400,0,0,,0,0,0{pad}",
    ]
    (tmp_path / "x.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    found = ud.load_rounds(tmp_path, player="Alex")
    assert len(found) == 1  # the all-zero round is dropped
    r = found[0]
    assert r.played == [1, 2]
    assert (r.total, r.par, r.to_par) == (7, 6, 1)


def test_overlapping_exports_deduplicated(csv_dir):
    shutil.copy(FIXTURE, csv_dir / "older-export.csv")
    assert len(ud.load_rounds(csv_dir, player="alex")) == 5


def test_missing_folder_and_empty_folder_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        ud.load_rounds(tmp_path / "nope")
    with pytest.raises(FileNotFoundError):
        ud.load_rounds(tmp_path)


def test_filter_rounds_by_date_and_course(alex):
    assert len(ud.filter_rounds(alex, start="2026-01-01")) == 3
    assert len(ud.filter_rounds(alex, end="2025-12-31")) == 2
    assert len(ud.filter_rounds(alex, course="oak")) == 1


def test_find_round_by_id_and_date(alex):
    r, _ = ud.find_round(alex, "2026-06-20 1800")
    assert r.course == "Oak Ridge"
    r, _ = ud.find_round(alex, "2026-06-20")
    assert r.course == "Oak Ridge"
    r, candidates = ud.find_round(alex, "1999-01-01")
    assert r is None
    assert candidates == []


def test_round_detail_holes(alex):
    detail = ud.round_detail(alex[0])
    assert detail["total"] == 33
    assert detail["holes_detail"][8] == {"hole": 9, "par": 4, "score": 5, "to_par": 1}


def test_list_courses_sorted_by_rounds(alex):
    courses = ud.list_courses(alex)
    assert [c["course"] for c in courses] == ["Pine Hollow", "Oak Ridge"]
    assert courses[0]["rounds"] == 4
    assert courses[0]["first_played"] == "2025-05-10"


def test_course_stats_ignores_partial_round_for_averages(alex):
    stats = ud.course_stats(alex, "Pine Hollow")
    assert stats["rounds"] == 4
    assert stats["avg_to_par"] == round((3 + 0 + 2) / 3, 2)
    assert stats["best"]["to_par"] == 0
    assert stats["worst"]["to_par"] == 3
    assert ud.course_stats(alex, "Nowhere") is None


def test_hole_stats_are_keyed_by_layout(alex):
    holes = ud.hole_stats(alex)
    assert {(h["course"], h["layout"]) for h in holes} == {("Pine Hollow", "Main"), ("Oak Ridge", "Short")}


def test_hole_problem_report_ranks_by_total_strokes_lost(alex):
    report = ud.hole_problem_report(alex, course="Pine Hollow", min_rounds=3)
    top = report[0]
    # hole 3 (par 4): +0, +0, +1, +0 -> 1 stroke; hole 9: +1, 0, 0 -> 1 stroke; hole 2: +1, 0, 0, 0
    assert top["total_strokes_over_par"] == 1
    assert all(h["rounds"] >= 3 for h in report)


def test_blowups_counted(alex):
    hole9 = next(h for h in ud.hole_stats(alex) if h["hole"] == 9 and h["course"] == "Pine Hollow")
    assert hole9["blowups"] == 0
    assert hole9["worst"] == 5


def test_scoring_trends_by_season_and_month(alex):
    seasons = ud.scoring_trends(alex, group_by="season")
    assert [(s["period"], s["rounds"]) for s in seasons] == [("2025", 2), ("2026", 2)]
    assert seasons[0]["avg_to_par"] == 1.5
    months = ud.scoring_trends(alex, course="Pine Hollow", group_by="month")
    assert [m["period"] for m in months] == ["2025-05", "2025-06", "2026-05"]
    with pytest.raises(ValueError):
        ud.scoring_trends(alex, group_by="week")


def test_compare_seasons(alex):
    cmp = ud.compare_seasons(alex, 2025, 2026)
    assert cmp["a"]["avg_to_par"] == 1.5
    assert cmp["b"]["avg_to_par"] == 2.0
    assert cmp["avg_to_par_change"] == 0.5
    assert ud.compare_seasons(alex, 2025, 1999)["avg_to_par_change"] is None


# ---------- server layer ----------


@pytest.fixture
def configured(csv_dir, monkeypatch):
    monkeypatch.setenv("UDISC_CSV_DIR", str(csv_dir))
    monkeypatch.setenv("UDISC_PLAYER", "Alex")
    srv._cache.update(key=None, rounds=None)
    return csv_dir


def test_tools_return_data(configured):
    assert srv.list_rounds(limit=2)[0]["date"] == "2026-07-01"
    assert srv.get_round("2025-05-10")["total"] == 33
    assert "error" in srv.get_round("1999-01-01")
    assert srv.course_stats("zzz") == {"error": "no rounds at a course matching 'zzz'"}
    status = srv.export_status()
    assert status["rounds"] == 5
    assert status["last_round"] == "2026-07-01"


def test_cache_reloads_when_new_export_added(configured):
    assert len(srv.rounds()) == 5
    extra = FIXTURE.read_text(encoding="utf-8").splitlines()
    row = extra[9].replace("2026-06-20 1800", "2026-08-01 1800").replace("2026-06-20 1840", "2026-08-01 1840")
    header = extra[0]
    par = extra[8].replace("2026-06-20 1800", "2026-08-01 1800").replace("2026-06-20 1840", "2026-08-01 1840")
    (configured / "newer.csv").write_text("\n".join([header, par, row]) + "\n", encoding="utf-8")
    assert len(srv.rounds()) == 6


def test_missing_config_exits(monkeypatch):
    monkeypatch.delenv("UDISC_CSV_DIR", raising=False)
    with pytest.raises(SystemExit):
        srv.need("UDISC_CSV_DIR")


def test_all_tools_registered_read_only():
    import asyncio

    tools = asyncio.run(srv.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "export_status",
        "list_rounds",
        "get_round",
        "list_courses",
        "course_stats",
        "scoring_trends",
        "hole_problem_report",
        "compare_seasons",
        "throw_export_status",
        "list_throws",
        "throw_stats",
        "throw_trends",
    }
    assert all(t.annotations and t.annotations.read_only_hint for t in tools)
