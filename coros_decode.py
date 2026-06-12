"""
Shared COROS decoder — single source of truth for all exporters (.ics today,
structured .ZWO/FIT/intervals.icu later).

Turns a `teamapi.coros.com/training/plan/detail` response into a normalized,
sport-agnostic workout model:

    Plan -> [Workout] -> blocks of (Step | RepeatGroup)

Decode tables are the corrected, review-validated ones from
docs/coros_map/COROS_MAP.md §4. Run/bike get full target/intensity detail;
other sports decode structurally (steps + durations) without sport-specific
intensity interpretation.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional, Union

# ---- decode tables (docs/coros_map/COROS_MAP.md §4) ----
SPORT = {1: "Run", 2: "Bike", 3: "Swim", 4: "Strength", 7: "Climb", 9: "Hybrid"}
ROLE = {1: "warmup", 2: "active", 3: "cooldown", 4: "rest"}
INTENSITY_KIND = {0: "none", 1: "weight", 2: "HR", 3: "pace", 5: "swim",
                  7: "HR", 8: "pace", 9: "power", 10: "climb"}
RICH_SPORTS = {"Run", "Bike", "Strength", "Hybrid"}   # full detail rendering


@dataclass
class Target:
    kind: str = "none"          # HR | pace | power | weight | swim | climb | none
    pct_low: float = 0.0        # % of threshold, e.g. 96.0  (0 = no % target)
    pct_high: float = 0.0
    weight_g: int = 0           # strength only
    abs_low: int = 0            # absolute HR (bpm) when no % target
    abs_high: int = 0

    @property
    def is_range(self) -> bool:
        return bool(self.pct_high) and round(self.pct_high, 1) != round(self.pct_low, 1)

    def human(self) -> str:
        if self.kind in ("none", ""):
            return ""
        if self.kind == "weight" and self.weight_g:
            kg = self.weight_g / 1000
            return f"{kg:g} kg" if kg >= 1 else f"{self.weight_g} g"
        if self.pct_low:
            label = {"HR": "HR", "pace": "pace", "power": "power"}.get(self.kind, self.kind)
            if self.is_range:
                return f"{self.pct_low:.0f}–{self.pct_high:.0f}% {label}"
            return f"{self.pct_low:.0f}% {label}"
        # Absolute HR (bpm) — the only absolute target type seen in real data.
        if self.kind == "HR" and self.abs_low:
            if self.abs_high and self.abs_high != self.abs_low:
                return f"{self.abs_low}–{self.abs_high} bpm"
            return f"{self.abs_low} bpm"
        # Other absolute targets (pace/power) have an unclear unit encoding —
        # suppress rather than print a misleading bare "@ pace".
        return ""


@dataclass
class Step:
    role: str                   # warmup | active | rest | cooldown
    name: str
    dur_kind: str               # time | distance | reps | open
    dur_value: int = 0          # seconds | metres | reps | 0
    target: Target = field(default_factory=Target)
    rest_s: int = 0
    sets: int = 1               # strength: number of straight sets
    hold: bool = False          # strength: time target is an isometric hold

    def human_duration(self) -> str:
        if self.dur_kind == "time":
            m, s = divmod(self.dur_value, 60)
            return f"{m}:{s:02d}" if s or not m else f"{m}min"
        if self.dur_kind == "distance":
            km = self.dur_value / 1000
            return f"{km:.2f} km" if km >= 1 else f"{self.dur_value} m"
        if self.dur_kind == "reps":
            return f"{self.dur_value} reps"
        return "open"

    def human(self) -> str:
        # duration / rep token (sets-aware for strength)
        if self.dur_kind == "reps":
            base = f"{self.dur_value} reps" if self.sets <= 1 else f"{self.sets}×{self.dur_value}"
        elif self.dur_kind == "time" and self.hold:
            h = f"{self.dur_value}s" if self.dur_value < 60 else f"{self.dur_value // 60}min"
            base = f"{h} hold" if self.sets <= 1 else f"{self.sets}×{h} hold"
        else:
            base = self.human_duration()
            if self.sets and self.sets > 1:
                base = f"{self.sets}×{base}"
        line = f"{self.name} — {base}"
        t = self.target.human()
        if t:
            line += f" @ {t}"
        if self.rest_s:
            line += f" (rest {self.rest_s}s)"
        return line


@dataclass
class RepeatGroup:
    count: int
    steps: list = field(default_factory=list)


Block = Union[Step, RepeatGroup]


@dataclass
class Workout:
    index: int
    sport: str
    title: str
    id_in_plan: Optional[int] = None
    overview: str = ""
    distance_m: int = 0
    duration_s: int = 0
    training_load: Optional[int] = None
    blocks: list = field(default_factory=list)   # list[Block]

    @property
    def is_rich(self) -> bool:
        return self.sport in RICH_SPORTS


@dataclass
class Plan:
    title: str
    weeks: Optional[int]
    total_days: Optional[int]
    region: int
    workouts: list = field(default_factory=list)


# ---------------- decode ----------------
def _target_from(ex: dict) -> Target:
    it = ex.get("intensityType", 0) or 0
    kind = INTENSITY_KIND.get(it, "none")
    t = Target(kind=kind)
    if kind == "weight":
        t.weight_g = ex.get("intensityValue", 0) or 0
        if not t.weight_g:
            t.kind = "none"      # intensityType=weight but no value -> bodyweight
    # %threshold is present whenever intensityPercent > 0 (the isIntensityPercent
    # flag is set on some sports but absent on others, e.g. run pace).
    if ex.get("intensityPercent"):
        t.pct_low = ex["intensityPercent"] / 1000.0
        ext = ex.get("intensityPercentExtend") or ex["intensityPercent"]
        t.pct_high = ext / 1000.0
    elif kind == "HR" and ex.get("intensityValue"):
        # absolute HR target (bpm), possibly a range via intensityValueExtend
        t.abs_low = int(ex["intensityValue"])
        t.abs_high = int(ex.get("intensityValueExtend") or ex["intensityValue"])
    return t


def _step_from(ex: dict, translate, sport: str = "") -> Step:
    tt = ex.get("targetType")
    tv = ex.get("targetValue", 0) or 0
    if tt == 2:
        dk, dv = "time", int(tv)
    elif tt == 5:
        dk, dv = "distance", int(tv) // 100      # cm -> m
    elif tt == 3:
        dk, dv = "reps", int(tv)
    else:
        dk, dv = "open", 0
    role = ROLE.get(ex.get("exerciseType"), "active")
    name = translate(ex.get("name", "")) or role.replace("warmup", "Warm Up").title()
    is_strength = sport in ("Strength", "Hybrid")
    return Step(role=role, name=name, dur_kind=dk, dur_value=dv,
                target=_target_from(ex), rest_s=int(ex.get("restValue", 0) or 0),
                sets=int(ex.get("sets", 1) or 1),
                hold=bool(is_strength and dk == "time" and role == "active"))


def _blocks_from(exercises: list, translate, sport: str = "") -> list:
    """Build ordered blocks, folding consecutive same-`groupId` members into a
    RepeatGroup. The interval HEADER (isGroup=true) carries the repeat `sets`
    count but NO groupId; its members (which follow it) share a groupId. So we
    latch the header's count and apply it to the next run of equal groupId."""
    blocks: list = []
    cur: Optional[RepeatGroup] = None
    cur_gid = None
    pending_count: Optional[int] = None
    for ex in exercises:
        if ex.get("isGroup"):
            pending_count = ex.get("sets", 1) or 1
            continue
        gid = ex.get("groupId")
        step = _step_from(ex, translate, sport)
        if gid and gid not in ("0", 0):
            if cur is not None and gid == cur_gid:
                cur.steps.append(step)
            else:
                cur = RepeatGroup(count=pending_count or 1, steps=[step])
                cur_gid = gid
                pending_count = None
                blocks.append(cur)
        else:
            cur = None
            cur_gid = None
            pending_count = None
            blocks.append(step)
    # unwrap trivial single-rep groups into plain steps
    out = []
    for b in blocks:
        if isinstance(b, RepeatGroup):
            if not b.steps:
                continue
            if b.count <= 1:
                out.extend(b.steps)
                continue
        out.append(b)
    return out


