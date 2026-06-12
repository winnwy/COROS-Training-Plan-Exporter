# Standalone Workout Export — Research

_Researched 2026-06-12. Empirically verified against the live COROS API + web assets. Feeds the implementation plan; no code changed yet._

> **Goal:** export a standalone COROS **workout** (a single workout from COROS's
> "Workouts" library), not just a multi-week **training plan**. Today the tool
> only handles plans via `teamapi.coros.com/training/plan/detail`.

## TL;DR

- **Feasible and small.** A workout payload is shaped like a single plan
  `program`, so the shared `coros_decode.py` decodes it **with zero changes**
  (proven on run / hybrid / strength / swim). The work is plumbing + a dictionary refresh, not decoding.
- **Endpoint:** `GET teamapi.coros.com/training/program/detail?id=<programId>&region=<r>` — live, HTTP 200, **no auth**.
- **Share URL a user pastes:** `https://training.coros.com/workout-program?programId=<ID>&region=<r>` (verified 200; the workout analogue of the plan's `schedule-plan/share?planId=`).
- **Dictionary staleness is fully solvable & automatable** — COROS's own locale bundle is the source and is a clean superset of our bundled file.

---

## 1. Workout data model vs. plan data model

A workout's `program/detail` `data` object ≈ **one element of a plan's `programs[]`** — same `sportType`, `name`/`overview` shortcodes, `duration`, `trainingLoad`, `distance`, and an **identical exercise-level schema**. The decoder already iterates `data['programs']`, so a workout just needs wrapping as a single-program synthetic plan.

### Field diff (verified live)

| | Fields |
|---|---|
| **On a workout, not on a plan-program** | `hybridTotalSets`, `poolLengthId`, `poolLengthUnit`, `gradeSystemVersion`, `officalConfig`, `officialPrimaryIdStr`, `originId`, `region` |
| **On a plan-program, not on a workout** | `idInPlan`, `planId`, `star`, `exerciseBarChart` (conditional) |
| **The real difference** | A plan has the **schedule wrapper** — top-level `entities[]` (dated days), `totalWeeks`, `totalDay`, `weekStages`, per-day `dayNo`. **A workout has none of this** — it is a single, undated workout. |

**Implication:** the plan exporter's date-alignment path (`calculate_plan_dates`, `entities` → `dayNo` → week/day mapping) **does not apply** to a workout. A workout export produces **one** `.ics` event (dated to "today" or undated) and/or **one** `.FIT` file.

### Exercise-level schema — identical
`exerciseType`, `targetType`, `targetValue`, `intensityType`, `intensityValue`(`Extend`), `intensityPercent`(`Extend`), `sets`, `restType`/`restValue`, `groupId`, `isGroup`, `equipment`, `part`, `videoInfos`/`videoUrl`, `gradeSystem`, `onsightGradeOffset`. → `coros_decode.decode_plan` consumes all of these already.

**Proof (live decode, no code changes):**
```
Run workout (…5811):  89min · 19.52 km · TL 1479
  • Warm Up — 20min @ 88–94% pace
  6× ( Training 6min @ 100–105% pace / Rest 3min )
  • Cool Down — 15min @ 88–94% pace

Hybrid workout (…2560):
  3× ( One Arm KB Military Press 3×12 @ 10 kg / Elastic Band Pull-down 3×20 ) ...
```

### Sport coverage (sportType values seen on real workouts)
`1` Run · `2` Bike · `3` Swim · `4` Strength · `5/6` trail/track-ish · `7` Climb · `8` Bouldering · `9` Hybrid.

- **Run / Bike / Strength / Hybrid** → already `RICH_SPORTS`; full step+target+sets detail. ✅
- **Swim (3)** → the decoder parses structure into `w.blocks` (distance + `sets` + `restValue`, e.g. 6×100m), and as of the swim-rendering change `format_description` renders that structure for any sport with blocks (`Workout.has_structure`), so a swim `.ics` event now shows its full set breakdown. `poolLength`/`poolLengthUnit` present but `0`/null on the sample (not surfaced). No swim `.FIT` schema — swim stays calendar-only. _(Updated: earlier this said swim was overview-only; the `has_structure` tier shipped.)_
- **Climb / Boulder (7=Climb mapped; 8 still numeric)** → render structure too via `has_structure`; the climb `intensityType 10` %target prints as `% climb` (real data). `gradeSystem`/`onsightGradeOffset` still not interpreted (niche). Calendar-only, no `.FIT`.

---

## 2. Input / share URL

- **Plan (today):** `training.coros.com/schedule-plan/share?planId=<ID>&region=1`
- **Workout (new):** `training.coros.com/workout-program?programId=<ID>&region=<r>` — **verified 200**; its `programId` resolves directly via `program/detail` (e.g. `471761160696414208` → "Long VO2 Intervals", run, 5 exercises).

`training.coros.com` / `t.coros.com` are a Nuxt SPA (`static.coros.com/coros-traininghub-v2/...`), so the path is cosmetic — **what matters is extracting the ID**. The input parser should accept, in order:
1. `programId=<digits>` (workout share URL) → `program/detail`
2. `planId=<digits>` (existing plan flow) → `plan/detail`
3. a bare numeric ID (ambiguous — try `program/detail`, fall back to `plan/detail`, or require the user to disambiguate).

`region` defaults to `1` (matches current hardcode); pass through if present in the URL.

**Catalog finder** (`coros.com/training` → `/api/training/get-more-workouts`, CSRF-guarded) enumerates all 146 workouts + 64 plans — but bulk enumeration stays **deferred/cut** per `BUILD_PLAN.md §A3/§6` (ToS exposure). Keep to the user's pasted item.

---

## 3. Dictionary refresh — solved & automatable ⭐

The bundled `coros_dictionary.json` is **COROS's own web i18n string table**, extracted verbatim from the Training Hub locale bundle:

```
https://static.coros.com/locale/coros-traininghub-v2/en-US.prod.js
  →  window.en_US = { "TD1030": "...", "T3001": "Training", "W30291": "Lu Peng ... Aerobic Interval Running", ... }
```

**Refresh recipe (trivial):** fetch the JS, strip the `window.en_US=` prefix and trailing `;`, `json.loads` the object → that **is** `coros_dictionary.json`.

**Verified staleness gap:** live bundle has **7078** entries vs our bundled **6778** → **300 new codes, 0 removed** (pure superset — safe to overwrite). New codes include the **26 missing `W` (workout-name)** codes that currently render as raw `W302xx`, plus 29 `T`, 30 `S`/`H`, and **185 `C`** codes (climbing-related).

**Locales:** `en-US`, `zh-CN`, `de-DE`, `fr-FR`, `es-ES`, `ja-JP` all return 200 (same key, localized value); `en-GB` 404. Codes **are** locale-keyed → default `en-US`; region/locale could be parameterized later.

**Recommended strategy (layered):**
1. **Refresh the committed bundle** now from `en-US.prod.js` (+ add a tiny `scripts/refresh_dictionary.py` so it's repeatable).
2. **Title fallback** at decode time when a code still misses: use the sport name (e.g. "Run Workout") instead of emitting the raw `W302xx`. Cheap insurance against future drift between refreshes.
3. _(Optional, later)_ fetch the locale bundle live at runtime with the committed file as offline fallback — avoids ever shipping stale, at the cost of a network dependency. Probably overkill; (1)+(2) is enough.

---

## 4. Implementation outline (for the plan)

1. **`coros_decode.py`** — add `decode_workout(data, translate) -> Workout` (wrap as one-program plan; reuse `decode_plan`). Optionally extend `SPORT` with `5/6/7/8` so climb/boulder at least get a real sport label; add a sport-based title fallback.
2. **`convert_to_ics.py`** — generalize the input parser (programId vs planId); add a single-event `.ics` path for workouts (no `entities`, no date alignment; date = today or undated).
3. **`coros_to_fit.py`** — generalize `fetch_plan`/`--plan` to also accept `--workout`/programId; emit one `.FIT`.
4. **`app.py` / templates** — accept a workout link in the same paste box; route to the workout path.
5. **Dictionary** — refresh from the locale bundle + commit `scripts/refresh_dictionary.py`.
6. **Tests** — commit RAW `program/detail` fixtures: run-with-intervals, hybrid/strength (sets+weight+rest), swim (distance+sets), and a dictionary-miss case exercising the title fallback.
7. **README** — document workout export alongside plan export (per the standing README-sync habit).

## 5. Legal / ToS
Unchanged from `BUILD_PLAN.md §6`: reading the **public** `program/detail` for a **user's own/selected** workout is the same access model as the existing plan flow. Do **not** add catalog enumeration/redistribution. Both unofficial endpoints (`teamapi`, the locale bundle) can change without notice — mitigated by raw fixtures + graceful unknown-code/locale handling.

## Appendix — verification provenance
All §1–§3 facts verified live on 2026-06-12 against `teamapi.coros.com/training/{plan,program}/detail`, `training.coros.com`, and `static.coros.com/locale/coros-traininghub-v2/en-US.prod.js`. (The parallel `/deep-research` web-search workflow failed on a harness issue — subagents didn't emit StructuredOutput — but its agents independently surfaced the `workout-program?programId=` share-URL pattern, which is confirmed here directly.)
