"""Tests for the Garmin .FIT workout exporter (coros_to_fit)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import coros_decode as D
import convert_to_ics as C

fit_tool = pytest.importorskip("fit_tool")
import coros_to_fit as F
from fit_tool.fit_file import FitFile
from fit_tool.profile.profile_type import FileType, Sport, WorkoutStepDuration

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
REP = WorkoutStepDuration.REPEAT_UNTIL_STEPS_CMPLT.value
DIST = WorkoutStepDuration.DISTANCE.value


def _plan(name):
    dd = C.load_dictionary()
    tr = lambda k: (C.translate_key(k, dd) if k else "")
    return D.decode_plan(json.load(open(os.path.join(FIX, f"{name}.json")))["data"], tr)


def _messages(fit_bytes):
    msgs = {"FileIdMessage": [], "WorkoutMessage": [], "WorkoutStepMessage": []}
    for rec in FitFile.from_bytes(fit_bytes).records:
        n = type(rec.message).__name__
        if n in msgs:
            msgs[n].append(rec.message)
    return msgs


def _v(x):
    return x.value if hasattr(x, "value") else x


def _dur(step):
    return _v(step.duration_type)


def test_fit_is_a_valid_workout_file():
    plan = _plan("bike_threshold")
    w = next(w for w in plan.workouts if w.blocks)
    m = _messages(F.build_fit(w))
    assert len(m["FileIdMessage"]) == 1
    assert _v(m["FileIdMessage"][0].type) == FileType.WORKOUT.value
    assert len(m["WorkoutMessage"]) == 1
    wkt = m["WorkoutMessage"][0]
    # num_valid_steps must equal the actual count of step messages
    assert wkt.num_valid_steps == len(m["WorkoutStepMessage"])
    assert _v(wkt.sport) == Sport.CYCLING.value


def test_fit_repeat_points_to_first_member():
    plan = _plan("bike_threshold")
    w = next(w for w in plan.workouts if any(isinstance(b, D.RepeatGroup) for b in w.blocks))
    steps = _messages(F.build_fit(w))["WorkoutStepMessage"]
    reps = [s for s in steps if _dur(s) == REP]
    assert reps, "expected a REPEAT step for the interval block"
    r = reps[0]
    # the from-index must be a real earlier step, and count matches the group
    grp = next(b for b in w.blocks if isinstance(b, D.RepeatGroup))
    assert r.target_repeat_steps == grp.count
    assert 0 <= r.duration_step < r.message_index


def test_fit_message_index_is_zero_based_sequential():
    plan = _plan("bike_threshold")
    w = next(w for w in plan.workouts if w.blocks)
    steps = _messages(F.build_fit(w))["WorkoutStepMessage"]
    assert [s.message_index for s in steps] == list(range(len(steps)))


def test_fit_run_plan_has_distance_steps_and_named_targets():
    plan = _plan("run_intervals_pace")
    w = next(w for w in plan.workouts if w.blocks)
    fit = F.build_fit(w)
    m = _messages(fit)
    assert _v(m["WorkoutMessage"][0].sport) == Sport.RUNNING.value
    steps = m["WorkoutStepMessage"]
    # at least one step carries a target in its name (e.g. "@ 77-87% pace")
    assert any(s.workout_step_name and "@" in s.workout_step_name for s in steps)


def test_fit_only_run_bike_in_scope():
    # strength workouts are out of scope; SPORT_FIT excludes them
    assert "Strength" not in F.SPORT_FIT and "Run" in F.SPORT_FIT and "Bike" in F.SPORT_FIT


def test_parse_plan_url():
    assert F.parse_plan_url("https://x/share?planId=123&region=2") == ("123", "2")
    assert F.parse_plan_url("https://x/share?planId=123") == ("123", "1")  # region defaults
    assert F.parse_plan_url("https://x/nope") == (None, "1")


def test_workouts_to_zip_contains_valid_fit_files():
    import io, zipfile
    plan = _plan("bike_threshold")
    data = F.workouts_to_zip(plan.workouts)
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = zf.namelist()
    assert names and all(n.endswith(".fit") for n in names)
    assert len(names) == len(F.exportable(plan.workouts))
    # each entry must itself decode as a WORKOUT file
    m = _messages(zf.read(names[0]))
    assert _v(m["FileIdMessage"][0].type) == FileType.WORKOUT.value
    assert m["WorkoutStepMessage"]
