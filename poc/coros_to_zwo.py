#!/usr/bin/env python3
"""
POC — Route A from the build plan: COROS training plan -> normalized workout
model -> Zwift .ZWO structured workouts -> intervals.icu upload.

This is a proof of concept for the structured-workout export path (NOT the
.ics calendar exporter). It demonstrates that a COROS plan can be decoded into
a sport-agnostic step model and emitted as a real, multi-step structured
workout that a sanctioned platform (intervals.icu) accepts and forwards to
Garmin/Zwift.

Usage:
    python coros_to_zwo.py --plan 459583119950004224 [--region 1] [--out ./out]
    # add --upload to POST to intervals.icu (needs env creds):
    INTERVALS_ICU_API_KEY=... INTERVALS_ICU_ATHLETE_ID=i12345 \
        python coros_to_zwo.py --plan <id> --upload --start 2026-07-01

Without --upload it does a DRY RUN: writes .zwo files and prints the exact
intervals.icu request it *would* send.

Caveats (see docs/BUILD_PLAN.md §4):
- .ZWO targets are power as FTP-fraction. COROS %threshold maps to that fraction
  directly; HR/pace %threshold are emitted as the same fraction with the real
  target type recorded in a <textevent> so nothing is silently misrepresented.
- Distance-based steps (targetType 5) have no native ZWO duration; we estimate
  seconds from the program's duration when possible and annotate.
- Strength/swim/triathlon are out of scope for this POC (run/bike only).
"""
import argparse, base64, json, os, sys, datetime as dt
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

import requests

# Reuse the existing shortcode dictionary / translator.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import convert_to_ics as C

HDRS = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"}
DETAIL = "https://teamapi.coros.com/training/plan/detail"

# --- decode tables (from docs/coros_map/COROS_MAP.md §4) ---
SPORT = {1: "Run", 2: "Bike", 3: "Swim", 4: "Strength", 9: "Hybrid"}
INTENSITY = {1: "weight", 2: "HR", 3: "pace", 5: "swim", 7: "HR-range",
             8: "pace-range", 9: "power", 10: "climb"}
EX_INTENSITY = {1: "warmup", 2: "active", 3: "cooldown", 4: "rest"}


@dataclass
class Step:
    role: str                 # warmup | active | rest | cooldown
    name: str                 # decoded label, e.g. "Training"
    dur_kind: str             # time | distance | open
    dur_value: int            # seconds (time) or metres (distance)
    pct_low: float = 0.0      # %threshold fraction (0..1+), 0 if none
    pct_high: float = 0.0
    target_kind: str = ""     # HR | pace | power | swim | none
    note: str = ""


@dataclass
class Workout:
    week: int
    day_no: int
    sport: str
    title: str
    steps: list = field(default_factory=list)


def translate(k):
    v = C.translate_key(k, C.load_dictionary())
    return v if v != k else k


def fetch_plan(plan_id, region):
    r = requests.get(DETAIL, params={"supportRestExercise": "1", "id": plan_id, "region": region},
                     headers=HDRS, timeout=25)
    r.raise_for_status()
    return r.json().get("data") or {}


def decode_step(ex):
    role = EX_INTENSITY.get(ex.get("exerciseType"), "active")
    tt = ex.get("targetType")
    tv = ex.get("targetValue", 0) or 0
    if tt == 2:
        dur_kind, dur_value = "time", int(tv)              # seconds
    elif tt == 5:
        dur_kind, dur_value = "distance", int(tv) // 100    # cm -> m
    else:
        dur_kind, dur_value = "open", 0
    it = ex.get("intensityType", 0)
    pct_low = pct_high = 0.0
    if ex.get("isIntensityPercent") and ex.get("intensityPercent"):
        pct_low = ex["intensityPercent"] / 1000.0 / 100.0   # 80000 -> 0.80
        ext = ex.get("intensityPercentExtend") or ex["intensityPercent"]
        pct_high = ext / 1000.0 / 100.0
    return Step(
        role=role,
        name=translate(ex.get("name", "")) or role.title(),
        dur_kind=dur_kind, dur_value=dur_value,
        pct_low=pct_low, pct_high=pct_high or pct_low,
        target_kind=INTENSITY.get(it, "none"),
    )


def decode_workouts(data):
    """Return list[Workout] for run/bike programs, with interval groups expanded."""
    out = []
    week_len = 7
    for idx, prog in enumerate(data.get("programs", [])):
        sport = SPORT.get(prog.get("sportType"), str(prog.get("sportType")))
        if sport not in ("Run", "Bike"):
            continue  # POC scope
        exercises = prog.get("exercises", []) or []
        steps, i = [], 0
        # group consecutive steps sharing a non-zero groupId, repeated `sets` times
        group_reps = {}
        for ex in exercises:
            if ex.get("isGroup"):
                group_reps[ex.get("groupId")] = ex.get("sets", 1) or 1
        seen_group = set()
        for ex in exercises:
            if ex.get("isGroup"):
                continue  # header, not a real step
            gid = ex.get("groupId")
            if gid and gid not in ("0", 0):
                # collect the whole group once, expand by reps
                if gid in seen_group:
                    continue
                seen_group.add(gid)
                members = [e for e in exercises if e.get("groupId") == gid and not e.get("isGroup")]
                reps = group_reps.get(gid, 1)
                for _ in range(reps):
                    for m in members:
                        steps.append(decode_step(m))
            else:
                steps.append(decode_step(ex))
        if steps:
            out.append(Workout(week=idx // week_len + 1, day_no=idx + 1,
                               sport=sport, title=translate(prog.get("name", "")) or f"Workout {idx+1}",
                               steps=steps))
    return out


