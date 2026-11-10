"""
Engine tests (plan §6) — pure-function, no DB required.

Covers:
  - determinism: same frozen inputs → identical output (hashable),
  - baseline never invented (empty history → partial, no fabricated baseline),
  - exclusions respected (excluded crop never appears in a plan),
  - insufficient-evidence path (< 2 feasible → status="partial"),
  - no zero-fill of missing rainfall (a gap day is None, not 0).
"""

import hashlib
import json

import pytest

from apps.analyses.engine import rules
from apps.analyses.engine.candidates import CropTraits
from apps.analyses.engine.et0 import PowerDay, compute_et0
from apps.analyses.engine.runner import EngineInput, run


def _crop(slug, family="Poaceae", legume=False, kc=1.1, heat="moderate",
          price=(15, 25), cost=(50000, 70000), yld=(2.0, 4.0), months=(12, 1, 2, 3)):
    return CropTraits(
        slug=slug, name=slug.title(), family=family, is_legume=legume,
        water_demand_mm=400, kc_canopy=kc, heat_tolerance=heat, drought_tolerance="moderate",
        price_low=price[0], price_high=price[1], cost_low=cost[0], cost_high=cost[1],
        yield_low_t=yld[0], yield_high_t=yld[1],
        irrigation_max="", equipment=[], season_months=list(months),
        is_paddy=(slug == "rice-boro"),
    )


def _input(crops, baseline, weights=None, exclusions=None, power_days=None,
           soil_ph=6.4, ndvi=0.7, ndvi_cov=88.0):
    crops_map = {c.slug: c for c in crops}
    return EngineInput(
        lat=25.34, lng=88.61, season="boro", season_months=[12, 1, 2, 3],
        irrigation="canal", drainage="moderate", soil_ph=soil_ph,
        equipment=set(), exclusions=exclusions or [], area_ha=2.0,
        weights=weights or dict(rules.DEFAULT_WEIGHTS),
        power_days=power_days or _power_days(),
        ndvi=ndvi, ndvi_coverage_pct=ndvi_cov,
        crops=crops_map,
        crop_families={c.slug: c.family for c in crops},
        crop_is_legume={c.slug: c.is_legume for c in crops},
        baseline_seq=baseline, baseline_is_paddy=("rice-boro" in baseline),
        soil_test_id="st-1", catalogue_version="v2026.11.0",
        rule_version=rules.RULE_VERSION,
    )


def _power_days(n=20):
    return [
        PowerDay(date=f"2026-01-{d:02d}", tmax=28.0 + (d % 5), tmin=14.0,
                 rh=70.0, ws=2.0, rs=220.0, prectot=(0.0 if d % 4 else 12.0))
        for d in range(1, n + 1)
    ]


def _result_hash(result: dict) -> str:
    # Drop only the timestamps-adjacent fields; the score/plans/evidence must
    # be byte-identical for identical inputs.
    stable = {
        "status": result["status"],
        "plans": result["plans"],
        "warnings": result["warnings"],
        "evidence": {k: v for k, v in result["evidence"].items() if k != "generatedAt"},
        "rule_version": result["rule_version"],
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True, default=str).encode()).hexdigest()


def test_determinism_same_inputs_same_output():
    crops = [_crop("rice-boro"), _crop("wheat", family="Poaceae"), _crop("mustard", family="Brassicaceae")]
    a = run(_input(crops, baseline=["rice-boro"]))
    b = run(_input(crops, baseline=["rice-boro"]))
    assert _result_hash(a) == _result_hash(b), "Engine is not deterministic"


def test_baseline_never_invented_without_history():
    crops = [_crop("wheat"), _crop("mustard", family="Brassicaceae")]
    result = run(_input(crops, baseline=[]))  # no history
    baselines = [p for p in result["plans"] if p["isBaseline"]]
    assert baselines == [], "Baseline must not be invented when there is no history"
    # And the run is partial (validity win), not a fabricated complete.
    assert result["status"] == "partial"
    assert "crop_history" in result.get("missing_data", []) or \
           "baseline_rotation" in result.get("missing_data", [])


def test_exclusions_respected():
    crops = [_crop("wheat"), _crop("mustard", family="Brassicaceae"), _crop("maize")]
    result = run(_input(crops, baseline=["wheat"], exclusions=["maize"]))
    for plan in result["plans"]:
        assert "maize" not in plan["seq"], f"Excluded crop 'maize' appeared in {plan['name']}"


