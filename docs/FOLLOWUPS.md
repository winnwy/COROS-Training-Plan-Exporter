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
- [ ] §4 (research-gated): structured export to production (intervals.icu / .ZWO /
  Garmin FIT) — needs user sign-off per BUILD_PLAN §2/§8.1.

## Standing task
- [x] First full README rewrite done 2026-06-12 — readability + matches current
  deliverables (rich `.ics`, structured-export POC, researched Garmin, deferred
  strength/swim/tri).
- [ ] **Standing:** keep `README.md` in sync with deliverables — refresh on every
  deliverable change, not just the first time.
