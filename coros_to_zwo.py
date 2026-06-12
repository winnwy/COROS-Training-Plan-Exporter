"""Export COROS run/bike workouts to Zwift `.ZWO` structured-workout files.

One `.zwo` per run/bike workout; a plan zips them. Reuses the shared decoder
(`coros_decode`) — one decoder, many exporters (`.ics`, `.FIT`, `.ZWO`).

`.ZWO` is power-as-FTP-fraction (cycling-native). COROS %-of-threshold **power**
targets map straight onto that fraction. For pace/HR targets (no power), we emit
`FreeRide` (duration only, no power prescription) plus a `<textevent>` carrying
the real target — so a pace workout is never silently misrepresented as power.

Scope: run/bike only (`.ZWO` has no swim/strength model). The live intervals.icu
upload is a separate, optional feature — this module produces files.

Usage:
    python coros_to_zwo.py --plan <id|url> [--region 1] [--out ./zwo_out]
    python coros_to_zwo.py --workout <id|url> [--out ./zwo_out]
"""
import argparse
import io
import os
import re
import sys
import zipfile
from xml.sax.saxutils import escape, quoteattr

sys.path.insert(0, os.path.dirname(__file__))
import coros_decode as D
import convert_to_ics as C
import requests

HDRS = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"}
PLAN_DETAIL = "https://teamapi.coros.com/training/plan/detail"
PROGRAM_DETAIL = "https://teamapi.coros.com/training/program/detail"

ZWO_SPORT = {"Run": "run", "Bike": "bike"}          # the only sports .ZWO models
_DEFAULT_SECS = 300                                  # open/unbounded step fallback
_RUN_PACE_S_PER_KM = 300                             # ~5:00/km to time a distance step


def _translator():
    dictionary = C.load_dictionary()
    return lambda k: (C.translate_key(k, dictionary) if k else "")


def fetch_plan(plan_id, region):
    r = requests.get(PLAN_DETAIL, params={"supportRestExercise": "1", "id": plan_id, "region": region},
                     headers=HDRS, timeout=25)
    r.raise_for_status()
    return r.json().get("data") or {}


def fetch_program(program_id, region):
    r = requests.get(PROGRAM_DETAIL, params={"id": program_id, "region": region},
                     headers=HDRS, timeout=25)
    r.raise_for_status()
    return r.json().get("data") or {}


def exportable(workouts):
    """Run/bike workouts with steps — the .ZWO-exportable subset."""
    return [w for w in workouts if w.sport in ZWO_SPORT and w.blocks]


def _flatten(workout):
    """Expand RepeatGroups into a flat ordered step list (ZWO has no generic
    N-step repeat; on/off intervals become repeated elements, like the .FIT path)."""
    steps = []
    for b in workout.blocks:
        if isinstance(b, D.RepeatGroup):
            for _ in range(max(b.count, 1)):
                steps.extend(b.steps)
        else:
            steps.append(b)
    return steps


def _seconds(step):
    if step.dur_kind == "time" and step.dur_value > 0:
        return step.dur_value
    if step.dur_kind == "distance" and step.dur_value > 0:
        # .ZWO is time-based; estimate from a ~5:00/km run pace (annotated in the note).
        return max(1, round(step.dur_value / 1000 * _RUN_PACE_S_PER_KM))
    return _DEFAULT_SECS


def _note(step):
    """Human label for the step's <textevent> — name + real target (e.g. pace),
    plus an 'est.' marker when the duration was inferred from a distance."""
    bits = [step.name or step.role.title()]
    t = step.target.human()
    if t:
        bits.append(f"@ {t}")
    if step.dur_kind == "distance" and step.dur_value:
        km = step.dur_value / 1000
        bits.append(f"({km:.2f} km, time est.)" if km >= 1 else f"({step.dur_value} m, time est.)")
    return " ".join(bits)


def _element(step):
    """One ZWO step element. Power FTP-fraction only for real power targets;
    everything else is FreeRide (honest — no fake power), detail in the note."""
    secs = _seconds(step)
    t = step.target
    if t.kind == "power" and t.pct_low:
        lo = round(t.pct_low / 100.0, 3)
        hi = round((t.pct_high or t.pct_low) / 100.0, 3)
        if step.role == "warmup":
            return f'<Warmup Duration="{secs}" PowerLow="{lo}" PowerHigh="{hi}"/>'
        if step.role == "cooldown":
            return f'<Cooldown Duration="{secs}" PowerLow="{lo}" PowerHigh="{hi}"/>'
        return f'<SteadyState Duration="{secs}" Power="{lo}"/>'
    return f'<FreeRide Duration="{secs}"/>'


