# COROS Training Plan Exporter — Extension Build Plan

_Last updated 2026-06-12. Grounded in the full site inspection — see [`coros_map/COROS_MAP.md`](coros_map/COROS_MAP.md)._

## 0. Verification status (done)

The existing decode pipeline was re-verified against the **live** COROS API on 2026-06-12 and works end-to-end:

- Endpoint `GET teamapi.coros.com/training/plan/detail` is live (HTTP 200).
- Shortcode decode via `coros_dictionary.json` (6,778 entries) still fires: `T1120`→Warm Up, `T1122`→Cool Down, `T3001`→Training.
- A real plan parsed to 98 workouts → 98 valid `.ics` VEVENTs.

Nothing is broken. Safe to extend.

## 1. What the full site inspection changed

We inspected **all 210 public catalog items** (146 workouts + 64 plans) across all 9 sport types. Key implications for the build (full data in `coros_map/`):

1. **The whole library is enumerable + decodable without login.** The marketing finder (`coros.com/training` → `/api/training/get-more-workouts`) is guarded only by a **CSRF token** (the page's own `x-csrf-token` cookie), not a secret signature. With that token it returns the full catalog. Each item then decodes via public detail endpoints:
   - Plans: `GET teamapi.coros.com/training/plan/detail?id=<planId>&region=<r>&supportRestExercise=1`
   - Workouts: `GET teamapi.coros.com/training/program/detail?id=<programId>&region=<r>`
   → The exporter can offer **browse/pick from the catalog**, not just "paste a share URL".

2. **The current parser is shallow, but unevenly so.** There are **two** code paths in `convert_to_ics.py`:
   - **New `exerciseBarChart` path** (`:124-200`): reads only the 3 summary bars, handles only `targetType` 2 (time) & 5 (distance), and **drops intensity entirely**.
   - **Legacy `sport`/`exercises[]` path** (`:202-256`): already parses the richer `exercises[]` array and **already renders pace intensity ranges** (`intensityType 3` → "@ X-Y% threshold", `:232-239`).
   So "intensity is dropped" is true only for the new path. The richer array still drops reps, sets, weight, HR/power targets, rest, intervals, and movement instructions on both paths. A1 unifies these into one decoder over `exercises[]`.

3. **Sport type is per-*program*, not per-*plan*, and mixing is common.** Many run plans embed strength days (Sub-2 Half = 57 run + 57 strength; ultras + Kilian carry strength; cross-training mixes run/bike/strength). The renderer must branch on each program's `sportType`.

4. **Decode tables** (see map §4). The enum *values* were observed across all 210 items, but their *semantics* were sampled from a few raw payloads — re-derive from raw fixtures (A4) before trusting unit scales/range fields. **Correction (post-review):** the less-common enums are NOT climbing-only — `intensityType 5 = Swim`, `9 = Cycling power`, `10 = Climb/Track`, and `targetType 8 = TrailRun`. They must be decoded, not skipped, or swim/cycling intensity targets get silently blanked.

## 2. Scope (confirmed with user)

- **Calendar export — build now:** (a) richer per-workout detail in each event, AND (b) strength/exercise-plan support.
- **Structured export — partially built (user signed off 2026-06-12):** Garmin **`.FIT`** export for run/bike is **DONE** (`coros_to_fit.py` — durations + interval repeats exact, targets in step names, USB sideload; `tests/test_fit.py`). Still not built: intervals.icu / `.ZWO` to production (POC in `poc/`), direct Garmin Connect upload (unofficial API), and strength/swim FIT schemas.

## 3. Work items

### A1 — Rich per-workout detail
1. Parse the `exercises[]` array (fall back to `exerciseBarChart` for old plans).
2. Decode every step: step-label T-code + the `_desc` movement instructions (373 available in the dictionary).
3. Extend target decoding beyond time/distance:
   - `targetType` 1=open, 2=time, 3=reps, 5=distance(cm), 8=trail-run, 9=climbing.
   - `intensityType` 1=weight(g), 2=HR, 3=pace, 5=swim, 7=HR-range, 8=pace-range, 9=cycling-power, 10=climb; render `intensityPercent`/`*Extend` as "% of threshold" and ranges as low–high. Reuse the legacy path's existing pace-range logic (`:232-239`) as the starting point.
4. Render interval/superset groups (`isGroup` + `groupId`, repeat = `sets`). NOTE: an all-day VEVENT has no time structure, so groups must be **flattened into text** — spec the exact format, e.g. "4× (800m @ 95–100% pace / 400m easy)", and decide how nested supersets collapse.
5. **`.ics` correctness (RFC 5545 — see §5):** DESCRIPTION may appear **only once** per VEVENT, so all step detail goes into one folded DESCRIPTION (escaped `\n`), not repeated lines. Lines fold at **75 octets** (octet-aware, not char-count — emoji are multi-byte). Rich bodies can be large (Cross Training Plan = 472 steps / 72 programs), so set a per-event truncation/summarization cap. `icalendar` handles folding but verify against the longest real plan.

### A2 — Strength / exercise plans
1. Detect kind via each program's raw `sportType` integer (4=strength, 9=hybrid). NOTE: the inspection artifacts store *decoded strings* ("Strength"/"Hybrid"); the live API returns integers — branch on the integers in code.
2. Parse `exercises[]` for sets, `restType`/`restValue`, `equipment`, `muscle`, and the `_desc` form cues; strength work-steps are media-rich (video/muscle present on ~all).
3. Render a strength-appropriate event body (movement — sets × reps/time @ weight, rest, form cues). Note `intensityType 1` weight is in **grams** — convert to kg/lb.
4. Validate against real strength plans from the catalog — `455706700727631876` (Injury Prevention, confirmed present). _(The previously-listed `441899422090182658` is NOT in the catalog — dropped; pick a second real strength ID from `catalog_210.json`.)_

### A3 — Catalog browse (DEFERRED — see review)
_Originally: enumerate the library via the CSRF-authed finder and let users pick from all 210 items. **Deferred / likely cut.** CSRF-token absence is not authorization; programmatically enumerating and redistributing COROS's catalog is a ToS exposure and a maintenance treadmill (Avelon/Nuxt surface that will change), and it adds little to the core calendar value. Keep the paste-a-URL flow plus the public per-item detail fetch. Revisit only if there's clear user demand and we accept the upkeep._

### A4 — Plumbing, correctness & safety
1. Extract a shared `format_workout(program, dictionary)` helper used by CLI, Flask, and any future Garmin exporter.
2. Add regression fixtures — **commit the RAW detail JSON** (not the decoded count summaries the map stores) so tests pin the decode logic offline and catch API drift. Highest-value cases: (a) run plan with `isGroup` intervals, (b) multi-sport plan (Cross Training, 3 sports), (c) strength workout with weight+reps+rest+`_desc`, (d) a swim (`intensityType 5`) and a cycling (`9`) workout — guards the "don't blank these" bug, (e) the Kilian trail workout (`targetType 8`), (f) a legacy `sport`-format payload, (g) `calculate_plan_dates` where the first workout isn't day 0.
3. Log any unmapped `targetType`/`intensityType` **and dictionary misses** (`translate_key` silently returns the raw key, `:48`; ~109 of 482 movements lack `_desc`) rather than emitting blanks/raw codes.
4. **Audit `calculate_plan_dates` (`:366-435`)** — it anchors to the first workout's weekday and back-computes a base date; verify it doesn't shift subsequent workouts when the plan's first day isn't day 0.
5. **Region/i18n:** `scrape_from_url` hardcodes `region="1"` (`:74`) and one dictionary; the catalog spans regions/locales. Decide whether to parameterize region and whether the dictionary is locale-specific.
6. **Unit conversions:** distance is cm (÷100000→km, already done), weight is grams (→kg/lb), pace needs formatting; add explicit conversion tests including imperial output.

## 4. Structured-workout export targets (research — folds in deep-research findings)

**Key reframe (from research): `.ics` and Garmin `.FIT` are not the only — or best — structured-workout targets.** An `.ics` event is a *reminder*; a watch-guided structured workout needs a real structured format. Once A1 produces a normalized step model, it can fan out to several sinks. Ranked by leverage:

### 4a. intervals.icu Open API — recommended primary structured sink
- **Official, sanctioned API** (OAuth 2.0 *or* per-user personal API key). Create planned structured workouts on the athlete calendar via `POST /api/v1/athlete/{id}/events/bulk?upsert=true`, dated with `start_date_local`. Accepts **`.zwo`/`.fit`/`.mrc`/`.erg`** payloads (base64 in `file_contents_base64`; ZWO also plain in `file_contents`).
- **Why it matters:** a documented, structured sink that **sidesteps Garmin's partner gate and COROS scraping entirely**, and intervals.icu itself fans workouts out to Garmin/Zwift. This is the cleanest path to "real" (non-reminder) export. _(intervals.icu Open API docs; forum: uploading planned workouts.)_

### 4b. `.ZWO` (Zwift) — low-effort portable structured file
- XML; power as **FTP fraction** (`Power="0.5"` = 50% FTP, not watts); typed steps `Warmup / SteadyState / IntervalsT / Ramp / Cooldown / FreeRide / MaxEffort`.
- **Why it matters:** human-readable, simpler than FIT, accepted directly by intervals.icu, and its FTP-fraction model maps cleanly onto COROS `%threshold`/zone targets. _(h4l/zwift-workout-file-reference; no official Zwift spec exists — caveat.)_

### 4c. Garmin — three distinct routes, very different gating (corrected)
| Route | Mechanism | Verdict for a hobby tool |
|---|---|---|
| **Official Training API** | Publishes planned workouts to Connect calendar for on-watch guidance | **Rule out** — partner-gated, enterprise-only, approval + throttling; program may be closed to new applicants. |
| **`python-garminconnect`** (unofficial) | Private `/workout-service`, `/workout-service/schedule`, `/calendar-service` via **mobile-SSO impersonation**; tokens cached `~/.garminconnect/`. | Works but **ToS/account risk** (429s/48h blocks reported). **CRITICAL CORRECTION:** `upload_activity()` pushes **completed activities, NOT planned workouts** — planned workouts need *workout-create* + `schedule_workout(id, date)`. |
| **USB `.FIT` sideload** | Write FIT to `GARMIN/NewFiles/` (auto-moved to `Workouts/`); some models need `Workouts/` directly | Safest (no login, no ToS). Manual; device caps (~25–50); per-model folder variation. |

**FIT workout schema (if we generate FIT)** — encode exactly: File Id **type 5 (Workout)** → one Workout msg with `num_valid_steps` → Workout Step msgs in performance order with **zero-based `message_index`**. Repeats = a step with `duration_type 6` (repeat_until_steps_cmplt), `duration_step` = index to repeat from, `repeat_steps` = count. Each step: `intensity` (Warmup/Active/Rest/Cooldown/Recovery/Interval), `duration_type`+value (time **ms**, distance **cm**, or Open), `target_type` (HR/Power/Speed/Cadence) with `custom_target_value_low/high` for absolute or % targets. Wrong order / counts / unit scaling → silent import failure. _(Garmin FIT cookbook; FIT File Types Description Rev 2.2.)_

COROS↔Garmin step models map ~1:1 (Warm Up→WARMUP, Training→ACTIVE, Rest→REST, Cool Down→COOLDOWN, interval→repeat, HR/pace/power→target_type; COROS `%threshold` → `custom_target` low/high). The A1 normalized model is the shared intermediate for all of 4a–4c.

## 5. Calendar & delivery correctness (.ics)
- **DESCRIPTION once per VEVENT**; pack steps into a single folded value or X-properties / RFC 9073 `STRUCTURED-DATA` — never repeated DESCRIPTION lines (invalid, truncated by parsers).
- **75-octet, octet-aware line folding** (CRLF + single space); emoji count as multiple octets.
- **Date-time forms:** floating-local / UTC (`Z`) / `TZID`-referenced, plus all-day `VALUE=DATE`. A dated multi-week plan across timezones must pick one consistently — mixing `TZID` with a `Z` value, or omitting `VTIMEZONE` (Google then ignores `TZID`), shifts workouts to wrong days/hours. Current code emits all-day `VALUE=DATE` (TZ-agnostic) — fine, but document the choice and don't half-add times.
- **Delivery model — add a hosted webcal feed:** a static downloaded `.ics` goes stale; a **webcal subscription** (one-way, auto-refresh) suits a plan that updates over time. CalDAV would be two-way (overkill). Decide: file download vs hosted subscription URL.

## 6. Risks
- COROS API/CSRF drift → mitigated by A4 raw fixtures + graceful unknown-enum logging. Both unofficial APIs (COROS teamapi, garminconnect) can break without notice.
- Strength rendering unknowns → A2 step 4 validates against real plans first.
- **Decode-semantics risk:** unit scales/range fields were sampled, not validated across all 210; mis-attributed enums touch mainstream **swim & cycling**. Re-derive from raw fixtures before shipping.
- Date-alignment bug risk in `calculate_plan_dates` (A4.4).
- **Legal / ToS** (do not treat as cleared):
  - Reading the *public* `teamapi.coros.com/training/plan/detail` for a user's own plan is likely CFAA-safe (hiQ v. LinkedIn, 9th Cir.) — but that's 9th-Circuit-only and does **not** immunize ToS breach, copyright, or state claims.
  - **Redistributing COROS plan *content*** (decoded shortcodes, curated plans) is the real exposure: copyright + breach-of-contract (cf. Meta v. BrandTotal). Browsewrap is usually unenforceable; clickwrap is enforceable.
  - **CSRF-token catalog enumeration (A3)** heightens ToS-breach risk → another reason A3 stays deferred. Keep exports to the *user's own* selected plan, not bulk catalog redistribution.
- `python-garminconnect` account risk (SSO impersonation, observed 429/48h blocks).

## 7. Prior art — reuse, don't rebuild
- **`xballoy/coros-api`** — already exports COROS activities (FIT/TCX/GPX/KML/CSV) and a **7-day training-calendar `.ics`** export. Reuse its export plumbing. Caveats: it reads the *authenticated personal Training Hub* (email+password — different access model from our public plan endpoint), warns it can break anytime, and its ICS is reminder-level (not the structured per-step detail A1/A2 add).
- **`futoshita/Coros-Training-Hub-Exporter`** — calendar + completed-activity export only; not structured workouts.
- No existing tool converts COROS *structured plans* → ZWO/FIT/intervals.icu — that per-step conversion is the genuinely new value here.

## 8. Open decisions (need a call before building 4x)
1. **Primary structured sink:** intervals.icu API (sanctioned, adds an account dependency) vs `.ZWO` files (portable, consumer-side import varies) vs FIT sideload. _Recommendation: intervals.icu first, `.ZWO` as the portable file format._
2. **COROS swim/triathlon/power model** still needs direct payload inspection (pool length, stroke, drills, transitions, brick workouts, running-power, cycling-FTP). Research found no COROS-published machine doc — inspect a real swim/tri payload during A1.
3. **Delivery:** one-time `.ics` download vs hosted webcal subscription (§5).
4. **Empirical calendar rendering:** test long folded DESCRIPTION + emoji in Google/Apple/Outlook before committing to a rich body format.

## 9. Proposed sequence
A1 + A4 (rich decode over unified `exercises[]` + shared helper + RAW fixtures) → A2 (strength, validated on real plans, after `sportType`/intensity tables re-derived) → **then, only if the user approves structured export per §2/§8.1**, 4a (intervals.icu) once the normalized model is solid → Garmin/ZWO documented. **A3 deferred/cut.**

## 10. Reference artifacts
- [`coros_map/COROS_MAP.md`](coros_map/COROS_MAP.md) — complete map (totals, taxonomy, decode tables, all plans + workouts)
- `coros_map/catalog_210.json` — every item's ID + metadata
- `coros_map/all_items_inspected.json` — per-item decoded summary
- `coros_map/exercise_library.json` — movement library
- `coros_map/taxonomy_raw.json` — raw filter taxonomy

## Appendix — research provenance
Deep-research run 2026-06-12: 5 angles, 23 sources fetched, 89 claims, 25 adversarially verified (25 confirmed / 0 killed). Key sources: intervals.icu Open API docs; h4l/zwift-workout-file-reference; Garmin FIT cookbook + FIT File Types Description Rev 2.2; RFC 5545; cyberjunky/python-garminconnect; xballoy/coros-api; Quinn Emanuel web-scraping legal review (hiQ v. LinkedIn, Meta v. BrandTotal).
