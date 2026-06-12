# Follow-ups / known issues

Running log of things found but deliberately deferred. Each entry: severity,
where it lives, what to do. Tick when fixed.

## From `/verify` of the rich `.ics` change (2026-06-12, branch `feat/unified-decoder`)

Verdict was PASS — rich run/bike detail works end-to-end at both the CLI and the
Flask web app. These are adjacent issues surfaced while verifying (mostly
pre-existing, not regressions from that change):

- [ ] **⚠️ Strength/exercise plans return 0 workouts with no message.**
  `scrape_from_url` skips entities that lack `exerciseBarChart`/`sport`
  (`convert_to_ics.py` ~line 129-131 `if not exercise_bar_chart and not sport: continue`),
  so strength/gym plans yield an empty result; the web app (`app.py` `index()`)
  then just bounces back to the form with no explanation.
  - *Pre-existing.* Real fix is rich strength support = **build-plan A2 (deferred)**.
  - *Quick interim:* when `scrape_from_url` returns 0 workouts, surface a clear
    message ("This plan type isn't supported yet — strength/gym plans coming soon")
    instead of a silent empty bounce.

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
- [ ] A2: strength/exercise-plan rich decode (sets/reps/weight/rest/form cues).
- [ ] §4 (research-gated): structured export to production (intervals.icu / .ZWO /
  Garmin FIT) — needs user sign-off per BUILD_PLAN §2/§8.1.
