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
  `scrape_from_url`, so region works. Non-English output is now **feasible**
  (not blocked): `scripts/refresh_dictionary.py` can pull other locale bundles
  (`zh-CN/de-DE/fr-FR/es-ES/ja-JP` all exist) — see open item L1 in the session
  log. Updated 2026-06-12 (the earlier "out of scope until dictionaries exist"
  is stale — the dictionaries are fetchable).
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
- [x] §4: `.ZWO` export to production DONE 2026-06-12 (#26) — `coros_to_zwo.py`,
  driven by the shared decoder; run/bike, real %FTP power targets, pace/HR as
  FreeRide + note (no fake power); plan→zip / workout→file; `tests/test_zwo.py`.
  POC retired. Live intervals.icu upload = **no-go** (see session log below).
- [ ] §4 (still open): direct Garmin Connect upload (unofficial API — account-ban
  risk, superseded by `.ZWO`/intervals.icu), and swim/climbing **FIT** schemas
  (the calendar already renders swim/climb structure as of #25).

## Standing task
- [x] First full README rewrite done 2026-06-12 — readability + matches current
  deliverables (rich `.ics`, structured-export POC, researched Garmin, deferred
  strength/swim/tri).
- [ ] **Standing:** keep `README.md` in sync with deliverables — refresh on every
  deliverable change, not just the first time.

## Design (2026-06-12)
- [x] Redesigned index + preview to a minimal warm-orange theme (frontend only).
- [x] a11y: the white-on-`#ff9800` ~2:1 concern is **moot** — the orange theme was
  reverted to blue (`--primary-color: #2563eb`); white-on-`#2563eb` is ~5:1 (passes
  WCAG AA). Closed 2026-06-12.

## UX (2026-06-12)
- [x] Reverted the orange redesign (kept old blue design per preference).
- [x] Preview UX: collapsible week sections (week 1 open, rest collapsed) + Expand/Collapse all, animated inline workout-detail expand, sticky table + week headers.
- [x] Landing: loading state on submit + single-page transition (fetch + in-place swap to preview; progressive enhancement, form still works with JS off).

## Session 2026-06-12 — workout export + improvements (PRs #22–#26, all merged)
Shipped:
- [x] #22 — refreshed `coros_dictionary.json` from COROS's live locale bundle (+300 codes)
  + graceful title fallback (raw `W302xx` no longer leak); `scripts/refresh_dictionary.py`.
- [x] #23 — **standalone workout export**: paste a workout link (`programId=`) → one
  dated `.ics` event / one `.fit`. `decode_workout` wraps a `program/detail` payload as
  a one-program plan (shared decoder).
- [x] #24 — **CI** (GitHub Actions): `pytest` + `compileall` on push/PR, Python 3.10–3.13.
- [x] #25 — **swim/climb/tri render full set structure** in the calendar (`Workout.has_structure`
  tier; fixed a second hidden `is_rich` gate on the plan path).
- [x] #26 — **`.ZWO` export** (run/bike) — see §4 above.

Open (genuinely actionable):
- [ ] **W1: web `.ZWO` download button** — `.ZWO` is CLI-only; the web preview offers
  `.ics`+`.FIT` but not `.ZWO`. Trivial (mirror `/generate-fit`; no secrets — it's a file).
- [ ] **L1: locale / non-English output** — `--locale` flag + pull the matching dictionary
  via `refresh_dictionary.py` (zh/de/fr/es/ja bundles exist). Region already parsed.
- [ ] **swim/climbing `.FIT` schemas** — calendar renders them (#25); FIT does not (harder schema).
- [ ] **absolute pace/power value rendering** — only HR decoded to bpm; pace encoded oddly
  (e.g. `383386`), absolute power suppressed. Blocked on confirming the unit encoding. (low)

Parked by decision (revisit only with a reason):
- Live intervals.icu **upload** — no-go 2026-06-12 (account-free `.ZWO` file is enough;
  the live push is the upkeep magnet — API drift + secret handling for a narrow audience).
- Catalog browse/enumeration (A3) — cut (ToS exposure).
- Direct Garmin Connect upload — account-ban risk; superseded by `.ZWO`/intervals.icu.
- Climbing grades (`gradeSystem`/`onsightGradeOffset`) — niche; structure already renders.