# ---------------- .ZWO emitter ----------------
def _dur_seconds(step, fallback=300):
    if step.dur_kind == "time" and step.dur_value > 0:
        return step.dur_value
    if step.dur_kind == "distance" and step.dur_value > 0:
        # rough estimate: assume 5:00/km running pace if no time given
        return int(step.dur_value / 1000 * 300)
    return fallback


def _power(step, default=0.6):
    lo = step.pct_low or default
    hi = step.pct_high or lo
    return round(lo, 3), round(hi, 3)


def to_zwo(w: Workout) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<workout_file>",
             "  <author>coros_to_zwo POC</author>",
             f"  <name>{escape(w.title)}</name>",
             f"  <description>Converted from COROS ({w.sport}). Power values are %threshold "
             "fractions; original target types annotated per step.</description>",
             f"  <sportType>{'run' if w.sport=='Run' else 'bike'}</sportType>",
             "  <workout>"]
    for s in w.steps:
        secs = _dur_seconds(s)
        lo, hi = _power(s)
        tag = {"warmup": "Warmup", "cooldown": "Cooldown"}.get(s.role, "SteadyState")
        ann = f"{s.name} [{s.target_kind} {int(s.pct_low*100)}-{int(s.pct_high*100)}%]" if s.pct_low else s.name
        if tag in ("Warmup", "Cooldown"):
            el = f'    <{tag} Duration="{secs}" PowerLow="{lo}" PowerHigh="{hi}"/>'
        else:
            el = f'    <SteadyState Duration="{secs}" Power="{lo}"/>'
        lines.append(el)
        lines.append(f'    <textevent timeoffset="0" message="{escape(ann)}"/>')
    lines += ["  </workout>", "</workout_file>"]
    return "\n".join(lines)


# ---------------- intervals.icu upload (Route A sink) ----------------
def intervals_payload(w: Workout, zwo: str, date: str):
    return {
        "category": "WORKOUT",
        "start_date_local": f"{date}T00:00:00",
        "type": w.sport,                       # "Run" / "Ride"-ish; intervals maps it
        "name": w.title,
        "file_contents": zwo,                  # ZWO can be sent unencoded
        "filename": "workout.zwo",
    }


def upload_intervals(payloads, dry_run=True):
    key = os.environ.get("INTERVALS_ICU_API_KEY")
    athlete = os.environ.get("INTERVALS_ICU_ATHLETE_ID")
    url = f"https://intervals.icu/api/v1/athlete/{athlete}/events/bulk?upsert=true"
    if dry_run or not (key and athlete):
        print(f"\n[DRY RUN] would POST {len(payloads)} events to:\n  {url}")
        print("  auth: HTTP Basic ('API_KEY', <key>)")
        print("  sample event:")
        sample = dict(payloads[0]); sample["file_contents"] = sample["file_contents"][:120] + "...(truncated)"
        print("  " + json.dumps(sample, indent=2).replace("\n", "\n  "))
        if not (key and athlete):
            print("\n  Set INTERVALS_ICU_API_KEY and INTERVALS_ICU_ATHLETE_ID + --upload to send for real.")
        return None
    resp = requests.post(url, json=payloads, auth=("API_KEY", key), timeout=30)
    print(f"\n[UPLOAD] POST {url} -> {resp.status_code}")
    print("  " + resp.text[:400])
    return resp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--region", default="1")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out"))
    ap.add_argument("--start", default=None, help="start date YYYY-MM-DD for scheduling (default: today)")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="cap number of workouts (0=all)")
    args = ap.parse_args()

    data = fetch_plan(args.plan, args.region)
    print(f"Plan: {translate(data.get('name',''))!r}  ({len(data.get('programs',[]))} programs)")
    workouts = decode_workouts(data)
    if args.limit:
        workouts = workouts[:args.limit]
    print(f"Decoded {len(workouts)} run/bike workouts into the normalized model.")

    os.makedirs(args.out, exist_ok=True)
    start = dt.date.fromisoformat(args.start) if args.start else dt.date.today()
    payloads = []
    for n, w in enumerate(workouts):
        zwo = to_zwo(w)
        fn = os.path.join(args.out, f"w{w.week:02d}_d{w.day_no:03d}_{w.sport.lower()}.zwo")
        with open(fn, "w") as f:
            f.write(zwo)
        date = (start + dt.timedelta(days=w.day_no - 1)).isoformat()
        payloads.append(intervals_payload(w, zwo, date))

    # show one decoded workout so the pipeline is visible
    if workouts:
        w = workouts[0]
        print(f"\n--- sample normalized workout: {w.title!r} ({w.sport}) ---")
        for s in w.steps[:8]:
            tgt = f"{s.target_kind} {int(s.pct_low*100)}-{int(s.pct_high*100)}%" if s.pct_low else "(no target)"
            print(f"  {s.role:8} {s.dur_kind}:{s.dur_value:<6} {tgt:18} {s.name}")
        if len(w.steps) > 8:
            print(f"  ... (+{len(w.steps)-8} more steps)")
        print(f"\n.zwo files written to: {args.out}/  ({len(payloads)} files)")

    upload_intervals(payloads, dry_run=not args.upload)


if __name__ == "__main__":
    main()
