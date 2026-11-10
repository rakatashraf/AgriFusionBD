"""
Crop-rotation diversity score (plan §4, Phase 4).

Pure function. Based on Tiemann et al. (2015): rotations with more unique
plant families and at least one legume show higher yield stability. We score:
  - unique family count (capped at MAX_FAMILIES),
  - legume inclusion bonus,
  - break-crop vs the last two seasons (no immediate repetition).

The result is a 0..1 composite with a qualification sentence.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import rules


@dataclass
class DiversityResult:
    score: float  # 0..1
    unique_families: int
    has_legume: bool
    repeated_crop: bool
    qualification: str = ""


def rotation_diversity(
    crop_slugs: list[str],
    crop_families: dict[str, str],
    crop_is_legume: dict[str, bool],
    last_two_seasons: list[str] | None = None,
) -> DiversityResult:
    """Score diversity for a candidate rotation (ordered crop slugs)."""
    families = {crop_families.get(s, "") for s in crop_slugs if s in crop_families}
    families.discard("")
    unique = len(families)
    has_legume = any(crop_is_legume.get(s, False) for s in crop_slugs)
    # Repetition: same crop in consecutive positions.
    repeated = any(crop_slugs[i] == crop_slugs[i + 1] for i in range(len(crop_slugs) - 1))
    # Break-crop: does the rotation differ from the last two seasons?
    break_bonus = 0.0
    if last_two_seasons:
        flat_last = set(last_two_seasons)
        flat_new = set(crop_slugs)
        if flat_new != flat_last:
            break_bonus = 0.10

    family_score = min(unique, rules.MAX_FAMILIES) / rules.MAX_FAMILIES
    legume_score = rules.LEGUME_BONUS if has_legume else 0.0
    raw = family_score + legume_score + break_bonus
    # Cap the repetition penalty: immediate repetition halves the score.
    if repeated:
        raw *= 0.5
    score = max(0.0, min(1.0, raw))

    qualification = (
        f"{unique} unique family(ies)"
        + (", includes a legume" if has_legume else "")
        + (", crop repeated in sequence (penalised)" if repeated else "")
        + ("; break-crop from last 2 seasons" if break_bonus else "")
        + ". Basis: Tiemann et al. (2015)."
    )
    return DiversityResult(
        score=score,
        unique_families=unique,
        has_legume=has_legume,
        repeated_crop=repeated,
        qualification=qualification,
    )
