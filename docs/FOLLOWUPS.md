# Follow-ups / known issues

Running log of things found but deliberately deferred. Each entry: severity,
where it lives, what to do. Tick when fixed.

## From `/verify` of the rich `.ics` change (2026-06-12, branch `feat/unified-decoder`)

Verdict was PASS — rich run/bike detail works end-to-end at both the CLI and the
Flask web app. These are adjacent issues surfaced while verifying (mostly
pre-existing, not regressions from that change):

- [ ] **⚠️ Strength/exercise plans return 0 workouts with no message.**
  `scrape_from_url` skips entities that lack `exerciseBarChart`/`sport`
  ~~(`convert_to_ics.py` ... `if not exercise_bar_chart and not sport: continue`)~~
  - [x] **FIXED (A2, 2026-06-12):** the skip now builds from the decoder when a
    program has rich blocks. Strength plans render full detail (sets×reps @ weight,
    rest, bodyweight); swim/tri/climb produce overview-level events instead of empty.
    A genuine 0-workout case is now rare, so the "not supported yet" message is moot.

- [x] **FIXED 2026-06-12: CLI `--start YYYY-MM-DD` / `--date` flag added** (bypasses
  the interactive prompt; validated up front; logic extracted to `resolve_start_date`
  + tested). No longer hangs with no TTY.

### Verified good (no action — recorded so we don't re-check)
- Bad/garbage `planId` and malformed URLs return the index page gracefully (no 500).
- RFC 5545 line folding holds with multibyte glyphs (`—`, `×`): 0 raw lines >75 octets.
- Run/bike, HR + pace, single targets + ranges, intervals (`N× (...)`), and the coach
  overview all render correctly through both the CLI and the web download.

## Code review (2026-06-12, 3 parallel agents)
Fixed in the same pass:
- [x] Decoder rendered a misleading bare `@ HR` for absolute (non-%) HR/pace/power
  targets → `Target.human()` now returns "" for value-less targets (regression test added).
- [x] FIT: sets-expansion now also runs for movements inside a RepeatGroup (defensive;
  not present in current COROS data but correct).
- [x] `requests.get` in `scrape_from_url` had no timeout → added `timeout=25`.
- [x] `dayNo: None` would crash the scrape → guarded (`entity.get('dayNo') or 0`).
- [x] Web error responses leaked `str(e)` → generic messages, traceback logged server-side.

Second pass (all fixed 2026-06-12):
- [x] `/generate` now validates `workouts_json` is a list of dicts with `title` and a
  parseable `date_str` (400 on bad input) — `tests/test_app.py`.
- [x] Absolute **HR** now renders as bpm (e.g. `@ 102–127 bpm`). Pace/power absolute
  values remain suppressed (encoding/unit not confidently decodable — still open below).
- [x] `_step_name` truncates on UTF-8 bytes + ASCII-folds `–`/`×`/etc. for older Garmins.
- [x] Prod config: `debug` off unless `FLASK_DEBUG=1`; `secret_key` from `SECRET_KEY` env.
- [x] `sportType: None` now decodes to `""` (not the literal `"None"`).
- [x] `Target.is_range` returns a real bool.

Still open (low):
- [ ] Render absolute **pace/power** values (only HR was confidently decodable; pace is
  encoded oddly, e.g. 383386). Needs unit confirmation before rendering.

## Carried over from the build plan / reviews (not yet done)
See `BUILD_PLAN.md` for full context.
- [x] A4: date audit DONE 2026-06-12 — found + fixed a **real bug** (not in
  `calculate_plan_dates` but in `scrape_from_url`'s `dayNo→week` mapping:
  `((dayNo-1)//7)+1` shifted ~all workouts off their real dates; `dayNo` is an
  absolute 0-based index). Extracted `day_no_to_week_dow` + regression tests
  (tests/test_dates.py). Verified ~9/10 workouts were landing on wrong dates before.
- [~] A4: region/i18n — region IS already parsed from the plan URL by
  `scrape_from_url` (the `region=1` is only the default when absent), so region works.
  True i18n (non-English output) needs additional locale dictionaries we don't have —
  **out of scope** until those exist. Closing the region part.
- [~] A4: dictionary-miss logging — decided **won't do** for now: low-value telemetry,
  and real movements have ~98% name / 93% `_desc` coverage; genuine misses already
  degrade gracefully (raw code shown, never a crash). Revisit if coverage gaps surface.
- [x] A2: strength/exercise-plan rich decode — DONE 2026-06-12 (sets×reps @ weight,
  holds, rest, bodyweight; supersets via groups; `part` decodable but omitted with
  muscle/equipment per coverage findings). Form cues not shown inline (length).
- [x] §4: Garmin `.FIT` export (run/bike) DONE 2026-06-12 — `coros_to_fit.py`,
  reuses the shared decoder; durations + interval repeats exact, targets carried
  in step names; tests/test_fit.py. Sideload via GARMIN/NewFiles. Strength/swim FIT
  (different schema) and direct Garmin Connect upload still open.
- [x] Strength `.FIT` DONE 2026-06-12 — sets expand to repeat blocks (work+rest
  ×sets), reps via REPS duration, sport TRAINING / sub-sport STRENGTH_TRAINING,
  weight in step name. Also served by the web /generate-fit route.
- [ ] §4 (still open): `.ZWO`/intervals.icu to production (POC exists), direct
  Garmin Connect upload (unofficial API), and swim/climbing FIT schemas.

## Standing task
- [x] First full README rewrite done 2026-06-12 — readability + matches current
  deliverables (rich `.ics`, structured-export POC, researched Garmin, deferred
  strength/swim/tri).
- [ ] **Standing:** keep `README.md` in sync with deliverables — refresh on every
  deliverable change, not just the first time.

## Design (2026-06-12)
- [x] Redesigned index + preview to a minimal warm-orange theme (frontend only).
- [ ] a11y: white text on #ff9800 buttons is ~2:1 (below WCAG AA). Kept per chosen brand color; fix = dark text on the orange button if AA is required.
