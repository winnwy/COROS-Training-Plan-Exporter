"""
Export a COROS run/bike/strength plan to Garmin .FIT structured-workout files.

One .fit per workout. Sideload by copying to the watch's GARMIN/NewFiles/
folder (some models: GARMIN/Workouts/) over USB — no account, no Garmin login.

Design notes (see docs/BUILD_PLAN.md §4c):
- Reuses the shared decoder (coros_decode) for the normalized Step/RepeatGroup
  model, so .ics / .ZWO / .FIT all share one source of truth.
- FIT structure: File Id (type=WORKOUT) -> Workout (num_valid_steps) -> ordered
  Workout Steps with zero-based message_index; intervals become a
  REPEAT_UNTIL_STEPS_CMPLT step pointing back to the first member.
- Targets: COROS gives %-of-threshold (HR/pace), which does NOT map cleanly onto
  FIT's %max-HR / zone model. Rather than encode a wrong absolute zone, we keep
  durations + repeats exact (the watch guides the structure and beeps on step
  changes) and put the intended target in the step NAME ("Training @ 96-102% HR").
- Scope: run, bike, and strength (strength sets expand to repeat blocks; sport
  TRAINING / sub-sport STRENGTH_TRAINING). Swim/climbing deferred.

Usage:
    python coros_to_fit.py --plan 459583119950004224 [--region 1] [--out ./fit] [--limit N]
"""
import argparse
import io
import os
import re
import sys
import zipfile
from datetime import datetime

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.workout_message import WorkoutMessage
from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
from fit_tool.profile.profile_type import (
    FileType, Sport, SubSport, Intensity, WorkoutStepDuration, WorkoutStepTarget,
)

sys.path.insert(0, os.path.dirname(__file__))
import coros_decode as D
import convert_to_ics as C
import requests

HDRS = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"}
DETAIL = "https://teamapi.coros.com/training/plan/detail"

SPORT_FIT = {"Run": Sport.RUNNING, "Bike": Sport.CYCLING,
             "Strength": Sport.TRAINING, "Hybrid": Sport.TRAINING}
STRENGTH_SPORTS = {"Strength", "Hybrid"}
INTENSITY_FIT = {
    "warmup": Intensity.WARMUP, "active": Intensity.ACTIVE, "rest": Intensity.REST,
    "recovery": Intensity.RECOVERY, "cooldown": Intensity.COOLDOWN,
}


def _step_name(step: D.Step) -> str:
    """Short label carrying the target, e.g. 'Training @ 96-102% HR'."""
    t = step.target.human()
    name = f"{step.name} @ {t}" if t else step.name
    return name[:48]


def _emit_step(idx: int, step: D.Step) -> WorkoutStepMessage:
    m = WorkoutStepMessage()
    m.message_index = idx
    m.workout_step_name = _step_name(step)
    m.intensity = INTENSITY_FIT.get(step.role, Intensity.ACTIVE)
    if step.dur_kind == "reps" and step.dur_value > 0:
        m.duration_type = WorkoutStepDuration.REPS        # strength: N reps
        m.duration_reps = step.dur_value
    elif step.dur_kind == "time" and step.dur_value > 0:
        m.duration_type = WorkoutStepDuration.TIME
        m.duration_time = float(step.dur_value)          # seconds
    elif step.dur_kind == "distance" and step.dur_value > 0:
        m.duration_type = WorkoutStepDuration.DISTANCE
        m.duration_distance = float(step.dur_value)      # metres
    else:
        m.duration_type = WorkoutStepDuration.OPEN        # lap-button to advance
    m.target_type = WorkoutStepTarget.OPEN
    return m


def _rest_step_for(seconds):
    return D.Step(role="rest", name="Rest", dur_kind="time", dur_value=int(seconds))


def _emit_repeat(idx: int, from_idx: int, count: int) -> WorkoutStepMessage:
    m = WorkoutStepMessage()
    m.message_index = idx
    m.duration_type = WorkoutStepDuration.REPEAT_UNTIL_STEPS_CMPLT
    m.duration_step = from_idx          # repeat from this message_index
    m.target_type = WorkoutStepTarget.OPEN
    m.target_repeat_steps = count       # number of repetitions
    return m


