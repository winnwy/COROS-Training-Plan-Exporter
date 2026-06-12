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
from dataclasses import dataclass, field
from typing import Optional, Union

# ---- decode tables (docs/coros_map/COROS_MAP.md §4) ----
SPORT = {1: "Run", 2: "Bike", 3: "Swim", 4: "Strength", 9: "Hybrid"}
ROLE = {1: "warmup", 2: "active", 3: "cooldown", 4: "rest"}
INTENSITY_KIND = {0: "none", 1: "weight", 2: "HR", 3: "pace", 5: "swim",
                  7: "HR", 8: "pace", 9: "power", 10: "climb"}
RICH_SPORTS = {"Run", "Bike"}   # v1 scope for full intensity rendering


@dataclass
class Target:
    kind: str = "none"          # HR | pace | power | weight | swim | climb | none
    pct_low: float = 0.0        # % of threshold, e.g. 96.0  (0 = no % target)
    pct_high: float = 0.0
    weight_g: int = 0           # strength only

    @property
    def is_range(self) -> bool:
        return self.pct_high and round(self.pct_high, 1) != round(self.pct_low, 1)

    def human(self) -> str:
        if self.kind in ("none", "") :
            return ""
        if self.kind == "weight" and self.weight_g:
            kg = self.weight_g / 1000
            return f"{kg:g} kg" if kg >= 1 else f"{self.weight_g} g"
        if self.pct_low:
            label = {"HR": "HR", "pace": "pace", "power": "power"}.get(self.kind, self.kind)
            if self.is_range:
                return f"{self.pct_low:.0f}–{self.pct_high:.0f}% {label}"
            return f"{self.pct_low:.0f}% {label}"
        return self.kind


@dataclass
class Step:
    role: str                   # warmup | active | rest | cooldown
    name: str
    dur_kind: str               # time | distance | reps | open
    dur_value: int = 0          # seconds | metres | reps | 0
    target: Target = field(default_factory=Target)
    rest_s: int = 0

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
        t = self.target.human()
        line = f"{self.name} — {self.human_duration()}"
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
    # %threshold is present whenever intensityPercent > 0 (the isIntensityPercent
    # flag is set on some sports but absent on others, e.g. run pace).
    if ex.get("intensityPercent"):
        t.pct_low = ex["intensityPercent"] / 1000.0
        ext = ex.get("intensityPercentExtend") or ex["intensityPercent"]
        t.pct_high = ext / 1000.0
    return t


def _step_from(ex: dict, translate) -> Step:
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
    return Step(role=role, name=name, dur_kind=dk, dur_value=dv,
                target=_target_from(ex), rest_s=int(ex.get("restValue", 0) or 0))


def _blocks_from(exercises: list, translate) -> list:
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
        step = _step_from(ex, translate)
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


def decode_plan(data: dict, translate) -> Plan:
    """`data` = response['data']; `translate(key)->str` resolves shortcodes."""
    plan = Plan(title=translate(data.get("name", "")) or "COROS Plan",
                weeks=data.get("totalWeeks"), total_days=data.get("totalDay"),
                region=data.get("region", 1))
    for idx, prog in enumerate(data.get("programs", [])):
        sport = SPORT.get(prog.get("sportType"), str(prog.get("sportType")))
        exercises = prog.get("exercises", []) or []
        w = Workout(
            index=idx, sport=sport,
            id_in_plan=prog.get("idInPlan"),
            title=translate(prog.get("name", "")) or f"Workout {idx+1}",
            overview=translate(prog.get("overview", "")) or "",
            distance_m=int((prog.get("distance") or 0) // 100),
            duration_s=int(prog.get("duration") or 0),
            training_load=prog.get("trainingLoad"),
            blocks=_blocks_from(exercises, translate),
        )
        plan.workouts.append(w)
    return plan


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