def test_insufficient_evidence_path():
    # Only one crop exists → at most one alternative (baseline + 1) → partial.
    crops = [_crop("wheat")]
    result = run(_input(crops, baseline=["wheat"]))
    alternates = [p for p in result["plans"] if not p["isBaseline"]]
    assert len(alternates) < 2
    assert result["status"] == "partial"
    assert any("alternatives" in m or "feasible" in m for m in result.get("missing_data", []))


def test_no_zero_fill_missing_rainfall():
    # A day with prectot=None must not be treated as 0 mm in the water balance.
    from apps.analyses.engine.water_balance import season_water_balance
    days = [
        PowerDay(date="2026-01-01", tmax=28, tmin=14, rh=70, ws=2, rs=220, prectot=None),
        PowerDay(date="2026-01-02", tmax=28, tmin=14, rh=70, ws=2, rs=220, prectot=10.0),
    ]
    res = season_water_balance(days, kc_canopy=1.1, irrigation="canal",
                               drainage="moderate", is_paddy=False)
    # Gap day is counted, and the qualification mentions uncertainty (not 0).
    assert res.gap_days >= 1
    assert "uncertainty" in res.qualification or "not zero" in res.qualification


def test_metric_raw_and_qualification_present():
    crops = [_crop("rice-boro"), _crop("wheat"), _crop("mustard", family="Brassicaceae")]
    result = run(_input(crops, baseline=["rice-boro"]))
    baseline_plan = next(p for p in result["plans"] if p["isBaseline"])
    for m in baseline_plan["metrics"]:
        assert "rawValue" in m, "Metric missing raw_value (plan §4)"
        assert "qualification" in m and m["qualification"], "Metric missing qualification (plan §4)"


def test_rule_version_stamped():
    crops = [_crop("rice-boro"), _crop("wheat")]
    result = run(_input(crops, baseline=["rice-boro"]))
    assert result["rule_version"] == rules.RULE_VERSION
    assert result["evidence"]["rule_version"] == rules.RULE_VERSION


def test_et0_returns_none_on_gap():
    day = PowerDay(date="2026-01-01", tmax=None, tmin=14, rh=70, ws=2, rs=220, prectot=0)
    assert compute_et0(day) is None


def test_no_ml_in_scoring_path():
    """Sanity: the scoring path is a pure weighted sum, no model inference."""
    from apps.analyses.engine import score
    import inspect
    src = inspect.getsource(score)
    # The module must not import any ML framework.
    for banned in ("sklearn", "torch", "tensorflow", "keras", "onnx", "lightgbm"):
        assert banned not in src, f"Scoring path imports a ML framework: {banned}"


def test_alternatives_not_reversed_duplicates():
    """
    plan §4: the two alternatives must be genuinely distinct — not the same
    two-crop rotation returned in reversed order ("Rice + Mustard" vs
    "Mustard + Rice").
    """
    from apps.analyses.engine.candidates import Candidate, pick_alternatives

    rice = _crop("rice-boro", "Poaceae")  # _crop sets is_paddy for rice-boro
    mustard = _crop("mustard", "Brassicaceae")
    wheat = _crop("wheat", "Poaceae")
    crops = {rice.slug: rice, mustard.slug: mustard, wheat.slug: wheat}

    # A candidate pool containing the same rotation in both orders, plus one
    # genuinely different alternative.
    cands = [
        Candidate(["rice-boro", "mustard"], "feasible", []),
        Candidate(["mustard", "rice-boro"], "feasible", []),  # reversed duplicate
        Candidate(["wheat", "mustard"], "feasible", []),      # genuinely different
    ]
    scores = {"rice-boro|mustard": 0.5, "mustard|rice-boro": 0.5, "wheat|mustard": 0.45}

    picks = pick_alternatives(cands, crops, baseline_seq=["rice-boro"], scores=scores)
    sets = [frozenset(p.slug_seq) for p in picks]
    # No two picks may share the same crop multiset.
    assert len(sets) == len(set(sets)), (
        f"Alternatives contain a reversed duplicate: {[sorted(s) for s in sets]}"
    )
    assert len(picks) <= 2
