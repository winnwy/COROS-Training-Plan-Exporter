"""Regression tests for coros_decode against committed raw fixtures."""
import json, os, sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import coros_decode as D
import convert_to_ics as C

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    return json.load(open(os.path.join(FIX, f"{name}.json")))["data"]


def translate(k):
    v = C.translate_key(k, C.load_dictionary())
    return v if v != k else (k if not k else "")  # blank unknown empty keys


@pytest.fixture(scope="module")
def tr():
    # real dictionary translator
    d = C.load_dictionary()
    return lambda k: (C.translate_key(k, d) if k else "")


def test_bike_intervals_preserved(tr):
    plan = D.decode_plan(load("bike_threshold"), tr)
    # at least one workout must contain a RepeatGroup with >1 count and members
    groups = [b for w in plan.workouts for b in w.blocks if isinstance(b, D.RepeatGroup)]
    assert groups, "expected interval RepeatGroups in the threshold bike plan"
    g = max(groups, key=lambda x: x.count)
    assert g.count >= 2 and len(g.steps) >= 2


def test_hr_pct_range_decoded(tr):
    plan = D.decode_plan(load("bike_threshold"), tr)
    targets = [s.target for w in plan.workouts for b in w.blocks
               for s in ([b] if isinstance(b, D.Step) else b.steps)]
    hr = [t for t in targets if t.kind == "HR" and t.pct_low]
    assert hr, "expected HR %threshold targets in bike plan"
    assert any(t.is_range for t in hr), "expected at least one HR range (e.g. 96–102%)"


def test_run_pace_targets(tr):
    plan = D.decode_plan(load("run_intervals_pace"), tr)
    targets = [s.target for w in plan.workouts for b in w.blocks
               for s in ([b] if isinstance(b, D.Step) else b.steps)]
    assert any(t.kind == "pace" and t.pct_low for t in targets), "expected pace %threshold targets"


def test_multisport_decodes_all_sports(tr):
    plan = D.decode_plan(load("multisport_cross"), tr)
    sports = {w.sport for w in plan.workouts}
    # cross-training mixes run/bike/strength; decoder must not crash on any
    assert len(sports) >= 2
    # non-rich sports still produce a workout object (graceful), just not rich body
    for w in plan.workouts:
        assert w.title


def test_no_blank_step_names(tr):
    plan = D.decode_plan(load("run_simple"), tr)
    for w in plan.workouts:
        for b in w.blocks:
            steps = [b] if isinstance(b, D.Step) else b.steps
            for s in steps:
                assert s.name and s.name.strip(), "step name should never be blank"


def test_description_renders_and_caps(tr):
    plan = D.decode_plan(load("bike_threshold"), tr)
    w = next(w for w in plan.workouts if any(isinstance(b, D.RepeatGroup) for b in w.blocks))
    desc = D.format_description(w)
    assert "×" in desc and "@" in desc          # interval + target rendered
    assert len(D.format_description(w, max_chars=50)) <= 50


def test_distance_cm_to_m(tr):
    plan = D.decode_plan(load("run_simple"), tr)
    dists = [s.dur_value for w in plan.workouts for b in w.blocks
             for s in ([b] if isinstance(b, D.Step) else b.steps) if s.dur_kind == "distance"]
    # COROS distances are cm; decoded metres should be realistic (10m–100km)
    assert dists and all(10 <= d <= 100000 for d in dists)
