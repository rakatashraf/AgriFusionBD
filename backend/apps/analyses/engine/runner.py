"""
Engine runner — the single entry point the views/tasks call (plan §4, Phase 4).

    run(field, request, power, hls, catalogue) → {plans, warnings, evidence}

Pure orchestration over the leaf modules. It:
  1. Reconstructs the POWER day list + HLS NDVI from the (frozen) inputs.
  2. Builds the baseline from CropHistory (NEVER invented — plan §4).
  3. Enumerates + hard-filters candidates.
  4. Scores each feasible candidate on the five metrics.
  5. Picks ≤2 materially-different alternatives.
  6. Emits plans, warnings, evidence, and the sensitivity flag.

If fewer than two alternatives are feasible, the run is ``partial`` with
``missing_data`` explaining why — a validity win, not a failure (plan §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import rules
from .candidates import Candidate, CropTraits, enumerate_candidates, pick_alternatives
from .cover import season_canopy_cover
from .diversity import rotation_diversity
from .economics import EconCrop, rotation_economics
from .et0 import PowerDay
from .heat import season_heat
from .score import MetricInput, weighted_score
from .water_balance import season_water_balance


@dataclass
class EngineInput:
    """Everything the engine needs, decoupled from the ORM (plan §4: no ORM)."""
    lat: float
    lng: float
    season: str
    season_months: list[int]
    irrigation: str
    drainage: str
    soil_ph: float | None
    equipment: set[str]
    exclusions: list[str]
    area_ha: float
    weights: dict[str, float]

    power_days: list[PowerDay] = field(default_factory=list)
    ndvi: float | None = None
    ndvi_coverage_pct: float | None = None

    # Catalogue (crop traits for every relevant crop).
    crops: dict[str, CropTraits] = field(default_factory=dict)
    crop_families: dict[str, str] = field(default_factory=dict)
    crop_is_legume: dict[str, bool] = field(default_factory=dict)

    # Baseline: the farmer's actual last rotation (ordered crop slugs).
    baseline_seq: list[str] = field(default_factory=list)
    baseline_is_paddy: bool = False

    soil_test_id: str = ""
    catalogue_version: str = ""
    rule_version: str = rules.RULE_VERSION


def _metrics_for(
    seq: list[str], inp: EngineInput,
) -> tuple[list[MetricInput], dict]:
    """Compute the five metrics for a rotation sequence."""
    # Use the first crop's traits for the season-level water/heat/cover
    # (declared simplification: the season is driven by the lead crop).
    lead = inp.crops.get(seq[0])
    if lead is None:
        return [], {}

    # Water efficiency → irrigation demand (lower is better).
    wb = season_water_balance(
        inp.power_days, lead.kc_canopy, inp.irrigation, inp.drainage,
        is_paddy=(lead.is_paddy or (seq[0] in inp.baseline_seq and inp.baseline_is_paddy)),
    )
    water = MetricInput("water_efficiency", wb.irrigation_demand_mm, wb.qualification)

    # Heat resilience → threshold days (lower is better).
    heat = season_heat(inp.power_days, lead.heat_tolerance)
    heat_m = MetricInput("heat_resilience", heat.threshold_days, heat.qualification)

    # Canopy cover → fraction (higher is better).
    cover = season_canopy_cover(rules.DEFAULT_CANOPY_FRACTION, inp.ndvi, inp.ndvi_coverage_pct)
    cover_m = MetricInput("canopy_cover", cover.fraction, cover.qualification)

    # Diversity → composite (higher is better).
    div = rotation_diversity(seq, inp.crop_families, inp.crop_is_legume)
    div_m = MetricInput("diversity", div.score, div.qualification)

    # Net margin → mid of the range (higher is better).
    econ_crops = []
    for slug in seq:
        c = inp.crops.get(slug)
        if c:
            econ_crops.append(EconCrop(
                slug=slug,
                yield_low_t=c.yield_low_t, yield_high_t=c.yield_high_t,
                price_low=c.price_low, price_high=c.price_high,
                cost_low=c.cost_low, cost_high=c.cost_high,
                area_ha=inp.area_ha,
            ))
    econ = rotation_economics(econ_crops)
    mid_margin = (econ.net_margin_low + econ.net_margin_high) / 2.0
    margin_m = MetricInput("net_margin", mid_margin,
                           f"{econ.qualification} Range: {econ.net_margin_low:,.0f}–{econ.net_margin_high:,.0f} BDT/ha.")

    details = {
        "water": wb, "heat": heat, "cover": cover,
        "diversity": div, "economics": econ,
    }
    return [water, heat_m, cover_m, div_m, margin_m], details


def run(inp: EngineInput) -> dict:
    """
    Run the engine. Returns a dict with:
      status: "complete" | "partial"
      plans:  [{name, isBaseline, feasible, reasons, score, seq, metrics[], ...}]
      warnings: [str]
      evidence: {power, hls, soil, rule_version, catalogue_version, ...}
      sensitivity_flip: bool
    """
    warnings: list[str] = []
    missing: list[str] = []

    # --- Baseline (NEVER invented) -----------------------------------------
    if not inp.baseline_seq:
        warnings.append("No crop history for this field — baseline could not be established.")
        missing.append("crop_history")
    baseline_is_paddy = inp.baseline_is_paddy or any(
        inp.crops.get(s, CropTraits(slug=s, name=s, family="", is_legume=False,
                                    water_demand_mm=0, kc_canopy=1.0, heat_tolerance="moderate",
                                    drought_tolerance="moderate", price_low=0, price_high=0,
                                    cost_low=0, cost_high=0, yield_low_t=0, yield_high_t=0)).is_paddy
        for s in inp.baseline_seq
    )

    # --- Enumerate + filter candidates --------------------------------------
    crops_list = list(inp.crops.values())
    candidates = enumerate_candidates(
        crops_list,
        season_months=inp.season_months,
        field_irrigation=inp.irrigation,
        soil_ph=inp.soil_ph,
        equipment=inp.equipment,
        exclusions=inp.exclusions,
        baseline_seq=inp.baseline_seq,
    )
    feasible = [c for c in candidates if c.feasible == "feasible"]
    if not feasible:
        warnings.append("No crop in the catalogue passes the hard filters for this season/field.")
        missing.append("feasible_crop")

    # --- Score every feasible candidate -------------------------------------
    scored: list[dict] = []
    metric_inputs_by_seq: dict[str, list[MetricInput]] = {}
    for cand in feasible:
        metrics, details = _metrics_for(cand.slug_seq, inp)
        if not metrics:
            continue
        sc = weighted_score(metrics, inp.weights)
        key = "|".join(cand.slug_seq)
        metric_inputs_by_seq[key] = metrics
        scored.append({
            "cand": cand,
            "score": sc.score,
            "normalized": sc.normalized,
            "contributions": sc.contributions,
            "details": details,
            "metrics": metrics,
            "key": key,
        })

    scored.sort(key=lambda s: s["score"], reverse=True)

    # --- Baseline plan entry ------------------------------------------------
    plans: list[dict] = []
    if inp.baseline_seq:
        b_metrics, b_details = _metrics_for(inp.baseline_seq, inp)
        b_sc = weighted_score(b_metrics, inp.weights) if b_metrics else None
        plans.append(_plan_entry(
            name="Baseline (your current rotation)",
            is_baseline=True,
            seq=inp.baseline_seq,
            feasible="feasible",
            reasons=["Built from your crop history — never invented."],
            score=b_sc.score if b_sc else None,
            metrics=b_metrics,
            details=b_details,
            inp=inp,
        ))

    # --- Pick ≤2 alternatives ----------------------------------------------
    alt_candidates = [
        Candidate(slug_seq=[s for s in x["cand"].slug_seq]) for x in scored
    ]
    alt_candidates = [c for c in alt_candidates if c.slug_seq != inp.baseline_seq]
    scores_by_key = {x["key"]: x["score"] for x in scored}
    picks = pick_alternatives(alt_candidates, inp.crops, inp.baseline_seq, scores_by_key)

    for p in picks:
        key = "|".join(p.slug_seq)
        x = next((s for s in scored if s["key"] == key), None)
        if x is None:
            continue
        plans.append(_plan_entry(
            name=f"Alternative: {' + '.join((getattr(inp.crops.get(s), 'name', s) if inp.crops.get(s) else s) for s in p.slug_seq)}",
            is_baseline=False,
            seq=p.slug_seq,
            feasible=p.feasible,
            reasons=p.reasons or ["Materially different family from baseline."],
            score=x["score"],
            metrics=x["metrics"],
            details=x["details"],
            inp=inp,
        ))

    # --- Status + sensitivity ----------------------------------------------
    status = "complete"
    if len(plans) < 3:  # baseline + <2 alternatives
        status = "partial"
        if not inp.baseline_seq:
            missing.append("baseline_rotation")
        if len([p for p in plans if not p["isBaseline"]]) < 2:
            missing.append("feasible_alternatives")
            warnings.append(
                "Fewer than two feasible, materially-different alternatives could be "
                "supported by the evidence for this season. See missing_data for why."
            )

    # Sensitivity: do the scored alternatives flip under a small weight nudge?
    from .score import ScoredPlan, sensitivity_flip
    sp_list = [ScoredPlan(seq_key=x["key"], score=x["score"]) for x in scored]
    flip = sensitivity_flip(sp_list, inp.weights, metric_inputs_by_seq) if len(scored) >= 2 else False

    # --- Evidence + provenance ---------------------------------------------
    evidence = {
        "power": {
            "days": len(inp.power_days),
            "stale": False,
            "gap_days": sum(1 for d in inp.power_days if d.prectot is None),
        },
        "hls": {
            "ndvi": inp.ndvi,
            "coverage_pct": inp.ndvi_coverage_pct,
            "source": "observed" if (inp.ndvi is not None and (inp.ndvi_coverage_pct or 0) >= rules.HLS_COVERAGE_FLOOR * 100) else "inferred",
        },
        "soil": {"test_id": inp.soil_test_id, "ph": inp.soil_ph},
        "rule_version": inp.rule_version,
        "catalogue_version": inp.catalogue_version,
        "sensitivity_flip": flip,
    }

    return {
        "status": status,
        "plans": plans,
        "warnings": warnings,
        "evidence": evidence,
        "missing_data": missing,
        "rule_version": inp.rule_version,
    }


def _plan_entry(name, is_baseline, seq, feasible, reasons, score, metrics, details, inp) -> dict:
    metric_out = []
    for m in metrics:
        from .score import normalize
        metric_out.append({
            "key": m.key,
            "rawValue": round(m.raw_value, 3),
            "normalized": round(normalize(m.key, m.raw_value), 4),
            "weight": inp.weights.get(m.key, 0.0),
            "qualification": m.qualification,
        })
    return {
        "name": name,
        "isBaseline": is_baseline,
        "feasible": feasible,
        "reasons": reasons,
        "score": round(score, 4) if score is not None else None,
        "seq": seq,
        "crops": [
            {
                "slug": s,
                "name": getattr(inp.crops.get(s), "name", s) if inp.crops.get(s) else s,
                "family": inp.crop_families.get(s, ""),
                "isLegume": inp.crop_is_legume.get(s, False),
            }
            for s in seq
        ],
        "metrics": metric_out,
        "economics": details.get("economics", {}).per_crop if details.get("economics") else [],
    }
