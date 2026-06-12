# POC — COROS → .ZWO → intervals.icu (structured-workout export, Route A)

Proof of concept for the **structured-workout** export path in
[`../docs/BUILD_PLAN.md`](../docs/BUILD_PLAN.md) §4a/§4b — distinct from the
existing `.ics` calendar exporter. It proves a COROS plan can be decoded into a
sport-agnostic step model and emitted as a real multi-step structured workout
that a sanctioned platform (intervals.icu) accepts and forwards to Garmin/Zwift.

## What it does
1. Fetches a plan from the public `teamapi.coros.com/training/plan/detail`.
2. Decodes each run/bike program's `exercises[]` into a normalized `Step`/`Workout`
   model (intensity role, duration kind/value, `%threshold` target low/high),
   **expanding interval groups** (`isGroup` + `sets`).
3. Emits one `.ZWO` per workout (power as FTP-fraction; original target type —
   HR/pace/power — preserved in `<textevent>` annotations).
4. Builds the intervals.icu `POST /events/bulk?upsert=true` payload, dated per day.

## Run
```bash
pip install requests icalendar          # or use a venv
# DRY RUN — writes .zwo files + prints the intervals.icu request it would send:
python coros_to_zwo.py --plan 459583119950004224 --start 2026-07-01

# REAL UPLOAD to intervals.icu:
INTERVALS_ICU_API_KEY=<key> INTERVALS_ICU_ATHLETE_ID=i12345 \
  python coros_to_zwo.py --plan 459583119950004224 --start 2026-07-01 --upload
```
`.zwo` files land in `poc/out/`. Get an API key at intervals.icu → Settings → Developer.

## Scope & caveats (POC only)
- **Run/bike only.** Strength/swim/triathlon are deferred (different schemas — see plan §4).
- `.ZWO` is power-centric; COROS HR/pace `%threshold` is emitted as the equivalent
  FTP-fraction with the real target type annotated, not silently misrepresented.
- Distance-based steps (no native ZWO duration) are time-estimated and annotated.
- Interval groups are expanded inline (valid ZWO) rather than using `<IntervalsT>`.

## Verified
Against `459583119950004224` (6-Week Threshold Cycling): decodes all programs,
expands the "Threshold" interval block correctly, and produces valid `.ZWO`.
