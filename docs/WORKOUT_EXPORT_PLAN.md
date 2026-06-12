# Standalone Workout Export — Implementation Plan

_Plan date 2026-06-12. Grounded in [`WORKOUT_EXPORT_RESEARCH.md`](WORKOUT_EXPORT_RESEARCH.md). Status: proposed, pre-review._

## Goal & non-goals

**Goal:** let a user paste a single COROS **workout** link (`training.coros.com/workout-program?programId=<ID>&region=<r>`) and get the same outputs the plan flow gives — a `.ics` calendar event and a Garmin `.FIT` — reusing the shared decoder.

**Non-goals (this change):** catalog enumeration/browse (deferred, `BUILD_PLAN.md §A3`); rich climbing/bouldering decode (stays overview-only); swim-specific pool metadata; intervals.icu / `.ZWO`. No change to the existing plan flow's behavior.

## Design

A workout payload is a single plan-`program` minus the schedule wrapper (no `entities[]`, no dates). So:
- **Fetch** `program/detail` instead of `plan/detail`.
- **Decode** by wrapping the workout as a one-program synthetic plan and reusing `decode_plan` → one `Workout`.
- **Render** a single, undated event (`.ics`) / single file (`.FIT`). No `calculate_plan_dates`.

The existing plan code paths are untouched; workout support is added alongside.

## Work items (ordered)

### W1 — Decoder: `decode_workout()` + sport/title robustness  (`coros_decode.py`)
- Add `decode_workout(data, translate) -> Workout`: wrap as `{"name": data.get("name"), "region": data.get("region",1), "programs": [data]}` and call `decode_plan`, returning `plan.workouts[0]`. (Single source of truth; no duplicate decode logic.)
- Extend `SPORT` map with **verified codes only** `7: "Climb"` (confirmed live). **[outside-voice]** Do NOT add `5`/`6`/`8` on a guess — research only says "trail/track-ish"; a wrong label is worse than a numeric fallback. Add each only when a real fixture confirms it. Keep `7` **out** of `RICH_SPORTS` (overview-only, like swim).
- Add a title fallback in `decode_plan`. **[D3 — review]** Detect a dictionary miss by **equality on the raw key**, not a regex: `name_key = prog.get("name",""); title = translate(name_key)`; if `not title or title == name_key` → `title = f"{sport} Workout"` (falling back to the existing `f"Workout {idx+1}"` only when `sport` is unknown/empty). Exact, can't misfire on a legit title. Shared path → both plan and workout decode benefit. **Regression-sensitive: this modifies live plan behavior — see W6 regression test.**

