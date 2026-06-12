# Improvements Plan — CI, Rich Swim, intervals.icu

_Plan date 2026-06-12. Three features, built in this order. Grounded in `BUILD_PLAN.md §4/§6`, `WORKOUT_EXPORT_*`. Each ships as its own PR._

## Feature 1 — CI (GitHub Actions)  [foundational, do first]

**Problem:** No CI. 69 pytest tests exist but nothing runs them on push/PR — both recent PRs were verified only by local runs.

**Plan:**
- `.github/workflows/ci.yml`: on `push` + `pull_request` to `main`. One job, matrix Python 3.10–3.12 (README says 3.10+).
- Steps: checkout → setup-python → `pip install -r requirements.txt` + `pytest` → `python -m pytest tests/ -q`. Add a compile guard: `python -m compileall coros_decode.py convert_to_ics.py coros_to_fit.py app.py scripts/refresh_dictionary.py`.
- `pytest` is a test-only dep not in `requirements.txt`; add `requirements-dev.txt` (pytest) or a `[dev]` extra and install it in CI.
- Tests must stay offline (they already mock `requests`); CI has no network to COROS.
- Badge in README.

**Acceptance:** a PR shows a green check; a deliberately failing test red-flags the PR.

## Feature 2 — Rich swim / triathlon rendering  [calendar-only]

**Problem:** Swim decodes into `blocks` but `format_description` only renders the step body for `RICH_SPORTS` (Run/Bike/Strength/Hybrid), so a swim `.ics` event is overview-only (near-empty), and `fit_for_workout` tells swimmers "use the calendar" — which is itself thin.

**Plan:**
- Add a **structural** rendering tier in `coros_decode.format_description`: when `w.sport` is not rich but `w.blocks` exist, render steps **without sport-specific intensity** — duration/distance/reps + rest + repeat groups (e.g. `6× ( 100m / rest 30s )`). Reuse the existing `Step.human()` / RepeatGroup logic; the only difference from rich is that swim intensity isn't interpreted (already the case — `INTENSITY_KIND[5]="swim"` but `Target.human()` only emits %targets, so swim steps already render cleanly without intensity).
- Pool length: surface `poolLength`/`poolLengthUnit` in the workout header when present (often 0/None — guard).
- Scope: **calendar only.** No swim FIT schema this round (FIT swim is a separate, harder encoding). `fit_for_workout`'s swim message stays, but the `.ics`/calendar swim event is now useful.
- Must not change run/bike/strength output (regression test pins existing rich rendering).

**Acceptance:** a swim workout `.ics` shows its set structure; `test_decode` asserts swim body now contains the steps; existing rich-sport snapshot tests unchanged.

## Feature 3 — `.ZWO` structured export + optional intervals.icu upload  [revised per CEO D1]

**Problem / opportunity:** `.ics` is a reminder; `.FIT` needs USB sideload. A portable `.ZWO` file imports into intervals.icu / Zwift / TrainingPeaks with no account, and intervals.icu fans it out to Garmin/Zwift. The **primary deliverable is the account-free file**; a live push is an optional convenience.

**[CEO D1 — reshaped]** Promote the existing `poc/coros_to_zwo.py` (259 lines — already decodes COROS → `.ZWO` and already POSTs the intervals.icu `/events/bulk?upsert=true` payload) to production. Do **NOT** build a new FIT-based exporter (FIT planned-workout ingestion on intervals.icu is unvalidated; rebuilding proven code violates DRY).

**Plan:**
- Move `poc/coros_to_zwo.py` → a production module (e.g. `coros_to_zwo.py`), reusing the shared decoder. Primary output: a `.ZWO` **file** per run/bike workout (download / CLI), zipped for a plan like `.FIT`.
- **Optional live upload** (`--upload` flag, off by default): POST plain `.ZWO` in `file_contents` to `intervals.icu/api/v1/athlete/{id}/events/bulk?upsert=true`, dated `start_date_local`, `category="WORKOUT"`. **Clearly labelled "may break if intervals.icu changes their API."**
- **Auth (upload only):** personal **API key**, HTTP Basic (`API_KEY`:`<key>`). **CLI/env only** (`--athlete-id`, `INTERVALS_API_KEY`). The **web app stays calendar + FIT only** — never collects/transmits user keys (`§6` ToS).
- ZWO power-as-FTP-fraction maps cleanly onto COROS %threshold (`§4b`); run/bike this round (ZWO is cycling/run-oriented; swim/strength out of scope, consistent with FIT).

**Acceptance:** a COROS plan/workout produces valid `.ZWO` file(s) (validated offline in tests). With `--upload` + key + athlete id, events land on the intervals.icu calendar (mocked HTTP in tests). A bad/expired key gives a clear error, not a traceback.

**Go/no-go:** the live-upload half gets a reassessment after CI + swim ship — the `.ZWO` file alone may be enough.

## Cross-cutting
- Shared-decoder DRY: all three reuse `coros_decode`; #3 drives ZWO from the shared `Workout`/`Step` model (NOT the POC's duplicate decode).
- Tests: offline raw fixtures + monkeypatched network, matching existing conventions.
- ToS (`§6`): keep to the user's own plan/workout; intervals.icu is the user's own account + key.

---

## Autoplan review — folded decisions (CEO + Eng + DX, `[subagent-only]`, Codex unavailable)

