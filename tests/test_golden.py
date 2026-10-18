"""The golden files that pin the TypeScript port (site/) must match what this Python code produces."""

import json
from datetime import datetime

import golden
import pytest

# Throw days are compared as local dates; the fixtures sit around midday UTC (15:00 in sample throws.csv), so the
# dates only agree for a machine zone between UTC-11 and UTC+8.
_hours = datetime.now().astimezone().utcoffset().total_seconds() / 3600


@pytest.mark.skipif(not -11 <= _hours <= 8, reason="golden throw dates assume a zone between UTC-11 and UTC+8")
def test_golden_files_are_current():
    assert golden.SYNTHETIC_SCORECARDS.read_text(encoding="utf-8") == golden.synthetic_scorecards()
    assert golden.SYNTHETIC_THROWS.read_text(encoding="utf-8") == golden.synthetic_throws()
    committed = json.loads(golden.GOLDEN.read_text(encoding="utf-8"))
    assert committed == golden.build(), r"run: .venv\Scripts\python tests\golden.py"
