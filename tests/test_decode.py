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


def test_absolute_hr_renders_bpm(tr):
    # the bike plan has an absolute-HR target (102-127, no %) -> render as bpm
    plan = D.decode_plan(load("bike_threshold"), tr)
    humans = [s.target.human() for w in plan.workouts for b in w.blocks
              for s in ([b] if isinstance(b, D.Step) else b.steps)]
    assert any("bpm" in h for h in humans), "expected an absolute HR rendered as bpm"


def test_no_bare_kind_target(tr):
    # an absolute (non-%) HR/pace/power target must not render a misleading
    # bare "@ HR"/"@ pace"/"@ power" — Target.human() returns "" instead.
    for name in ("bike_threshold", "run_intervals_pace", "run_simple", "strength_injury_prevention"):
        plan = D.decode_plan(load(name), tr)
        for w in plan.workouts:
            for b in w.blocks:
                for s in ([b] if isinstance(b, D.Step) else b.steps):
                    assert s.target.human() not in ("HR", "pace", "power"), \
                        f"{name}: bare kind target on {s.name!r}"
                    assert " @ HR" not in s.human() and " @ pace" not in s.human()


def test_readable_titles_preserved_regression(tr):
    """REGRESSION (iron rule): the title fallback must NOT clobber real names.

    run_simple's program names ("4 mile with strides", ...) are human-readable
    but are NOT dictionary keys, so translate() returns them unchanged. The
    equality-miss fallback must keep them verbatim — only unresolved
    *shortcode-shaped* names (W30291) fall back to "<Sport> Workout".
    """
    data = load("run_simple")
    raw_names = [p.get("name") for p in data["programs"]]
    plan = D.decode_plan(data, tr)
    assert [w.title for w in plan.workouts] == raw_names


def test_dictionary_resolved_titles_preserved(tr):
    """Names that DO resolve in the dictionary keep their resolved value
    (the fallback never fires for them)."""
    for fx in ("bike_threshold", "strength_injury_prevention"):
        data = load(fx)
        plan = D.decode_plan(data, tr)
        for w, p in zip(plan.workouts, data["programs"]):
            assert w.title == tr(p["name"])
            assert w.title != f"{w.sport} Workout"


def test_title_fallback_for_untranslated_shortcode(tr):
    """Only an unresolved, shortcode-shaped (or empty) name falls back."""
    assert D._workout_title("ZZ99999", tr, "Run", 0) == "Run Workout"   # unknown code -> fallback
    assert D._workout_title("", tr, "Bike", 2) == "Bike Workout"        # empty -> fallback
    assert D._workout_title("", tr, "", 4) == "Workout 5"               # no sport -> indexed
    assert D._workout_title("4 mile easy", tr, "Run", 0) == "4 mile easy"  # readable -> kept
    assert D._workout_title("T3001", tr, "Run", 0) == "Training"        # resolves -> dictionary value


def test_title_fallback_edge_cases(tr):
    """Defensive edges surfaced in adversarial review."""
    # non-string name must not crash the decode (coerced -> fallback)
    assert D._workout_title(12345, tr, "Run", 0) == "Run Workout"
    assert D._workout_title(None, tr, "Bike", 1) == "Bike Workout"
    # a shortcode with trailing whitespace (COROS data has e.g. "E11002\xa0")
    # must still be treated as a code, not leaked raw
    assert D._workout_title("W30291\xa0", tr, "Run", 0) == "Run Workout"
    # human names that merely look codish (<=2 digits) are KEPT, not clobbered
    for name in ("EMOM12", "WOD21", "Z30", "AMRAP20"):
        assert D._workout_title(name, tr, "Strength", 0) == name


def _workout(name):
    return json.load(open(os.path.join(FIX, f"{name}.json")))["data"]