def workout_to_fit_steps(workout: D.Workout):
    """Flatten the normalized blocks into ordered FIT WorkoutStepMessages.

    Strength movements with multiple sets are expanded into a repeat block
    ([work, rest] x sets), which is how a watch guides straight sets."""
    strength = workout.sport in STRENGTH_SPORTS
    steps = []

    def add(step):
        steps.append(_emit_step(len(steps), step))

    def add_repeat(from_idx, count):
        steps.append(_emit_repeat(len(steps), from_idx, count))

    def add_movement(s):
        # strength straight-set movement -> [work, (rest)] repeated `sets` times
        if strength and s.role == "active" and s.sets > 1:
            first = len(steps)
            add(s)
            if s.rest_s > 0:
                add(_rest_step_for(s.rest_s))
            add_repeat(first, s.sets)
        else:
            add(s)

    for block in workout.blocks:
        if isinstance(block, D.RepeatGroup):
            first = len(steps)
            for s in block.steps:
                add_movement(s)              # members may themselves be multi-set
            add_repeat(first, block.count)
        else:
            add_movement(block)
    return steps


def build_fit(workout: D.Workout) -> bytes:
    builder = FitFileBuilder(auto_define=True)

    fid = FileIdMessage()
    fid.type = FileType.WORKOUT
    fid.manufacturer = 255              # development / undefined
    fid.product = 0
    fid.serial_number = 0x434F524F      # "CORO"
    fid.time_created = round(datetime.now().timestamp() * 1000)
    builder.add(fid)

    steps = workout_to_fit_steps(workout)

    wkt = WorkoutMessage()
    wkt.workout_name = (workout.title or "COROS Workout")[:64]
    wkt.sport = SPORT_FIT.get(workout.sport, Sport.GENERIC)
    if workout.sport in STRENGTH_SPORTS:
        wkt.sub_sport = SubSport.STRENGTH_TRAINING
    wkt.num_valid_steps = len(steps)
    builder.add(wkt)

    for s in steps:
        builder.add(s)

    return builder.build().to_bytes()


def fetch_plan(plan_id, region):
    r = requests.get(DETAIL, params={"supportRestExercise": "1", "id": plan_id, "region": region},
                     headers=HDRS, timeout=25)
    r.raise_for_status()
    return r.json().get("data") or {}


def parse_plan_url(url):
    """Extract (plan_id, region) from a COROS share/schedule URL."""
    pid = re.search(r'planId=([0-9]+)', url or "")
    reg = re.search(r'region=([0-9]+)', url or "")
    return (pid.group(1) if pid else None, reg.group(1) if reg else "1")


def decode_plan_for(plan_id, region):
    dictionary = C.load_dictionary()
    tr = lambda k: (C.translate_key(k, dictionary) if k else "")
    return D.decode_plan(fetch_plan(plan_id, region), tr)


def _fit_filename(n, w):
    safe = "".join(c if c.isalnum() else "_" for c in w.title)[:30]
    return f"{n:03d}_{w.sport.lower()}_{safe}.fit"


def exportable(workouts):
    """Run/bike workouts with real steps (the FIT-exportable subset)."""
    return [w for w in workouts if w.sport in SPORT_FIT and w.blocks]


def workouts_to_zip(workouts):
    """Zip one .fit per exportable workout. Returns zip bytes (empty zip if none)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, w in enumerate(exportable(workouts), 1):
            z.writestr(_fit_filename(n, w), build_fit(w))
    buf.seek(0)
    return buf.getvalue()


def fit_zip_for_plan(plan_url):
    """End-to-end: COROS plan URL -> zip of Garmin .fit workout files."""
    plan_id, region = parse_plan_url(plan_url)
    if not plan_id:
        raise ValueError("Could not find a planId in the URL")
    plan = decode_plan_for(plan_id, region)
    workouts = exportable(plan.workouts)
    if not workouts:
        raise ValueError("No run/bike/strength workouts in this plan to export as .FIT")
    return workouts_to_zip(plan.workouts)


def main():
    ap = argparse.ArgumentParser(description="COROS run/bike/strength plan -> Garmin .FIT workouts")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--region", default="1")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "fit_out"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    plan = decode_plan_for(args.plan, args.region)
    workouts = exportable(plan.workouts)
    if args.limit:
        workouts = workouts[:args.limit]

    os.makedirs(args.out, exist_ok=True)
    print(f"Plan: {plan.title!r} — {len(workouts)} run/bike/strength workouts -> .FIT")
    for n, w in enumerate(workouts, 1):
        path = os.path.join(args.out, _fit_filename(n, w))
        with open(path, "wb") as f:
            f.write(build_fit(w))
    print(f"Wrote {len(workouts)} .fit files to {args.out}/")
    print("Sideload: copy to your watch's GARMIN/NewFiles/ folder over USB.")


if __name__ == "__main__":
    main()
