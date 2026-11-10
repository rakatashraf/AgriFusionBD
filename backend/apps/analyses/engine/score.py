"""
Metric normalization + weighted scoring + sensitivity (plan §4, Phase 4).

Pure function. Each metric is normalized to [0,1] against the declared bounds
in ``rules.BOUNDS`` (direction-aware), then combined as ``Σ wᵢ sᵢ / Σ wᵢ``.
Feasibility and its reasons are **independent of the weights** (plan §4): a
weight slider can change the ranking but never a hard-filter outcome.

Sensitivity: re-run the weighted sum with each weight nudged by
``SENSITIVITY_WEIGHT_DELTA`` and report whether the preferred plan flips
(plan §4: "expose whether small weight changes flip the preferred plan").
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import rules


@dataclass
class MetricInput:
    key: str
    raw_value: float
    qualification: str = ""


@dataclass
class ScoredPlan:
    seq_key: str
    score: float
    contributions: dict[str, float] = field(default_factory=dict)
    normalized: dict[str, float] = field(default_factory=dict)


def normalize(key: str, raw_value: float) -> float:
    """Normalize a raw metric value to [0,1] using the declared bounds."""
    b = rules.BOUNDS.get(key)
    if b is None:
        return 0.0
    lo, hi = b["min"], b["max"]
    if hi == lo:
        return 0.0
    t = (raw_value - lo) / (hi - lo)
    t = max(0.0, min(1.0, t))
    if b["direction"] == "lower_is_better":
        return 1.0 - t
    return t


def weighted_score(metrics: list[MetricInput], weights: dict[str, float]) -> ScoredPlan:
    """Combine normalized metrics with Σ wᵢ sᵢ / Σ wᵢ."""
    total_w = 0.0
    total_ws = 0.0
    contributions: dict[str, float] = {}
    normalized: dict[str, float] = {}
    for m in metrics:
        s = normalize(m.key, m.raw_value)
        normalized[m.key] = s
        w = weights.get(m.key, 0.0)
        contributions[m.key] = w * s
        total_w += w
        total_ws += w * s
    score = (total_ws / total_w) if total_w > 0 else 0.0
    return ScoredPlan(seq_key="", score=score, contributions=contributions, normalized=normalized)


def sensitivity_flip(
    plans: list[ScoredPlan],
    weights: dict[str, float],
    metric_inputs_by_seq: dict[str, list[MetricInput]],
) -> bool:
    """
    True if nudging any single weight by SENSITIVITY_WEIGHT_DELTA changes
    which plan ranks first (plan §4). Used to surface ranking stability.
    """
    if len(plans) < 2:
        return False
    current_best = max(plans, key=lambda p: p.score)

    for key in rules.METRIC_KEYS:
        if weights.get(key, 0.0) <= 0:
            continue
        perturbed = dict(weights)
        delta = rules.SENSITIVITY_WEIGHT_DELTA
        if perturbed[key] - delta < 0:
            continue
        perturbed[key] -= delta
        # Re-score all plans under the perturbed weights.
        re_scored = []
        for p in plans:
            re_scored.append(weighted_score(metric_inputs_by_seq[p.seq_key], perturbed))
        new_best = max(re_scored, key=lambda p: p.score)
        if new_best.seq_key != current_best.seq_key:
            return True
    return False
