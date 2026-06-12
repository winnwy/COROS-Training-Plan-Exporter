# COROS Training Content — Complete Site Map

_Generated 2026-06-12. COMPLETE enumeration: all 210 public catalog items inspected (0 fetch failures)._

## 1. Inventory totals

- **Total catalog items: 210** (146 workouts + 64 training plans)
- **By sport type:** run=118, strength=45, cycling=30, trail_run=25, hybrid_fitness=12, bouldering=7, climbing=4, swimming=2, triathlon=1
- **By difficulty:** intermediate=87, advanced=68, (plans:n/a)=64, beginner=45
- **Plan targets:** marathon=17, half_marathon=14, 10k=10, 5k=10, ultra_distance=9, base_plan=7, speed_development=3, plan_target_triathlon=1
- **Workout targets:** vo2max=31, threshold=26, base_workout=19, full_body=19, lower_body=16, tempo=13, upper_body=12, sprint=11, core=9, station=8, running=6, ftp=5, strength=3

## 2. Site surfaces & how the catalog was obtained

- **Marketing finder** `coros.com/training` → Nuxt server routes `/api/training/{page-ssr-data, get-more-workouts}` backed by Avelon CMS. Guarded by **CSRF** (`x-csrf-token` cookie), NOT a secret signature. Driving it with the page's own CSRF token returns the full catalog (paginated, 50/page).
- **Training Hub** `training.coros.com` → `teamapi.coros.com`, list via `POST /training/program/query` (login-gated; not needed once the finder is enumerated).
- **Public per-item detail (no auth):**
  - Plans: `GET teamapi.coros.com/training/plan/detail?id=<planId>&region=<r>&supportRestExercise=1`
  - Workouts: `GET teamapi.coros.com/training/program/detail?id=<programId>&region=<r>`

## 3. Taxonomy (full classification)

- **categories** (2): workout=Workout, plan=Plan
- **sportTypes** (9): run=Run, trail_run=Trail Run, cycling=Bike, swimming=Swim, triathlon=Triathlon, strength=Strength, climbing=Indoor Climb, hybrid_fitness=, bouldering=Bouldering
- **workoutTargets** (13): base_workout=Base, strength=Strength, running=, station=, tempo=Tempo, threshold=Threshold, ftp=FTP, vo2max=VO2max, sprint=Sprint, full_body=Full body, core=Core, upper_body=Upper body, lower_body=Lower body
- **planTargets** (8): 5k=5k, 10k=10k, half_marathon=Half-marathon, marathon=Marathon, ultra_distance=Ultra-distance, plan_target_triathlon=Triathlon, base_plan=Base, speed_development=Speed Developement
- **difficulties** (3): intermediate=Intermediate, beginner=Beginner, advanced=Advanced

## 4. Workout-step decode tables (enum VALUES observed across all 210; semantics sampled)

```
sportType      1 Run · 2 Bike · 3 Swim · 4 Strength · 9 Hybrid Fitness
               (raw API integers; some climb items decode to "Track")
targetType     0 OPEN/none · 1 OPEN(no value) · 2 TIME(sec) · 3 REPS · 5 DISTANCE(cm)
               8 trail-run-specific (TrailRun only; sport confirmed, semantics inferred)
               9 climbing-specific target (moves/problems; Climb/Boulder only; sport confirmed, semantics inferred)
intensityType  0 none · 1 weight(g) · 2 HR(single) · 3 pace(single)
               5 SWIM intensity (swim + run/bike/swim mixes)
               7 HR-range · 8 pace-range(value+valueExtend)
               9 CYCLING power/intensity (bike only)
               10 climb/track intensity (grade/effort; inferred)
intensityPercent  x1000 => % of threshold (80000 = 80.0%); isIntensityPercent flags it
intensityDisplayUnit  0 none · 2 pace · 7 strength
hrType         0 none · 3 %threshold(LTHR) · 2 %max(likely) · 1 zone(likely)
restType       0 n/a · 1 fixed(restValue sec) · 3 none
isGroup=true   interval/superset header; sets = repeat count; members share groupId
```
_Validation caveat: the enum **values** were observed across all 210 items (per-item counts in `all_items_inspected.json`), but the **semantics** (cm/grams/×1000-percent scales, range fields, interval grouping) were derived from a sampled handful of raw step payloads — the artifacts store decoded counts, not raw step fields. Re-derive from committed raw fixtures before relying on them. Sport attribution of the less-common enums IS confirmed: targetType 8→TrailRun; intensityType 5→Swim, 9→Bike, 10→Climb/Track — so they must NOT be treated as "climbing-only, skip"._