def test_decode_workout_run_intervals(tr):
    w = D.decode_workout(_workout("workout_run_intervals"), tr)
    assert w.sport == "Run" and w.is_rich
    groups = [b for b in w.blocks if isinstance(b, D.RepeatGroup)]
    assert groups and groups[0].count >= 2, "expected an interval repeat group"
    targets = [s.target for b in w.blocks
               for s in ([b] if isinstance(b, D.Step) else b.steps)]
    assert any(t.kind == "pace" and t.pct_low for t in targets), "expected pace %targets"


def test_decode_workout_strength_sets(tr):
    w = D.decode_workout(_workout("workout_strength_sets"), tr)
    assert w.sport in ("Strength", "Hybrid") and w.is_rich
    steps = [s for b in w.blocks for s in ([b] if isinstance(b, D.Step) else b.steps)]
    assert any(s.dur_kind == "reps" for s in steps), "expected rep-based strength steps"


def test_decode_workout_swim_renders_structure(tr):
    # Swim is not a RICH_SPORT, but it decodes into blocks and now renders its
    # set structure (has_structure tier) instead of an overview-only blank.
    w = D.decode_workout(_workout("workout_swim"), tr)
    assert w.sport == "Swim" and not w.is_rich
    assert w.has_structure and w.blocks
    body = D.format_description(w)
    assert "Workout:" in body, "swim body must now show its steps"
    assert "×" in body, "swim interval repeats (e.g. 6×) must render"
    assert " m" in body, "swim per-step distances (metres) must render"


def test_decode_workout_climb_renders_structure(tr):
    # Climb (sportType 7) also renders structure; its %target is real data.
    w = D.decode_workout(_workout("workout_climb"), tr)
    assert w.sport == "Climb" and not w.is_rich
    assert w.has_structure
    assert "Workout:" in D.format_description(w)


def test_has_structure_predicate():
    assert D.Workout(index=0, sport="Swim", title="x",
                     blocks=[D.Step(role="active", name="Swim", dur_kind="distance", dur_value=100)]).has_structure
    assert not D.Workout(index=0, sport="Swim", title="x").has_structure  # no blocks -> overview only


def test_decode_workout_missing_title_falls_back(tr):
    w = D.decode_workout(_workout("workout_missing_title"), tr)
    assert w.title == "Run Workout"   # name was an unresolved W-code


def test_parse_coros_url_workout():
    assert C.parse_coros_url(
        "https://training.coros.com/workout-program?programId=478&region=2") == ("workout", "478", "2")
    assert C.parse_coros_url("https://x?workoutId=99")[:2] == ("workout", "99")


def test_parse_coros_url_plan():
    assert C.parse_coros_url(
        "https://training.coros.com/schedule-plan/share?planId=123&region=1") == ("plan", "123", "1")
    assert C.parse_coros_url("https://x?planId=123")[2] == "1"   # region defaults


def test_parse_coros_url_rejects_bare_and_garbage():
    for bad in ("478100463168962560", "https://example.com/nope", "", None):
        with pytest.raises(ValueError):
            C.parse_coros_url(bad)


def test_parse_coros_url_planId_wins_over_programId():
    # both ids present -> a plan link is unambiguous, planId wins
    assert C.parse_coros_url("https://x/share?planId=123&programId=456")[:2] == ("plan", "123")


def test_parse_coros_url_ignores_nested_id_in_other_param():
    # a programId buried in a redirect/next value must NOT hijack a plan link
    assert C.parse_coros_url(
        "https://x/share?planId=123&next=/p?programId=456")[:2] == ("plan", "123")


def test_decode_workout_rejects_non_dict_payload(tr):
    for bad in ([], "x", None, 5):
        with pytest.raises(ValueError):
            D.decode_workout(bad, tr)


def test_distance_cm_to_m(tr):
    plan = D.decode_plan(load("run_simple"), tr)
    dists = [s.dur_value for w in plan.workouts for b in w.blocks
             for s in ([b] if isinstance(b, D.Step) else b.steps) if s.dur_kind == "distance"]
    # COROS distances are cm; decoded metres should be realistic (10m–100km)
    assert dists and all(10 <= d <= 100000 for d in dists)