def to_zwo(workout):
    """Render a decoded run/bike Workout as a .ZWO XML string."""
    sport = ZWO_SPORT[workout.sport]
    desc = (f"Converted from COROS ({workout.sport}). Power values are %-of-threshold "
            "fractions; pace/HR steps are FreeRide with the real target in the step note.")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<workout_file>",
        "  <author>COROS Training Plan Exporter</author>",
        f"  <name>{escape(workout.title or 'COROS Workout')}</name>",
        f"  <description>{escape(desc)}</description>",
        f"  <sportType>{sport}</sportType>",
        "  <workout>",
    ]
    for s in _flatten(workout):
        lines.append(f"    {_element(s)}")
        lines.append(f"    <textevent timeoffset=\"0\" message={quoteattr(_note(s))}/>")
    lines += ["  </workout>", "</workout_file>"]
    return "\n".join(lines) + "\n"


def _zwo_filename(n, w):
    safe = "".join(c if (c.isascii() and c.isalnum()) else "_" for c in (w.title or "workout")).strip("_")[:40]
    return f"{n:03d}_{w.sport.lower()}_{safe or 'workout'}.zwo"


def zwo_zip_for_plan(plan_url):
    """COROS plan URL -> zip of .zwo files (run/bike workouts)."""
    plan_id, region = _plan_id(plan_url)
    plan = D.decode_plan(fetch_plan(plan_id, region), _translator())
    workouts = exportable(plan.workouts)
    if not workouts:
        raise ValueError("No run/bike workouts in this plan to export as .ZWO "
                         "(swim/strength aren't supported by the .ZWO format — use the calendar).")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, w in enumerate(workouts, 1):
            z.writestr(_zwo_filename(n, w), to_zwo(w))
    buf.seek(0)
    return buf.getvalue()


def zwo_for_workout(url):
    """COROS workout URL -> (filename, .zwo bytes). Raises ValueError if the
    workout isn't run/bike or has no structured steps."""
    kind, workout_id, region = C.parse_coros_url(url)
    if kind != "workout":
        raise ValueError("That looks like a plan link — use --plan for .ZWO export.")
    w = D.decode_workout(fetch_program(workout_id, region), _translator())
    if w.sport not in ZWO_SPORT:
        raise ValueError(f"This {w.sport or 'kind of'} workout can't be exported as .ZWO "
                         f"(run/bike only) — use the calendar (.ics) export.")
    if not w.blocks:
        raise ValueError("This workout has no structured steps to export as .ZWO — "
                         "use the calendar (.ics) export.")
    return _zwo_filename(1, w)[4:], to_zwo(w)   # drop the "001_" prefix for a single file


def _plan_id(url):
    """Accept a planId URL or a bare id."""
    if re.fullmatch(r"[0-9]+", url or ""):
        return url, "1"
    kind, _id, region = C.parse_coros_url(url)
    if kind != "plan":
        raise ValueError("That looks like a workout link — use --workout for .ZWO export.")
    return _id, region


def main():
    ap = argparse.ArgumentParser(description="COROS run/bike plan or workout -> Zwift .ZWO files")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--plan", help="plan id or share URL (planId=...) -> zip of .zwo")
    src.add_argument("--workout", help="workout id or share URL (programId=...) -> one .zwo")
    ap.add_argument("--region", default="1")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "zwo_out"))
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    try:
        if args.workout:
            url = args.workout
            if re.fullmatch(r"[0-9]+", url):
                url = f"https://training.coros.com/workout-program?programId={url}&region={args.region}"
            filename, data = zwo_for_workout(url)
            path = os.path.join(args.out, filename)
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
            print(f"Wrote {path}")
        else:
            zip_bytes = zwo_zip_for_plan(args.plan if not re.fullmatch(r"[0-9]+", args.plan)
                                         else f"https://x?planId={args.plan}&region={args.region}")
            path = os.path.join(args.out, "coros_zwo_workouts.zip")
            with open(path, "wb") as f:
                f.write(zip_bytes)
            print(f"Wrote {path}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    print("Import the .zwo into Zwift, intervals.icu, or TrainingPeaks.")


if __name__ == "__main__":
    main()
