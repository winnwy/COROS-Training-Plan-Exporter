"""Regression tests for date alignment + the --start CLI flag.

These guard the dayNo->date bug fixed 2026-06-12 (week was ((dayNo-1)//7)+1,
which shifted ~all workouts off their real dates) and the non-interactive
start-date flag (CLI used to hang on input() with no TTY).
"""
import io
import os
import sys
import subprocess
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import convert_to_ics as C

REPO = os.path.join(os.path.dirname(__file__), "..")


# ---- date mapping (the actual bug site) ----
def test_day_no_mapping_invariant():
    # (week-1)*7 + day_of_week must reconstruct dayNo for the whole plan range
    for d in range(0, 84):
        week, dow = C.day_no_to_week_dow(d)
        assert (week - 1) * 7 + dow == d, f"dayNo {d} -> week {week}, dow {dow}"


def test_day_no_mapping_known_points():
    assert C.day_no_to_week_dow(0) == (1, 0)    # day 0 = week 1, Monday
    assert C.day_no_to_week_dow(7) == (2, 0)    # used to wrongly land in week 1
    assert C.day_no_to_week_dow(13) == (2, 6)
    assert C.day_no_to_week_dow(14) == (3, 0)


def _workout(day_no):
    week, dow = C.day_no_to_week_dow(day_no)
    return {"week": week, "day_of_week": dow, "title": f"d{day_no}", "dayNo": day_no,
            "description": "", "duration": None, "distance": None, "training_load": None}


def test_dates_equal_start_plus_dayno():
    # dayNos crossing week boundaries incl. multiples of 7 (where the bug fired)
    day_nos = [0, 1, 3, 4, 6, 7, 8, 13, 14, 15, 21, 28]
    start = datetime(2026, 6, 15)  # Monday
    rich = C.calculate_plan_dates([_workout(d) for d in day_nos], start)
    for w in rich:
        expected = (start + timedelta(days=w["dayNo"])).date()
        assert w["date_obj"].date() == expected, \
            f"dayNo={w['dayNo']}: got {w['date_obj'].date()} expected {expected}"


def test_first_workout_anchors_on_start():
    start = datetime(2026, 6, 15)  # Monday
    rich = C.calculate_plan_dates([_workout(0), _workout(2), _workout(7)], start)
    got = sorted(w["date_obj"].date() for w in rich)
    assert got[0] == datetime(2026, 6, 15).date()   # dayNo 0 -> start
    assert datetime(2026, 6, 22).date() in got       # dayNo 7 -> +1 week


# ---- --start flag / resolve_start_date ----
def test_resolve_start_date_explicit():
    assert C.resolve_start_date("2026-07-01") == datetime(2026, 7, 1)


def test_resolve_start_date_bad_raises():
    with pytest.raises(ValueError):
        C.resolve_start_date("07/01/2026")


def test_resolve_start_date_none_falls_back_to_today(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))  # immediate EOF, no hang
    assert C.resolve_start_date(None).date() == datetime.now().date()


def test_cli_bad_start_exits_without_hanging():
    # argparse validation error -> exit 2, must not block on input()
    r = subprocess.run(
        [sys.executable, "convert_to_ics.py", "--url", "x", "--start", "nope"],
        cwd=REPO, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20,
    )
    assert r.returncode == 2
    assert "invalid --start date" in r.stderr
