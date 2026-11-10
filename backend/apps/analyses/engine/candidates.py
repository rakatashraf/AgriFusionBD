"""
Candidate rotation enumeration + hard filters (plan §4, Phase 4).

Pure function. Enumerates candidate rotations from the reviewed calendars and
applies the farmer's hard constraints. A candidate that fails a hard filter is
``infeasible``; one that passes with a warning is ``constrained``; otherwise
``feasible``. Capped at MAX_CANDIDATES (plan §4).

Hard filters (plan §4):
  - season overlap (calendar windows must fit the requested season),
  - irrigation limit (crop must be runnable under the field's irrigation),
  - soil range (pH within the crop's bounds, if known),
  - equipment (crop must not require equipment the farmer lacks),
  - farmer exclusions (crops the farmer explicitly excluded).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import rules


@dataclass
class CropTraits:
    """The crop subset the engine needs (decoupled from the ORM Crop)."""
    slug: str
    name: str
    family: str
    is_legume: bool
    water_demand_mm: int
    kc_canopy: float
    heat_tolerance: str
    drought_tolerance: str
    price_low: float
    price_high: float
    cost_low: float
    cost_high: float
    yield_low_t: float
    yield_high_t: float
    soil_ph_min: float | None = None
    soil_ph_max: float | None = None
    irrigation_max: str = ""
    equipment: list[str] = field(default_factory=list)
    season_months: list[int] = field(default_factory=list)
    is_paddy: bool = False


@dataclass
class Candidate:
    slug_seq: list[str]  # ordered crop slugs (one per season slot)
    feasible: str = "feasible"  # feasible | constrained | infeasible
    reasons: list[str] = field(default_factory=list)


def _fits_season(crop: CropTraits, season_months: list[int]) -> bool:
    if not crop.season_months:
        return True
    return any(m in season_months for m in crop.season_months)


def _irrigation_ok(crop: CropTraits, field_irrigation: str) -> bool:
    if not crop.irrigation_max:
        return True
    # Rainfed crops need rainfed; canal/drip crops are fine on canal/drip.
    return crop.irrigation_max == field_irrigation or field_irrigation in ("canal", "drip")


def _soil_ok(crop: CropTraits, ph: float | None) -> bool:
    if ph is None or (crop.soil_ph_min is None and crop.soil_ph_max is None):
        return True
    if crop.soil_ph_min is not None and ph < crop.soil_ph_min:
        return False
    if crop.soil_ph_max is not None and ph > crop.soil_ph_max:
        return False
    return True


def _equipment_ok(crop: CropTraits, available: set[str]) -> bool:
    if not crop.equipment:
        return True
    return all(e in available for e in crop.equipment)


def enumerate_candidates(
    crops: list[CropTraits],
    *,
    season_months: list[int],
    field_irrigation: str,
    soil_ph: float | None,
    equipment: set[str],
    exclusions: list[str],
    baseline_seq: list[str] | None,
) -> list[Candidate]:
    """
    Produce up to MAX_CANDIDATES feasible rotations.

    The pilot enumerates single-crop and two-crop (break-crop) sequences that
    pass the hard filters, then marks those materially different from the
    baseline as alternatives (≥1 different family, per rules).
    """
    excluded = set(exclusions)
    eligible = [c for c in crops if c.slug not in excluded]

    candidates: list[Candidate] = []

    def check(crop: CropTraits) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        ok = True
        if not _fits_season(crop, season_months):
            ok = False
            reasons.append(f"{crop.name} not suited to this season window")
        if not _irrigation_ok(crop, field_irrigation):
            ok = False
            reasons.append(f"{crop.name} needs different irrigation")
        if not _soil_ok(crop, soil_ph):
            ok = False
            reasons.append(f"{crop.name} outside soil pH range")
        if not _equipment_ok(crop, equipment):
            ok = False
            reasons.append(f"{crop.name} requires unavailable equipment")
        return ok, reasons

    # Single-crop rotations.
    for c in eligible:
        ok, reasons = check(c)
        if ok:
            candidates.append(Candidate([c.slug], "feasible", []))
        else:
            candidates.append(Candidate([c.slug], "infeasible", reasons))

    # Two-crop break-crop rotations (c1 then c2), distinct families preferred.
    for c1 in eligible:
        for c2 in eligible:
            if c1.slug == c2.slug:
                continue
            ok1, r1 = check(c1)
            ok2, r2 = check(c2)
            if ok1 and ok2:
                candidates.append(Candidate([c1.slug, c2.slug], "feasible", []))
            else:
                candidates.append(Candidate([c1.slug, c2.slug], "infeasible", r1 + r2))
            if len(candidates) >= rules.MAX_CANDIDATES:
                break
        if len(candidates) >= rules.MAX_CANDIDATES:
            break

    return candidates[: rules.MAX_CANDIDATES]


def pick_alternatives(
    candidates: list[Candidate],
    crops_by_slug: dict[str, CropTraits],
    baseline_seq: list[str],
    scores: dict[str, float],  # key = "|".join(slug_seq) → weighted score
) -> list[Candidate]:
    """
    Choose up to two feasible alternatives, each materially different from the
    baseline (≥1 different family), ranked by weighted score (plan §4).

    Returns the top two, or fewer if evidence is thin.
    """
    baseline_families = {crops_by_slug[s].family for s in baseline_seq if s in crops_by_slug}

    def is_different(seq: list[str]) -> bool:
        seq_fams = {crops_by_slug[s].family for s in seq if s in crops_by_slug}
        differing = seq_fams - baseline_families
        return len(differing) >= rules.MIN_DIFFERING_FAMILIES

    feasible = [
        c for c in candidates
        if c.feasible == "feasible" and is_different(c.slug_seq)
    ]
    feasible.sort(key=lambda c: scores.get("|".join(c.slug_seq), -1), reverse=True)

    # De-duplicate by crop *multiset*: "Rice + Mustard" and "Mustard + Rice"
    # are the same rotation reversed, so only the first (higher-scored) is kept.
    picked: list[Candidate] = []
    seen_sets: set[frozenset] = set()
    for c in feasible:
        fs = frozenset(c.slug_seq)
        if fs in seen_sets:
            continue
        picked.append(c)
        seen_sets.add(fs)
        if len(picked) == 2:
            break
    return picked
