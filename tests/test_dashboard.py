import json
import re
import shutil
from pathlib import Path

import pytest

import dashboard
import techdisc_data as td
import udisc_data as ud
import udisc_mcp as srv

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def data_dir(tmp_path):
    shutil.copy(FIXTURES / "sample.csv", tmp_path / "scorecards.csv")
    shutil.copy(FIXTURES / "throws.csv", tmp_path / "throws.csv")
    return tmp_path


def embedded(html):
    return json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))


def test_payload_has_only_the_configured_player(data_dir):
    rounds = ud.load_rounds(data_dir, player="Alex")
    payload = dashboard.build_payload(rounds, td.load_throws(data_dir), "Alex")
    assert payload["player"] == "Alex"
    assert len(payload["rounds"]) == 5
    assert payload["through"] == "2026-07-01"
    assert len(payload["throws"]) == 7
    assert "Sam" not in json.dumps(payload)  # other players in the export are never embedded


def test_round_fields_and_partial_round_flag(data_dir):
    payload = dashboard.build_payload(ud.load_rounds(data_dir, player="Alex"), [], "Alex")
    first, partial = payload["rounds"][0], payload["rounds"][-1]
    assert (first["c"], first["l"], first["t"], first["p"], first["tp"], first["f"]) == (
        "Pine Hollow",
        "Main",
        33,
        30,
        3,
        True,
    )
    assert len(first["s"]) == len(first["q"]) == 9
    assert partial["f"] is False  # 4 of 9 holes scored


def test_courses_filter_needs_four_rounds(data_dir):
    payload = dashboard.build_payload(ud.load_rounds(data_dir, player="Alex"), [], "Alex")
    assert [(c["key"], c["n"]) for c in payload["courses"]] == [("Pine Hollow|Main", 4)]  # Oak Ridge has 1


def test_render_embeds_data_and_escapes_script_end(data_dir):
    rounds = ud.load_rounds(data_dir, player="Alex")
    payload = dashboard.build_payload(rounds, [], "Alex")
    payload["player"] = "</script><b>x"
    html = dashboard.render(payload)
    assert "__DATA__" not in html
    assert html.count("</script>") == 2  # the data block and the code block, none from the payload
    assert embedded(html)["player"] == "</script><b>x"


def test_template_renders_text_without_innerhtml():
    source = dashboard.TEMPLATE.read_text(encoding="utf-8")
    assert "innerHTML" not in source  # labels come from CSV data, so they must only go in as text
    assert "transition" not in source and "animation" not in source  # no motion or flashing


def test_main_writes_file_from_env(data_dir, tmp_path_factory, monkeypatch):
    out = tmp_path_factory.mktemp("out") / "nested" / "dash.html"
    monkeypatch.setenv("UDISC_CSV_DIR", str(data_dir))
    monkeypatch.setenv("TECHDISC_CSV_DIR", str(data_dir))
    monkeypatch.setenv("UDISC_PLAYER", "Alex")
    srv._cache.update(key=None, rounds=None)
    srv._throw_cache.update(key=None, throws=None)
    dashboard.main(["--out", str(out)])
    payload = embedded(out.read_text(encoding="utf-8"))
    assert (len(payload["rounds"]), len(payload["throws"])) == (5, 7)


def test_main_works_without_techdisc(data_dir, tmp_path_factory, monkeypatch):
    out = tmp_path_factory.mktemp("out") / "dash.html"
    monkeypatch.setenv("UDISC_CSV_DIR", str(data_dir))
    monkeypatch.delenv("TECHDISC_CSV_DIR", raising=False)
    monkeypatch.setenv("UDISC_PLAYER", "Alex")
    srv._cache.update(key=None, rounds=None)
    srv._throw_cache.update(key=None, throws=None)
    monkeypatch.setattr(srv, "load_env", lambda: None)  # don't pick TECHDISC_CSV_DIR back up from the real .env
    dashboard.main(["--out", str(out)])
    assert embedded(out.read_text(encoding="utf-8"))["throws"] == []
