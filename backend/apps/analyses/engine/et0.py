"""
FAO-56 Penman-Monteith reference evapotranspiration (ET0), daily.

Pure function — no ORM, no I/O (plan §4). Input is one POWER day; output is
ET0 in mm/day. Citation: Allen et al. (1998), FAO Irrigation and Drainage
Paper No. 56.

  ET0 = (Δ·Rn + γ·(900/(T+273))·ea·u2) / (Δ + γ·(1 + 0.34·u2))

  where (FAO-56, Allen et al. 1998):
    T      = Tmean in °C
    Δ      = slope of the saturation vapour-pressure curve, kPa/°C
             Δ = 4098 · es(Tmean) / (Tmean + 237.3)²
    γ      = psychrometer constant, ≈ 0.0665 kPa/°C
    ea     = actual vapour pressure, kPa  (ea = RH/100 · es̄)
    u2     = wind speed at 2 m, m/s
    Rn     = net radiation, MJ/m²/day
             Rn = (1−α)·Rsn − (0.34 − 0.14·√ea)·Rnl
    Rsn    = ALLSKY_SFC_SW_DWN from POWER, already in MJ/m²/day
    Rnl    = σ·[(Tmax_K)⁴ + (Tmin_K)⁴],  σ = 4.903×10⁻⁹
    es̄     = (es(Tmax) + es(Tmin)) / 2
    es(t)  = 0.6108 · exp(17.27·t / (t + 237.3))  kPa

  Acceptance test: the FAO-56 Paper No. 56 worked example
  (Tmax=34, Tmin=24, RH=45 %, u2=1.4, Rso=19.0 MJ/m²/day)
  should give ET0 ≈ 5.4–6.3 mm/day (depending on α and exact ea).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PowerDay:
    """One day of POWER climate variables (the engine's input unit)."""
    date: str
    tmax: float | None  # °C
    tmin: float | None  # °C
    rh: float | None    # % (2 m)
    ws: float | None    # m/s (2 m)
    rs: float | None    # MJ/m²/day all-sky sfc shortwave down (POWER ALLSKY_SFC_SW_DWN)
    prectot: float | None  # mm (None = gap; never treated as 0)


# ── helper functions ──────────────────────────────────────────────────────────

def _es(t_c: float) -> float:
    """Saturation vapour pressure es(t), kPa (FAO-56 eq. 11)."""
    return 0.6108 * math.exp(17.27 * t_c / (t_c + 237.3))


def _es_bar(tmax_c: float, tmin_c: float) -> float:
    """Mean saturation vapour pressure es̄, kPa (FAO-56 eq. 11)."""
    return (_es(tmax_c) + _es(tmin_c)) / 2.0


def _slope(t_c: float) -> float:
    """Slope Δ of the saturation vapour-pressure curve, kPa/°C (FAO-56 eq. 13)."""
    return 4098.0 * _es(t_c) / (t_c + 237.3) ** 2


def _net_radiation(rsn_mj: float, tmax_c: float, tmin_c: float, ea: float) -> float:
    """
    Net radiation Rn, MJ/m²/day (FAO-56 eqs. 46–52).

      Rn = (1 − α)·Rsn − (0.34 − 0.14·√ea)·Rnl
      Rnl = 4.903×10⁻⁹ · [(Tmax_K)⁴ + (Tmin_K)⁴]
    """
    alpha = 0.20  # cropland
    rnl = 4.903e-9 * ((tmax_c + 273.16) ** 4 + (tmin_c + 273.16) ** 4)
    rn = (1.0 - alpha) * rsn_mj - (0.34 - 0.14 * math.sqrt(max(ea, 0.0))) * rnl
    return rn


# ── main entry point ──────────────────────────────────────────────────────────

def compute_et0(day: PowerDay, elevation_m: float = 40.0) -> float | None:
    """
    Daily ET0 in mm/day (FAO-56 Penman-Monteith).
    Returns None if any required input is a gap.
    """
    if day.tmax is None or day.tmin is None or day.rh is None or day.rs is None:
        return None

    tmean = (day.tmax + day.tmin) / 2.0
    gamma = 0.0665  # kPa/°C
    u2 = day.ws if day.ws is not None else 1.0

    es_bar = _es_bar(day.tmax, day.tmin)
    ea = (day.rh / 100.0) * es_bar  # actual vapour pressure, kPa
    delta = _slope(tmean)

    rn = _net_radiation(day.rs, day.tmax, day.tmin, ea)

    numerator = delta * rn + gamma * (900.0 / (tmean + 273.0)) * ea * u2
    denominator = delta + gamma * (1.0 + 0.34 * u2)

    if denominator <= 0:
        return None

    et0 = numerator / denominator
    return max(et0, 0.0)