# COROS shortcode keys look like W30291 / T1120 / TD1030 / P12999 / S4274:
# 1–4 leading capitals then 3+ digits. Real COROS name-codes carry 4–5 digits, so
# requiring 3+ keeps human-authored names that merely look codish — "EMOM12",
# "WOD21", "Z30" (2 digits), "4 mile with strides", "Marathon!" — from matching.
# Used to tell an UNTRANSLATED CODE from an already-readable name.
_SHORTCODE_RE = re.compile(r"^[A-Z]{1,4}\d{3,}$")


def _workout_title(name_key, translate, sport: str, idx: int) -> str:
    """Resolve a workout title, with a graceful fallback for untranslated codes.

    `translate_key` returns the key unchanged on a dictionary miss, so
    `translated == name_key` means "not found in the dictionary". But that alone
    is ambiguous: it's also true for plain-text plan names that were never
    shortcodes (e.g. "4 mile with strides"), which we must KEEP, not clobber.
    So we fall back to "<Sport> Workout" only when the name is BOTH unresolved
    AND shortcode-shaped (e.g. "W30291" — the COROS locale dictionary drifts and
    newer name-codes lag behind our bundle). An unresolved but human-readable
    name is already good; keep it.

    Defensive: COROS sends `name` as a string, but coerce non-strings (a stray
    int/None on malformed data must not crash the whole plan decode), and match
    the shortcode test against the stripped key — COROS data carries codes with
    trailing whitespace (e.g. "E11002\\xa0"), which would otherwise leak raw.
    """
    if not isinstance(name_key, str):
        name_key = ""
    title = translate(name_key)
    if title and title != name_key:
        return title                                   # resolved from dictionary
    key = name_key.strip()
    if key and not _SHORTCODE_RE.match(key):
        return key                                     # unresolved but already readable
    return f"{sport} Workout" if sport else f"Workout {idx + 1}"   # raw code / empty -> fallback


