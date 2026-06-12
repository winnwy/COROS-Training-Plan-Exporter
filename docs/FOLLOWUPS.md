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

- [ ] **⚠️ CLI blocks on an interactive start-date prompt; no flag for non-interactive use.**
  `convert_to_ics.py` `main()` prompts on stdin for the start date; with no TTY
  (background/CI/automation) it hangs (observed during verify — a backgrounded run
  wedged here). Add a `--start YYYY-MM-DD` / `--date` flag that bypasses the prompt.

### Verified good (no action — recorded so we don't re-check)
- Bad/garbage `planId` and malformed URLs return the index page gracefully (no 500).
- RFC 5545 line folding holds with multibyte glyphs (`—`, `×`): 0 raw lines >75 octets.
- Run/bike, HR + pace, single targets + ranges, intervals (`N× (...)`), and the coach
  overview all render correctly through both the CLI and the web download.

## Carried over from the build plan / reviews (not yet done)
See `BUILD_PLAN.md` for full context.
- [ ] A4: audit `calculate_plan_dates` (`convert_to_ics.py` ~366-435) — verify it
  doesn't shift workouts when the plan's first day isn't day 0; add a fixture test.
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