### W2 — Dictionary refresh  (`scripts/refresh_dictionary.py` + regenerated `coros_dictionary.json`)
- New script: fetch `https://static.coros.com/locale/coros-traininghub-v2/en-US.prod.js`, strip `window.en_US=` prefix + trailing `;`, `json.loads`, write `coros_dictionary.json` (sorted keys, UTF-8). Print added/removed counts.
- Run it once to commit the refreshed bundle (7078 entries; +300, −0 vs current). Verify the 26 new `W` codes resolve.
- Guard: only overwrite if parse yields a dict with ≥ current entry count (don't clobber on a bad fetch).

### W3 — ICS: workout input path  (`convert_to_ics.py`)
- Add `parse_coros_url(url) -> (kind, id, region)` where `kind ∈ {"plan","workout"}`. **[D1 — review: cut bare-ID]** `programId=` → `("workout", id, region)`; `planId=` → `("plan", id, region)`; **anything else (bare number, garbage) → raise/return a clear "paste the full COROS link (it should contain planId= or workoutId=/programId=)" error.** No ambiguous fallback double-fetch. Region defaults to `1`.
- Add `scrape_workout_from_url(url)`: fetch `program/detail`, `decode_workout`, reuse `coros_decode.format_description(w, include_summary=False)` for the body. **[outside-voice]** `include_summary=False` is required — `create_ics_file` prints its own Distance/Duration/TL (lines 520–528); defaulting to `True` would duplicate those lines (same reason the plan path passes `False` at line 299). Return a **single** workout dict in the shape `create_ics_file` consumes, carrying `week=1`, `date_str`/`weekday_name`, and **`date_obj` = chosen start date (default today)**.
- **[outside-voice — date divergence]** Do NOT let the workout flow run through `calculate_plan_dates` — it sorts by `(week, day_of_week)` and forces a missing `day_of_week` to Monday (lines 430–433), silently shifting "today" → "next Monday" and diverging from the CLI. The workout dict already carries `date_obj`; the web path (W5) must skip `calculate_plan_dates` for workouts, and `create_ics_file` already honors a pre-set `date_obj` (line 493).
- `main()`: route via `parse_coros_url`; keep `--url` working for both. CLI writes `coros_workout.ics` for workouts (date = today, no alignment).

### W4 — FIT: workout input path  (`coros_to_fit.py`)
- Generalize fetch: add `fetch_program(program_id, region)` hitting `program/detail`; `decode_workout` → one `Workout`.
- Add `fit_for_workout(url) -> (filename, bytes)` and a CLI `--workout <ID|url>` (mutually exclusive with `--plan`). **[D2 — review]** Single workout → **bare `.fit`** (reuse `build_fit`, which already returns raw bytes), NOT a zip. Plans keep `.zip`.
- **[A2 — review]** If the workout can't be FIT-exported, **raise `ValueError`** (not a bare `Exception`) with a clear message — **[outside-voice]** `/generate-fit` only surfaces `ValueError` to the user (app.py:133); anything else shows the generic "Sorry, we couldn't build". Two cases to cover, both → `ValueError`:
  1. sport not in `SPORT_FIT` (swim/climb): "This {sport} workout can't be exported as .FIT yet — use the calendar (.ics) export".
  2. **[outside-voice]** FIT sport but **no decoded blocks** (e.g. an overview-only recovery run — `exportable()` needs `w.sport in SPORT_FIT AND w.blocks`, line 203): "This workout has no structured steps to put on the watch — use the calendar (.ics) export".
  The `.ics` path must still produce a (overview-level) event in both cases.
- Reuse `build_fit` / `workout_to_fit_steps` unchanged.

### W5 — Web app  (`app.py`, `templates/index.html`, `templates/preview.html`)
- `index()`: detect plan vs workout via `parse_coros_url`. Workout → one-row preview. **Verified in review: `preview.html` groups by `week` (line 133) and renders `date_str`/`weekday_name`/`title`/`description`, so a single dict with `week=1` + date fields renders as-is — reuse the template, no fork.** **[outside-voice] For a workout, skip the `calculate_plan_dates(...)` call (app.py:44) and pass the workout dict (which already has `date_obj`/`date_str`/`weekday_name`) straight through** — otherwise the date shifts to Monday. (Optional polish: hide the "Total Weeks" tile for single workouts.)
- `/generate-fit` (reads hidden field `plan_url`, app.py:121): branch on URL content — workout URL → `fit_for_workout` → send bare `coros_workout.fit`; plan URL → existing `.zip` path. The `ValueError` handler (app.py:133) already surfaces the A2 message.
- Minimal copy tweak: the paste box hint mentions "plan or workout link".

### W6 — Tests  (`tests/`)  _(expanded in review — was missing 4 paths)_
- Commit **raw** `program/detail` fixtures: `workout_run_intervals.json`, `workout_strength_sets.json`, `workout_swim.json`, and `workout_missing_title.json` (W-code not in dict) for the W1 fallback.
- `test_decode.py`:
  - `decode_workout` yields correct blocks/targets per fixture (run groups/pace %, strength sets×reps@weight). **[D5 — outside-voice]** For swim, assert `decode_workout` populates `w.blocks` correctly BUT `format_description(w)` returns **overview-only** (swim ∉ `RICH_SPORTS`) — do NOT assert "6×100m" appears in the rendered body. (Documents the known limitation; rich swim is deferred.)
  - Title fallback: missing-title fixture → `"<Sport> Workout"`.
  - **[CRITICAL — REGRESSION, iron rule]** existing-plan decode is unchanged: a plan fixture whose program names **do** resolve keeps its real titles (the equality-fallback must NOT clobber resolvable titles). Guards the shared-path change.
- `test_parse_url.py` (or in `test_decode`): `parse_coros_url` — `programId=` → workout, `planId=` → plan (guard existing flow), bare/garbage → error. **[D1]**
- `test_fit.py`: a run/strength workout fixture builds a valid FIT (num_valid_steps, repeat indices); **[A2 — outside-voice]** assert a swim/climb workout AND a FIT-sport-but-no-blocks workout each raise `ValueError` (assert the exception **type**, since `/generate-fit` only surfaces `ValueError`).
- `test_refresh_dict.py`: `refresh_dictionary` parses a small `window.en_US={...}` sample blob; the shrink/bad-fetch guard refuses to overwrite. **[W2 guard]**
- `test_app.py`: a workout URL (mocked fetch) renders preview (one row) and `/generate-fit` returns a bare `.fit`.
- Keep fixtures offline (mock `requests.get`), matching the existing fixture style.

### W7 — Docs  (`README.md`)
- Per the standing README-sync habit: document workout export alongside plan export (input URL, what you get, CLI `--workout`). Update the Status table.

## Sequencing — two PRs  **[D6 — outside-voice]**
The title-fallback + dict refresh fixes raw `W302xx` titles for **existing plan exports too** (a live shipped bug), so it ships first, independently of the unproven workout feature.

- **PR1 — "Fix raw shortcode titles + refresh dictionary"** (user-facing fix for today's plan users):
  W1 (title fallback only — equality detection + `SPORT` 7) + W2 (refresh script + regenerated dict) + the W6 **plan-title regression test** + the title-fallback test. Independently shippable and revertable. Update `README`/Status if a deliverable line changes.
- **PR2 — "Standalone workout export"** (builds on PR1):
  W1 (`decode_workout`) + W3 + W4 + W5 + remaining W6 tests + W7 docs.
  Internal order: W1 → (W3 ‖ W4) → W5; tests alongside each.

## Risks / mitigations
- **API/locale drift** → raw fixtures (W6) pin decode offline; refresh script (W2) re-pulls on demand; title fallback (W1) degrades gracefully.
- **`preview.html`** → resolved in review: it groups by `week` (line 133), so a single `week=1` row renders without forking the template.
- **Input ambiguity** → resolved by D1: URL-only, no bare-ID fallback. A `programId=` vs `planId=` URL is self-identifying (one fetch).
- **ToS** → unchanged; user's own pasted item only, no enumeration (`BUILD_PLAN.md §6`).

## Acceptance
- Paste a workout link in the web app → preview → download `.ics` (one correct event) and a **bare `.fit`** (one correct file, no unzip).
- CLI: `convert_to_ics.py --url <workout-url>` and `coros_to_fit.py --workout <ID>` both work.
- `python -m pytest tests/` green, including new workout fixtures + the plan-title regression test.
- Refreshed dictionary resolves the previously-missing `W` codes; titles never render as raw codes (fallback covers any future miss).

## What already exists (reused, not rebuilt)
- `coros_decode.decode_plan` — decodes the workout payload unchanged (verified live). `decode_workout` is a thin wrapper.
- `coros_decode.format_description` — renders the `.ics` body; reused for workouts.
- `coros_to_fit.build_fit` / `workout_to_fit_steps` — FIT generation; reused unchanged.
- `convert_to_ics.create_ics_file`, `translate_key`, `_DICTIONARY_CACHE` — reused.
- `templates/preview.html` — reused as-is (groups by `week`; a `week=1` single row renders).
- `app.py` routes `/`, `/generate`, `/generate-fit` — extended, not duplicated.

## NOT in scope (deferred, with rationale)
- **Bare-ID input** — cut (D1); require a URL. Re-add only if users ask.
- **Catalog browse / enumeration** — deferred (`BUILD_PLAN.md §A3`, ToS exposure).
- **Rich climbing/bouldering decode** (`gradeSystem`/`onsightGradeOffset`) — overview-only, like swim. Niche.
- **Swim-specific FIT schema** (pool length, strokes) — not built; swim stays `.ics`-only.
- **intervals.icu / `.ZWO`** — separate research track (`BUILD_PLAN.md §4`).
- **Runtime/auto dictionary refresh** — manual script only; live-fetch fallback is optional future work.
- **Locale parameterization** — en-US only this PR (codes are locale-keyed; non-US deferred).

## Failure modes (per new codepath)
| Codepath | Realistic failure | Test? | Error handling | User sees |
|---|---|---|---|---|
| `program/detail` fetch | COROS API down / 5xx / schema drift | mock | try/except → message | "couldn't read that workout" (not a stack trace) |
| `parse_coros_url` | bare/garbage input | yes (D1) | explicit raise | "paste the full COROS link" |
| `decode_workout` | unmapped sport (climb/swim) | yes | overview-only render | event with overview, no rich steps |
| `fit_for_workout` | non-FIT sport (swim/climb) | yes (A2) | `ValueError` | "use the calendar export" |
| `fit_for_workout` | FIT sport, **no blocks** (recovery run) | yes (A2) | `ValueError` | "no structured steps — use calendar" |
| web date path | `calculate_plan_dates` shifts workout to Monday | covered | skip alignment for workouts | event on the right day (today) |
| title fallback | resolvable title clobbered | **regression test** | equality guard | real title preserved |
| `refresh_dictionary` | bad/short remote fetch | yes | shrink guard, no overwrite | committed dict untouched |

No failure mode is both untested **and** silent → no critical gaps.

## Worktree parallelization
| Step | Modules | Depends on |
|---|---|---|
| W1 decoder | `coros_decode.py` | — |
| W2 dict | `scripts/`, `coros_dictionary.json` | — |
| W3 ics | `convert_to_ics.py` | W1 |
| W4 fit | `coros_to_fit.py` | W1 |
| W5 web | `app.py`, `templates/` | W3, W4 |

Lane A: W1 → (W3 ‖ W4) → W5. Lane B: W2 (independent). **Launch W1 and W2 in parallel; W3/W4 are parallel after W1 (different modules, no shared files); W5 last.** W6 tests land with each step; W7 README last.

## Implementation Tasks
Synthesized from review findings. Checkbox as you ship.

- [ ] **T1 (P1, human: ~1h / CC: ~10min)** — coros_decode — add `decode_workout` + extend `SPORT` (5/6/7/8) + equality title-fallback
  - Surfaced by: Architecture + D3
  - Files: `coros_decode.py`
  - Verify: `pytest tests/test_decode.py`
- [ ] **T2 (P1, human: ~45min / CC: ~8min)** — scripts — `refresh_dictionary.py` + regenerate `coros_dictionary.json` (shrink guard)
  - Surfaced by: Research §3 / W2
  - Files: `scripts/refresh_dictionary.py`, `coros_dictionary.json`
  - Verify: `pytest tests/test_refresh_dict.py`; W-codes resolve
- [ ] **T3 (P1, human: ~1.5h / CC: ~12min)** — convert_to_ics — `parse_coros_url` (URL-only, D1) + `scrape_workout_from_url` + CLI route
  - Surfaced by: D1, Test review
  - Files: `convert_to_ics.py`
  - Verify: `pytest tests/test_parse_url.py tests/test_app.py`
- [ ] **T4 (P1, human: ~1h / CC: ~10min)** — coros_to_fit — `fetch_program` + `fit_for_workout` (bare .fit, D2) + non-FIT-sport message (A2) + `--workout`
  - Surfaced by: D2, A2
  - Files: `coros_to_fit.py`
  - Verify: `pytest tests/test_fit.py`
- [ ] **T5 (P2, human: ~1h / CC: ~10min)** — app/templates — workout routing in `index()` + `/generate-fit` branch; paste-box copy
  - Surfaced by: Architecture
  - Files: `app.py`, `templates/index.html`
  - Verify: `pytest tests/test_app.py`
- [ ] **T6 (P1, human: ~2h / CC: ~15min)** — tests — fixtures + decode/parse/fit/refresh/app tests + **plan-title regression**
  - Surfaced by: Test review (4 gaps + iron-rule regression)
  - Files: `tests/`
  - Verify: `python -m pytest tests/`
- [ ] **T7 (P3, human: ~30min / CC: ~5min)** — README — document workout export alongside plans
  - Surfaced by: README-sync habit
  - Files: `README.md`
  - Verify: manual read

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | not run (optional) |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 4 issues raised + 4 test gaps + 1 regression; all resolved into plan |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | not run (no real UI surface beyond a copy tweak) |
| Outside Voice | Claude subagent | Independent 2nd opinion | 1 | HAS-REAL-GAPS → resolved | 5 real gaps found; all folded into plan |

**Decisions locked:** D1 cut bare-ID (URL-only) · D2 bare `.fit` for single workout · D3 equality-based title-miss detection · D5 swim/climb overview-only (docs+test corrected) · D6 split into PR1 (dict/title fix) + PR2 (workout export) · A2 graceful non-FIT + `.ics` still works.
**CROSS-MODEL:** outside voice (no review context) caught 5 gaps the eng review missed — all confirmed against code and folded in:
- swim `.ics` is overview-only (RICH_SPORTS excludes swim) → D5 corrects docs+test; A2 wording softened.
- web-vs-CLI date divergence (`calculate_plan_dates` forces Monday) → workout path skips alignment (W3/W5).
- `include_summary` would duplicate Distance/Duration → workout passes `include_summary=False` (W3).
- FIT-sport-but-no-blocks (recovery run) unhandled → second A2 `ValueError` case (W4).
- A2 message must be `ValueError` to surface in `/generate-fit` → specified (W4); `SPORT` 5/6 guess dropped (verified 7 only).
Rejected: "no demand signal" — the tool owner explicitly requested workout export.
**UNRESOLVED:** none.
**Critical gaps:** none (every failure mode is tested or non-silent; title-fallback regression test mandated, iron rule).
**VERDICT:** ENG CLEARED (post outside-voice) — ready to implement. Ship PR1 (dict/title fix) first, then PR2 (workout export).
