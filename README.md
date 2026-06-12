# COROS Training Plan Exporter

Turn a COROS training plan into something you can actually use outside the COROS app — a **calendar feed** (`.ics`) today, and **structured workouts** (`.ZWO` / intervals.icu) experimentally.

## ▶️ Try it now — no install

### **[coros-training-plan-exporter.vercel.app](https://coros-training-plan-exporter.vercel.app/)**

Paste a COROS plan URL, preview the schedule, download the `.ics`. That's it. The hosted app is live and runs the full decoder, so run/bike workouts come through with every interval and HR/pace target spelled out (see the example below).

---

COROS publishes its plans through a public API, but the workout details are stored as shortcodes (`T3001`, `P12999`, …). This tool fetches a plan, **decodes those shortcodes into plain English** using a bundled dictionary, and exports the result. Prefer to run it yourself? See [Run locally](#run-locally).

---

## What you get

### 📅 Calendar export (`.ics`) — the main feature
Paste a COROS plan URL and download an `.ics` you can import into Google Calendar, Apple Calendar, Outlook, etc. One all-day event per workout, dated to your start day (aligned to the plan's first weekday).

For **run, bike, and strength** plans, each event now carries the **full decoded workout** — warm-up, every interval or movement, and cool-down, with targets:

```
Threshold                                    (Tue 24 Jun)

Duration: 60min / Training Load: 103
This should not feel like an easy session (RPE 8/10). Slowly progress
towards threshold and try to remain seated throughout.

Workout:
 • Warm Up — open
 • Training — 30min @ 80–90% HR
3×
   • Training — 5min @ 96–102% HR
   • Rest — 5min @ 80–90% HR
 • Cool Down — open
```

Intervals are shown as repeats (`3× (...)`), and HR / pace targets are decoded as `%`-of-threshold ranges. **Strength** plans render each movement as `sets×reps @ weight` (or `Ns hold`), with bodyweight moves omitting the load — e.g. `Deadlifts with Bands — 3×10 @ 6.8 kg (rest 60s)`. Swim / triathlon / climbing plans export at overview level for now.

### ⌚ Garmin watch export (`.FIT`)
A `.ics` event is just a reminder. To get a **watch-guided** workout (your Garmin steps you through warm-up, every interval, and cool-down), use `coros_to_fit.py` — it turns a **run/bike** plan into Garmin `.FIT` workout files:

```bash
pip install -r requirements-fit.txt
python3 coros_to_fit.py --plan <ID> --out ./fit_out
# then copy the .fit files to your watch's GARMIN/NewFiles/ folder over USB
```

Durations and interval repeats are encoded exactly (the watch guides the structure); the intended HR/pace target is carried in each step's name (e.g. `Training @ 96–102% HR`), because COROS uses %-of-threshold which doesn't map cleanly onto Garmin's zone model. Strength/swim use a different FIT schema (not yet supported).

### 🏃 Also: `.ZWO` / intervals.icu (experimental POC)
The proof-of-concept in [`poc/`](poc/) converts run/bike plans to Zwift **`.ZWO`** files and can upload them to **intervals.icu** (which forwards to Garmin/Zwift). See [`poc/README.md`](poc/README.md). Opt-in, not wired into the web app.

---

## Use online

The hosted version needs nothing installed: **https://coros-training-plan-exporter.vercel.app/**

1. Paste your COROS plan URL.
2. (Optional) pick a start date — blank = today, aligned to the plan's first weekday.
3. **Preview** the schedule, then **download** the `.ics`.
4. Import it into your calendar app.

---

## Run locally

**Prerequisites:** Python 3.10+ and an internet connection.

```bash
git clone https://github.com/winnwy/COROS-Training-Plan-Exporter.git
cd COROS-Training-Plan-Exporter
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Web app
```bash
./run.sh            # or: python3 app.py
# open http://127.0.0.1:5000
```

### CLI
```bash
python3 convert_to_ics.py --url "https://training.coros.com/schedule-plan/share?planId=<ID>&region=1"
# writes coros_training_plan.ics  (prompts for a start date; press Enter for today)
```

### Structured-workout POC
```bash
python3 poc/coros_to_zwo.py --plan <ID> --start 2026-07-01      # writes .zwo files (dry run)
# real upload: set INTERVALS_ICU_API_KEY + INTERVALS_ICU_ATHLETE_ID and add --upload
```

---

## How it works

```
COROS plan URL
   └─ teamapi.coros.com/training/plan/detail        (public API, no login)
        └─ coros_decode.py        decode shortcodes + build a normalized
                                   Step / RepeatGroup / Workout model
             ├─ convert_to_ics.py  → .ics calendar (rich run/bike detail)
             ├─ coros_to_fit.py    → Garmin .FIT workouts  (run/bike, sideload)
             └─ poc/coros_to_zwo.py → .ZWO / intervals.icu  (structured, experimental)
```

`coros_decode.py` is the shared decoder — one source of truth that both the calendar exporter and the structured-export POC build on.

## Project layout

| Path | Purpose |
|---|---|
| `app.py` | Flask web app (UI + routing) |
| `convert_to_ics.py` | URL scraping, date alignment, `.ics` generation |
| `coros_decode.py` | Shared decoder → normalized workout model + rich description |
| `coros_dictionary.json` | Shortcode → natural-language dictionary (~6,800 entries) |
| `templates/` | Web frontend (`index.html`, `preview.html`) |
| `coros_to_fit.py` | Garmin `.FIT` workout exporter (run/bike) — needs `requirements-fit.txt` |
| `poc/` | Structured-export proof of concept (`.ZWO` / intervals.icu) |
| `tests/` | pytest + committed raw API fixtures |
| `docs/` | [Build plan](docs/BUILD_PLAN.md), [full site map](docs/coros_map/COROS_MAP.md), [follow-ups](docs/FOLLOWUPS.md) |

## Status

- ✅ **Shipped:** `.ics` export with rich detail for **run, bike, and strength** (steps/movements, intervals, sets×reps, HR/pace % targets, weight).
- ⌚ **Shipped (CLI):** Garmin `.FIT` workout export for run/bike (`coros_to_fit.py`) — sideload to the watch.
- 🧪 **Experimental:** `.ZWO` / intervals.icu structured export (run/bike, POC).
- 🔬 **Researched, not built:** direct Garmin Connect upload (unofficial API) — see [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md) §4.
- 🚧 **Basic only:** swim / triathlon / climbing plans export at overview level (no per-step detail yet) — tracked in [`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md).

## License

MIT