def decode_plan(data: dict, translate) -> Plan:
    """`data` = response['data']; `translate(key)->str` resolves shortcodes."""
    plan = Plan(title=translate(data.get("name", "")) or "COROS Plan",
                weeks=data.get("totalWeeks"), total_days=data.get("totalDay"),
                region=data.get("region", 1))
    for idx, prog in enumerate(data.get("programs", [])):
        st = prog.get("sportType")
        sport = SPORT.get(st, str(st) if st is not None else "")
        exercises = prog.get("exercises", []) or []
        w = Workout(
            index=idx, sport=sport,
            id_in_plan=prog.get("idInPlan"),
            title=_workout_title(prog.get("name", ""), translate, sport, idx),
            overview=translate(prog.get("overview", "")) or "",
            distance_m=int((prog.get("distance") or 0) // 100),
            duration_s=int(prog.get("duration") or 0),
            training_load=prog.get("trainingLoad"),
            blocks=_blocks_from(exercises, translate, sport),
        )
        plan.workouts.append(w)
    return plan


def decode_workout(data: dict, translate) -> Workout:
    """Decode a standalone COROS workout (`teamapi.coros.com/training/program/
    detail` -> response['data']) into a single Workout.

    A workout payload is shaped exactly like one element of a plan's
    `programs[]` (same sportType / name / overview / exercises), just without
    the plan's dated schedule wrapper. So wrap it as a one-program synthetic
    plan and reuse decode_plan — one decode path for plans and workouts, no
    duplicated logic."""
    if not isinstance(data, dict):
        raise ValueError("Unexpected workout payload from COROS (expected an object).")
    synthetic = {"name": data.get("name", ""), "region": data.get("region", 1),
                 "programs": [data]}
    return decode_plan(synthetic, translate).workouts[0]


# ---------------- rendering: rich .ics DESCRIPTION ----------------
def format_description(w: Workout, max_chars: int = 4000, include_summary: bool = True) -> str:
    """Human-readable structured body for an .ics VEVENT DESCRIPTION.

    Rich sports get the full step breakdown with repeats; others get the
    overview only. Set include_summary=False when the caller already prints
    its own Distance/Duration lines (e.g. create_ics_file)."""
    head = []
    summary = []
    if include_summary and w.duration_s:
        m = w.duration_s // 60
        summary.append(f"{m}min")
    if include_summary and w.distance_m:
        summary.append(f"{w.distance_m/1000:.2f} km")
    if include_summary and w.training_load:
        summary.append(f"TL {w.training_load}")
    if summary:
        head.append(" · ".join(summary))
    if w.overview:
        head.append(w.overview)

    body = []
    if w.is_rich and w.blocks:
        body.append("Workout:")
        for b in w.blocks:
            if isinstance(b, RepeatGroup):
                body.append(f"{b.count}×")
                for s in b.steps:
                    body.append(f"   • {s.human()}")
            else:
                body.append(f" • {b.human()}")

    text = "\n".join(head + ([""] if head and body else []) + body).strip()
    if len(text) > max_chars:
        text = text[:max_chars - 1].rstrip() + "…"
    return text
