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

Still open (lower severity):
- [ ] `/generate` accepts arbitrary `workouts_json` (hidden field, but POST-able): validate
  it's a list of dicts with `title`/`date_str` before building, to avoid 500s on crafted input.
- [ ] Render the actual absolute HR (bpm) / pace / power value (we currently suppress it);
  needs unit handling per `hrType` / `intensityDisplayUnit`.
- [ ] `_step_name` should truncate on encoded bytes + ASCII-fold `–`/`×` for older Garmin displays.
- [ ] Prod config: don't run `app.run(debug=True)`; move `secret_key` to an env var.
- [ ] `sportType: None` decodes to the literal sport `"None"` — default to "" / "Workout".

## Carried over from the build plan / reviews (not yet done)
See `BUILD_PLAN.md` for full context.
- [x] A4: date audit DONE 2026-06-12 — found + fixed a **real bug** (not in
  `calculate_plan_dates` but in `scrape_from_url`'s `dayNo→week` mapping:
  `((dayNo-1)//7)+1` shifted ~all workouts off their real dates; `dayNo` is an
  absolute 0-based index). Extracted `day_no_to_week_dow` + regression tests
  (tests/test_dates.py). Verified ~9/10 workouts were landing on wrong dates before.
- [ ] A4: region/i18n — `scrape_from_url` hardcodes `region="1"`; dictionary is
  single-locale. Decide whether to parameterize.
- [ ] A4: log dictionary misses (`translate_key` returns raw key on miss; ~109 of
  482 movements lack `_desc`).
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
