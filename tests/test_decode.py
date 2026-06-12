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


def test_strength_is_rich_and_decodes(tr):
    plan = D.decode_plan(load("strength_injury_prevention"), tr)
    assert plan.workouts, "strength plan should decode workouts"
    assert all(w.sport in ("Strength", "Hybrid") for w in plan.workouts), "expected strength/hybrid sport"
    assert all(w.is_rich for w in plan.workouts), "strength must render rich now"


def test_strength_sets_reps_and_weight(tr):
    plan = D.decode_plan(load("strength_injury_prevention"), tr)
    steps = [s for w in plan.workouts for b in w.blocks
             for s in ([b] if isinstance(b, D.Step) else b.steps)]
    # weighted movement: reps + sets>1 + a kg weight target
    weighted = [s for s in steps if s.target.kind == "weight" and s.target.weight_g]
    assert weighted, "expected at least one weighted movement"
    w = weighted[0]
    assert "kg" in w.target.human()
    reps_sets = [s for s in steps if s.dur_kind == "reps" and s.sets > 1]
    assert reps_sets, "expected movements with multiple sets"
    # rendered line shows the NxM sets form
    assert "×" in reps_sets[0].human()


def test_strength_bodyweight_has_no_weight(tr):
    plan = D.decode_plan(load("strength_injury_prevention"), tr)
    steps = [s for w in plan.workouts for b in w.blocks
             for s in ([b] if isinstance(b, D.Step) else b.steps)]
    # a bodyweight movement (intensityType weight but no value, or no intensity)
    # must not render "@ weight"/"@ 0"
    for s in steps:
        assert "@ weight" not in s.human() and "@ 0" not in s.human()


def test_strength_description_renders(tr):
    plan = D.decode_plan(load("strength_injury_prevention"), tr)
    w = max(plan.workouts, key=lambda x: len(x.blocks))
    desc = D.format_description(w)
    assert "Workout:" in desc
    # should contain at least one set/rep or hold token
    assert ("×" in desc) or ("reps" in desc) or ("hold" in desc)


def test_distance_cm_to_m(tr):
    plan = D.decode_plan(load("run_simple"), tr)
    dists = [s.dur_value for w in plan.workouts for b in w.blocks
             for s in ([b] if isinstance(b, D.Step) else b.steps) if s.dur_kind == "distance"]
    # COROS distances are cm; decoded metres should be realistic (10m–100km)
    assert dists and all(10 <= d <= 100000 for d in dists)