## 5. All training plans (64)

| title | targets | diff | wks | progs | ex-steps | sport mix |
|---|---|---|---|---|---|---|
| Introduction to 10k Training Plan | 10k |  | 6 | 18 | 62 | {'Run': 18} |
| 10k Beginner Training Plan | 10k |  | 10 | 35 | 132 | {'Run': 35} |
| 10k Intermediate/Advanced Training Pla | 10k |  | 10 | 45 | 187 | {'Run': 45} |
| Sub-45min 10K Plan | 10k |  | 8 | 31 | 172 | {'Run': 31} |
| Sub-50min 10K Plan | 10k |  | 8 | 31 | 169 | {'Run': 31} |
| Sub-55min 10K Plan | 10k |  | 8 | 31 | 169 | {'Run': 31} |
| Sub-60min 10K Plan | 10k |  | 8 | 31 | 168 | {'Run': 31} |
| Sub-70min 10K Plan | 10k |  | 6 | 18 | 25 | {'Run': 18} |
| Strength Training Plan for Injury Prev | 5k,10k,half_marathon,marathon,ultra_distance |  | 8 | 24 | 176 | {'Strength': 24} |
| 10-Week Return to Running Training Pla | 5k,10k,half_marathon,marathon |  | 10 | 42 | 92 | {'Run': 42} |
| Introduction to 5k Training Plan | 5k |  | 6 | 18 | 76 | {'Run': 18} |
| 5k Beginner Training Plan | 5k |  | 12 | 48 | 220 | {'Run': 48} |
| 5k Intermediate/Advanced Training Plan | 5k |  | 10 | 44 | 218 | {'Run': 44} |
| Sub-25 5K Training Plan | 5k |  | 14 | 48 | 156 | {'Run': 48} |
| Sub-25min 5K Plan | 5k |  | 4 | 12 | 23 | {'Run': 12} |
| Sub-30min 5K Plan | 5k |  | 4 | 12 | 21 | {'Run': 12} |
| Sub-35min 5K Plan | 5k |  | 4 | 12 | 12 | {'Run': 12} |
| 21-Day Habit-Building Plan | 5k |  | 3 | 10 | 60 | {'Run': 10} |
| Beginner Runner Base Plan (Metric) | base_plan |  | 10 | 44 | 132 | {'Run': 43, 'Bike': 1} |
| Beginner Base Plan | base_plan |  | 6 | 48 | 118 | {'Strength': 24, 'Run': 24} |
| Intermediate Base Plan | base_plan |  | 6 | 54 | 147 | {'Run': 24, 'Strength': 30} |
| Cross Training Plan | base_plan |  | 8 | 72 | 472 | {'Strength': 40, 'Bike': 8, 'Run': 24} |
| 8-Week Off-Season Training Plan | base_plan |  | 8 | 42 | 131 | {'Run': 29, 'Bike': 13} |
| Beginner Base Endurance Cycling Plan | base_plan |  | 8 | 28 | 143 | {'Bike': 28} |
| Intermediate Base Endurance Cycling Pl | base_plan |  | 8 | 37 | 192 | {'Bike': 37} |
| Advanced Half-Marathon Training Plan - | half_marathon |  | 12 | 66 | 255 | {'Run': 66} |
| Intermediate Half-Marathon Training Pl | half_marathon |  | 12 | 56 | 211 | {'Run': 56} |
| Beginner Half-Marathon Training Plan - | half_marathon |  | 12 | 56 | 209 | {'Run': 56} |
| Half Marathon HR Plan | half_marathon |  | 12 | 60 | 217 | {'Run': 60} |
| Beginner Half-Marathon Training Plan - | half_marathon |  | 12 | 56 | 209 | {'Run': 56} |
| Intermediate Half-Marathon Training Pl | half_marathon |  | 12 | 56 | 211 | {'Run': 56} |
| 1:40 Half-Marathon Plan | half_marathon |  | 10 | 39 | 226 | {'Run': 39} |
| 1:50 Half-Marathon Plan | half_marathon |  | 10 | 39 | 223 | {'Run': 39} |
| Sub-2:00 Half Marathon Training Plan | half_marathon |  | 12 | 114 | 796 | {'Strength': 57, 'Run': 57} |
| 2:00 Half-Marathon Plan | half_marathon |  | 10 | 39 | 219 | {'Run': 39} |
| Half-Marathon Finish Plan | half_marathon |  | 10 | 30 | 150 | {'Run': 30} |
| 10-Week Half-Marathon Mountain Trainin | half_marathon |  | 10 | 61 | 339 | {'Run': 45, 'Strength': 16} |
| 2:45-3:00 Marathon Plan | marathon |  | 12 | 65 | 211 | {'Run': 65} |
| Sub-3:15 Marathon Training Plan | marathon |  | 8 | 22 | 124 | {'Run': 22} |
| 3:15-3:35 12-Week Marathon Plan | marathon |  | 12 | 59 | 205 | {'Run': 59} |
| 4:00-4:30 12-Week Marathon Plan | marathon |  | 12 | 58 | 196 | {'Run': 58} |
| 16-Week Beginner Marathon Training Pla | marathon |  | 16 | 76 | 258 | {'Run': 76} |
| 16-Week Intermediate Marathon Training | marathon |  | 16 | 76 | 257 | {'Run': 76} |
| Advanced Marathon Training Plan | marathon |  | 16 | 87 | 306 | {'Run': 87} |
| Beginner Marathon Training Plan | marathon |  | 20 | 95 | 323 | {'Run': 95} |
| 20-Week Intermediate Marathon Training | marathon |  | 20 | 95 | 323 | {'Run': 95} |
| Advanced Marathon Training Plan | marathon |  | 20 | 112 | 389 | {'Run': 112} |
| 12-Week Molly Seidel Marathon Plan | marathon |  | 12 | 68 | 251 | {'Run': 68} |
| 3:30 Marathon plan | marathon |  | 12 | 48 | 218 | {'Run': 48} |
| 4:00 Marathon plan | marathon |  | 12 | 48 | 216 | {'Run': 48} |
| 4:30 Marathon plan | marathon |  | 12 | 47 | 206 | {'Run': 47} |
| 5:00 Marathon Plan | marathon |  | 12 | 47 | 206 | {'Run': 47} |
| Beginner Sprint Distance Triathlon Pla | plan_target_triathlon |  | 12 | 87 | 367 | {'Bike': 28, 'Swim': 26, 'Run': 33} |
| Run Speed Development | speed_development |  | 12 | 64 | 272 | {'Run': 64} |
| Threshold Development | speed_development |  | 9 | 48 | 207 | {'Run': 48} |
| Threshold Development Cycling Plan | speed_development |  | 6 | 30 | 142 | {'Bike': 30} |
| Intermediate Mountain Training Plan | ultra_distance |  | 12 | 76 | 533 | {'TrailRun': 53, 'Run': 12, 'Strength': 11} |
| Advanced Mountain Training Plan | ultra_distance |  | 12 | 96 | 672 | {'TrailRun': 72, 'Run': 12, 'Strength': 12} |
| 6-Week Mountain Running Training Plan | ultra_distance |  | 6 | 39 | 233 | {'Run': 31, 'Strength': 8} |
| 10-Week 50k Mountain Training Plan | ultra_distance |  | 10 | 62 | 379 | {'Run': 46, 'Strength': 16} |
| 50k Trail Run Training Plan | ultra_distance |  | 20 | 109 | 407 | {'Run': 109} |
| 100K Ultra Training Plan | ultra_distance |  | 12 | 81 | 382 | {'Run': 67, 'Strength': 14} |
| 12-Week 100 Mile Ultra Training Plan | ultra_distance |  | 12 | 81 | 312 | {'Strength': 14, 'Run': 67} |
| 100-Miles Cycling Training Plan | ultra_distance |  | 12 | 56 | 243 | {'Bike': 56} |