### Feature 1 (CI) corrections
- **F4** Matrix must include **3.13** (local interpreter is 3.13; README "3.10+") → matrix 3.10–3.13.
- **F6** One mechanism: `requirements-dev.txt` = `-r requirements.txt` + pinned `pytest`; CI runs `pip install -r requirements-dev.txt` (installs runtime + dev in one step — fixes the `ModuleNotFoundError: icalendar` the CEO voice hit).
- **F5** Pin `fit-tool` (the FIT tests bind to its enums; unpinned = non-reproducible red builds). Pin the others opportunistically.
- **F7** `actions/setup-python` with `cache: pip`.
- **F8** Compile guard: `python -m compileall .` (whole tree, incl. the new `coros_to_zwo.py`) — `compileall` of a fixed list is near-redundant with pytest imports.

### Feature 2 (swim) corrections — **critical: the plan was incomplete**
- **F1 (CRITICAL)** Relaxing `format_description` alone does NOT fix swim in a **plan** — `convert_to_ics.py:387` has a SECOND `if rich.is_rich and rich.blocks` gate. Add a `Workout.has_structure` (≈ `bool(self.blocks)`) predicate and use it in **all three** sites (`format_description`, `convert_to_ics.py:387`, and the already-ungated `:246`) — one predicate, not three hand-rolled checks (DRY).
- **F2/F3** "No sport-specific intensity" is false for **Climb** (`@ 80% climb` renders). Decision (P1 completeness + correct data): render structure for **any sport with blocks** and let `Target.human()` emit whatever %target it has (swim → none, climb → `% climb`, both correct). Update plan wording; add a **climb fixture** + assert climb is intentional.
- **Test flip:** the existing `test_decode_workout_swim_decodes_structure_but_renders_overview_only` ASSERTS THE OLD limitation — it must be **rewritten** (assert `Workout:` + the `×` repeats + per-step distances), not just added to. Add an end-to-end swim **plan** test through `scrape_from_url` (mocked) — the path F1 exposes.
- Cut `poolLength` (F2 from CEO): `0`/None on real data.

### Feature 3 (ZWO + upload) corrections
- **F10 (HIGH)** Drive ZWO from the shared decoder's `Workout`/`Step` (the POC's `decode_step` gates on `isIntensityPercent` and would **drop run-pace %targets** the shared decoder keeps). **F10 taste:** ZWO `Power` is an FTP fraction — only emit it for actual power (`intensityType 9`); for run-pace/HR, render structure + a `<textevent>` note rather than encoding pace as a fake power fraction (avoid a semantic lie).
- **F9 + DX 2.1 (CRITICAL) error taxonomy** — `--upload` with missing key/athlete-id must **error out** (POC silently falls into dry-run — a trap); `401`→"API key rejected (bad/expired)…"; `403`/bad athlete→clear; `RequestException`→"couldn't reach intervals.icu"; the bulk endpoint returns **per-event results in a 200 body** → parse the array and report which events failed (partial failure doesn't raise).
- **F15 (dates)** Derive event dates from the same scheduling the `.ics` path uses (`calculate_plan_dates`/`dayNo`), NOT the POC's `idx+1` index arithmetic (mis-dates plans with rest days / multi-session days).
- **F14** Swim/strength-only plan → raise `ValueError("No run/bike workouts to export as .ZWO")` (mirror `fit_zip_for_plan`), don't emit an empty artifact or `IndexError` the dry-run printer.
- **DX 3.1 env names** Reconcile POC's `INTERVALS_ICU_*` with the plan: standardize on **`INTERVALS_API_KEY`** (env) + `--athlete-id` flag (accept `INTERVALS_ATHLETE_ID` env as fallback).
- **DX 3.2 CLI parity** New `coros_to_zwo.py` matches `coros_to_fit.py`: `--plan`/`--workout`, id-or-URL, reuse `parse_coros_url`. `--upload` off by default with `help=` text; dry-run prints the exact real-upload command.
- **F11** Test asserts the API key never appears in any printed/returned string.
- **F12/F13** ZWO validity test: `ElementTree.fromstring` parses + structural asserts (root `<workout_file>`, one `<sportType>∈{run,bike}`, known step tags, `Duration` positive int, `Power` 0.3–2.0). Upload test: monkeypatch `requests.post`, assert payload shape (`category=WORKOUT`, `start_date_local`, `file_contents`=ZWO), Basic auth `("API_KEY", key)`, URL has athlete id, `--upload` off ⇒ no POST; add 401 + ConnectionError cases.
- **DX 4.1 / 5.1 README** (same PR, per README-sync): new `.ZWO` CLI section mirroring `.FIT`; an **intervals.icu setup** recipe (key location, athlete-id location, the un-guessable `API_KEY`-as-Basic-username quirk, `export INTERVALS_API_KEY=`); the "may break if their API changes" + "run/bike only" caveats; file-vs-upload one-liner ("download the file to import anywhere; `--upload` only if you already use intervals.icu"); update Status table + "How it works" diagram (drop "experimental").

### Consensus (each phase: Claude subagent only; Codex N/A)
- **CEO** 1 strategic reframe (Feature 3 → ZWO POC, gated as D1, user chose it) + swim re-scope + order go/no-go. 
- **Eng** 17 findings (3 HIGH: F1 second gate, F9 error handling, F10 stale decode) — all folded.
- **DX** TTHW for the upload path ≈ 10–15 min (existing intervals.icu user) / 25–40 min (new) — dominated by the `API_KEY`-Basic-auth quirk and finding the athlete id → addressed by the README recipe + error taxonomy.

### Revised order & sizing
1. **CI** (~½ day) — no regret risk; do first.
2. **Swim** (~1 line + test flip + climb fixture, same day) — fold near CI.
3. **ZWO file export** (promote POC, shared-decoder rewrite, tests, README) — the real project.
4. **intervals.icu `--upload`** — **go/no-go after 1–3**: the account-free `.ZWO` file may be enough; the live push is the upkeep magnet.