## 6. All workouts (146) — grouped by sport

Counts by sport: run=67, strength=45, cycling=26, trail_run=16, hybrid_fitness=12, bouldering=7, climbing=4, swimming=2

<details><summary>Full workout list (146)</summary>

| title | sport | target | steps | load |
|---|---|---|---|---|
| Lu Peng Hybrid Fitness - Foundational St | hybrid_fitness | strength | 13 | 0 |
| Lu Peng Hybrid Fitness - Metabolic Stren | hybrid_fitness | strength | 11 | 0 |
| Lu Peng Hybrid Fitness - Specific Streng | hybrid_fitness | strength,station | 11 | 0 |
| Lu Peng Hybrid Fitness - Mixed Cardio Tr | hybrid_fitness | running,station | 11 | 136 |
| Lu Peng Hybrid Fitness - Aerobic Interva | hybrid_fitness,run | running,threshold | 5 | 1479 |
| Lu Peng Hybrid Fitness - Anaerobic Inter | hybrid_fitness,run | running,vo2max | 5 | 1336 |
| Lu Peng Hybrid Fitness - Compromised Run | hybrid_fitness | running,station | 22 | 0 |
| Lu Peng Hybrid Fitness - Station Enhance | hybrid_fitness | station,running | 20 | 0 |
| Lu Peng Hybrid Fitness - Doubles Trainin | hybrid_fitness | running,station | 14 | 0 |
| Lu Peng Hybrid Fitness - Burpee Broad Ju | hybrid_fitness | station | 7 | 0 |
| Lu Peng Hybrid Fitness - Farmer's Carry | hybrid_fitness | station | 7 | 0 |
| Lu Peng Hybrid Fitness - Wall Balls | hybrid_fitness | station | 3 | 0 |
| 20 Minute All-Out Ride | cycling | ftp | 3 | 0 |
| Ingebrigtsen Strength Workout | strength | lower_body | 5 | 0 |
| Interval Run | run | vo2max | 9 | 107 |
| Track Pyramid - Short Distance | run | sprint | 23 | 942 |
| Track Pyramid - Middle Distance | run | vo2max | 23 | 922 |
| Kilian's Favorite Uphill Workout | trail_run | threshold | 8 | 0 |
| Hill Intervals | trail_run | base_workout,lower_body | 5 | 584 |
| Hannah Otto Sharp Efforts Cycling Workou | cycling | sprint | 5 | 60 |
| Hannah Otto's Cycling Confidence Builder | cycling | sprint | 6 | 21 |
| MAF180 | run | base_workout | 2 | 91 |
| Long Run | run | base_workout | 7 | 98 |
| 30 Minute Base With Pick Ups | run | base_workout | 5 | 363 |
| 45 Minute Base With Pick Ups | run | base_workout | 5 | 565 |
| 1 Hour Base With Pick Ups | run | base_workout | 5 | 699 |
| Core Strength Routine | strength | core | 6 | 0 |
| Sally McRae's Power 5 Workout | strength | lower_body | 7 | 0 |
| Alex Yee Triathlon Run Workout | run | threshold,vo2max | 7 | 980 |
| Alex Yee Triathlon Bike Workout | cycling | ftp,sprint | 12 | 302 |
| Alex Yee Triathlon Swim Workout | swimming | base_workout,threshold | 12 | 0 |
| Threshold Intervals | run | threshold | 5 | 157 |
| Elite Threshold Workout | run | threshold | 15 | 878 |
| Anaerobic into Threshold Development | cycling | threshold,vo2max,sprint | 8 | 220 |
| 2min VO2 Max Ride - Beginner | cycling | vo2max,sprint | 8 | 49 |
| 4min VO2 Max Ride - Intermediate | cycling | vo2max | 8 | 128 |
| 6min VO2 Max Ride - Advanced | cycling | vo2max | 8 | 102 |
| 1-minute Intervals- Beginner | cycling | vo2max | 9 | 53 |
| 1 min and 2 min Intervals- Advanced | cycling | vo2max | 14 | 100 |
| 1 Minute Intervals+ Hills (Beginner) | run,trail_run | vo2max | 9 | 479 |
| 1 Minute Intervals+Hills (Intermediate/A | run,trail_run | vo2max | 9 | 599 |
| 2 Minute Hill Intervals | trail_run | threshold | 5 | 249 |
| 10-Minute Core Workout | strength | core | 10 | 0 |
| Core Workout | strength,run | core | 23 | 0 |
| Daily Core for Runners | strength,run | core | 7 | 0 |
| Mobility and Core Workout | strength | core | 8 | 0 |
| Core Strength Routine | strength | core | 11 | 0 |
| 3 Minute Fartlek Workout | run | threshold | 5 | 118 |
| 30 Minute Fartlek | run | tempo | 10 | 29 |
| Fartlek Run | run | threshold,vo2max | 16 | 205 |
| Short Interval Fartlek | run | threshold,vo2max | 5 | 60 |
| Fartlek Training for Marathon | run | tempo,threshold | 11 | 71 |
| 5k Pace Intervals- Beginner | run | threshold | 5 | 647 |
| 5k Pace Intervals- Intermediate/Adv | run | vo2max | 5 | 962 |
| 5k Speed Improvement | run | threshold,vo2max | 8 | 696 |
| 60-minute Tempo Ride - Beginner | cycling | tempo | 5 | 153 |
| 90-Minute Tempo Ride - Intermediate | cycling | tempo | 5 | 201 |
| 120-Minute Tempo Ride - Advanced | cycling | tempo | 5 | 301 |
| FTP Intervals- Beginner | cycling | ftp | 9 | 88 |
| FTP Intervals- Intermediate | cycling | ftp | 12 | 91 |
| FTP Intervals- Advanced | cycling | ftp | 13 | 220 |
| Broken Tempo - Beginner | run | tempo | 6 | 77 |
| Broken Tempo - Advanced | run | base_workout | 6 | 123 |
| Broken Tempo - Intermediate | run | tempo | 5 | 98 |
| 800m Speed Workout | run | threshold | 5 | 168 |
| Tabata Running Workout | run | vo2max | 14 | 61 |
| Power Endurance | bouldering | upper_body | 13 | 0 |
| Bouldering 4x4 | bouldering | upper_body | 33 | 0 |
| Bouldering Competition Simulation | bouldering | upper_body | 10 | 0 |
| Bouldering Pyramid | bouldering | upper_body | 33 | 0 |
| Stride Development | strength,run | tempo | 8 | 0 |
| Cadence Drills | strength,run | lower_body | 6 | 0 |
| Cadence Training | strength,run | tempo | 8 | 0 |
| Sprint Intervals- Beginner | cycling | sprint | 12 | 63 |
| Sprint Intervals- Intermediate | cycling | sprint | 12 | 56 |
| Sprint Intervals- Advanced | cycling | sprint | 12 | 53 |
| Beginner Aerobic Power Intervals | run | tempo | 5 | 604 |
| Intermediate/Advanced Aerobic Power Inte | run | tempo | 5 | 906 |
| Beginner Swim Workout | swimming | base_workout | 10 | 0 |
| Single Leg Strength | strength | lower_body | 12 | 0 |
| Effort Pace: Beginner VO2max Development | run | threshold,vo2max | 8 | 609 |
| Effort Pace: Beginner Threshold Developm | run | threshold | 5 | 490 |
| Effort Pace: Advanced VO2max Development | run | vo2max | 12 | 1470 |
| Effort Pace: Advanced Threshold Developm | run | threshold | 11 | 1187 |
| "Feel the Burn" Strength Workout | strength,run | full_body | 32 | 0 |
| Winter Warm-up Routine | strength | full_body | 6 | 0 |
| Dynamic Warm-up | strength,run | full_body | 8 | 0 |
| Abdominal Stabilization Workout | strength | core | 5 | 0 |
| Recovery Run | run | base_workout | 2 | 25 |
| Back to Training - Full Body | strength | full_body | 11 | 0 |
| Progression Run | run | base_workout | 8 | 551 |
| Progression Run - Fast Finish | run | base_workout | 4 | 684 |
| Progressive Onsite Bouldering Workout | bouldering | upper_body | 14 | 0 |
| Progressive onsite Lead Workout | climbing | upper_body | 13 | 0 |
| Cross Training Workout | cycling | tempo | 7 | 91 |
| VO2max Intervals | run | vo2max | 5 | 262 |
| Pyramid Fartlek Run | run | base_workout | 14 | 765 |
| Pyramid Interval Workout | run | threshold | 14 | 147 |
| Pyramid Training | run | threshold | 8 | 183 |
| Inverted Pyramid | run | threshold | 10 | 291 |
| Full Body - Eccentric/Isometric Workout | strength | full_body | 7 | 0 |
| Take a Break from Work to Train | strength | core | 7 | 0 |
| Long Ride for Marathon Training | cycling,run | base_workout | 6 | 430 |
| Endurance Ride - Beginner | cycling | base_workout | 3 | 164 |
| Endurance Ride - Intermediate | cycling | base_workout | 3 | 243 |
| Endurance Ride - Advanced | cycling | base_workout | 3 | 360 |
| Aerobic Endurance Ride | cycling | sprint | 3 | 59 |
| Strength Routine | strength,climbing,bouldering | full_body | 20 | 0 |
| Power Development - Running Specific | strength,run | lower_body | 17 | 0 |
| Strength Development - Running Specific | strength,run | full_body | 26 | 0 |
| Pre-Run Strength Routine | strength,run | full_body | 9 | 0 |
| Post Run Strength Routine | strength,run | full_body | 13 | 0 |
| Hills and Threshold Combo（Beginner） | trail_run | lower_body,threshold,vo2max | 7 | 450 |
| Hills and Threshold Combo (Intermediate/ | trail_run | lower_body,threshold,vo2max | 7 | 653 |
| Hill Strides Beginner | run,trail_run | lower_body,vo2max | 5 | 162 |
| Hill Strides Advanced | run,trail_run | lower_body,vo2max | 9 | 337 |
| Uphill Training | cycling | threshold,vo2max,sprint | 5 | 229 |
| 1:1 Hill Fartlek Workout | run,trail_run | threshold | 9 | 161 |
| Full Body Workout | strength | full_body | 11 | 0 |
| Full Body Strength Workout | strength | full_body | 8 | 0 |
| Uphill Athlete: Killer Core Routine | strength,run,trail_run | full_body | 14 | 0 |
| Uphill Athlete: Strength Routine | strength,run,trail_run | full_body | 18 | 0 |
| Mountain Running Routine | strength,run,trail_run | lower_body,core | 12 | 0 |
| Upper Body Workout | strength | upper_body | 15 | 0 |
| Upper Body Workout | strength | upper_body | 8 | 0 |
| Barehanded Upper-Body Strength | strength | upper_body | 6 | 0 |
| Advanced Upper-Body Strength | strength | upper_body | 5 | 0 |
| Climbing Strength | strength,climbing,bouldering | upper_body | 6 | 0 |
| Doubles Pure Endurance Training | climbing | upper_body | 12 | 0 |
| Speed Play Workout | run | vo2max | 5 | 16 |
| Hip Mobility | strength | lower_body | 13 | 0 |
| Lower Body Workout | strength | lower_body | 8 | 0 |
| Lower-Body Strength Training | strength | lower_body | 6 | 0 |
| Lower-Body Physical Training | strength,run | lower_body | 10 | 0 |
| Downhill Strength Workout | strength,run,trail_run | lower_body | 9 | 0 |
| Eccentric Lower Body | strength | full_body | 10 | 0 |
| Yasso 800s | run | vo2max | 5 | 353 |
| Aerobic Run ending with 30 second Stride | run | base_workout,vo2max | 6 | 410 |
| Aerobic Endurance Run with Strides Inter | run | base_workout,vo2max | 7 | 16 |
| Tempo Trail Workout | trail_run | tempo,vo2max | 5 | 610 |
| Trail Run Fartlek | trail_run | threshold,vo2max | 5 | 458 |
| Beginner Plyometrics | strength | full_body | 20 | 0 |
| Intermediate/Advanced Plyometrics | strength | full_body | 19 | 0 |
| Climbing Hangboard Endurance | strength | full_body | 15 | 0 |
| Bodyweight Tabata Workout | strength | full_body | 13 | 0 |
| Bodyweight - Running Specific | strength,run | full_body | 13 | 0 |

</details>

## 7. Exercise/movement library (coros_dictionary.json)

- Total dictionary entries: **6778**
- Movements with form descriptions (`_desc`): **373**
- Named movements: **482**
- Step labels: **33**, UI strings: **119**
- Full inventory: `exercise_library.json`

## 8. Recorded artifacts

- `COROS_MAP.md` (this) · `catalog_210.json` (all IDs+metadata) · `all_items_inspected.json` (per-item decoded summary) · `exercise_library.json` · `taxonomy_raw.json`

**Enumeration status: COMPLETE.** 210/210 public catalog items recorded and decoded.