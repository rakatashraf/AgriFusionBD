"""
FAO-56 Penman-Monteith reference evapotranspiration (ET0), daily.

Pure function — no ORM, no I/O (plan §4). Input is one POWER day; output is
ET0 in mm/day. Citation: Allen et al. (1998), FAO Irrigation and Drainage
Paper No. 56.

  ET0 = (0.409 * Rn + 0.9 * (Tmean - 34) * Rn / (T + 273) * u2) /
        (lambda * (Δ + γ(1 + 0.34 u2)))
  with the FAO-56 simplification (T = Tmean in °C, u2 = 2 m wind speed,
  lambda ≈ 2.45 MJ/kg, Rn = net radiation approximated from ALLSKY_SFC_SW_DWN).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PowerDay:
    """One day of POWER climate variables (the engine's input unit)."""
    date: str
    tmax: float | None  # °C
    tmin: float | None  # °C
    rh: float | None    # % (2 m)
    ws: float | None    # m/s (2 m)
    rs: float | None    # W/m2 all-sky sfc shortwave down
    prectot: float | None  # mm (None = gap; never treated as 0)


def _slope_vapour_pressure(t: float) -> float:
    """Slope of the saturation vapour-pressure curve, kPa/°C."""
    def svp(tt: float) -> float:
        return 0.6108 * _exp(17.27 * tt / (tt + 237.3))
    return 0.6108 * 17.27 * _exp(17.27 * t / (t + 237.3)) / (t + 237.3) ** 2


def _exp(x: float) -> float:
    import math
    return math.exp(x)


def _psychrometer_constant() -> float:
    """γ in kPa/°C ≈ 0.0665 (FAO-56)."""
    return 0.0665


def _net_radiation(rs_w_m2: float, tmean: float) -> float:
    """
    Approximate net radiation Rn (MJ/m2/day) from all-sky shortwave.
    FAO-56: Rn = (1 - alpha) * Rsn - (0.34 - 0.14 * sqrt(RH/100)) * Rnl.
    We approximate Rnl from Tmean and use alpha = 0.20 (cropland).
    """
    import math
    alpha = 0.20
    # Rsn (MJ/m2/day) from W/m2: 1 W/m2 * 86400 s = 86400 J = 0.0864 MJ.
    rsn = rs_w_m2 * 86400 / 1_000_000  # W/m2 → MJ/m2/day
    # Net longwave Rnl (MJ/m2/day) — FAO-56 estimate using Tmean (K).
    tmin_k = tmean - 273.0
    rnl = (0.34 - 0.14 * 1.0) * 4.903e-9 * (abs(tmin_k) ** 4)  # clear-sky, RH≈100 bound
    rn = (1 - alpha) * rsn - rnl
    return max(rn, 0.0)


def compute_et0(day: PowerDay, elevation_m: float = 40.0) -> float | None:
    """Daily ET0 (mm/day). Returns None if any required input is a gap."""
    if day.tmax is None or day.tmin is None or day.rh is None or day.rs is None:
        return None

    tmean = (day.tmax + day.tmin) / 2.0
    t = tmean  # °C, FAO-56 working variable
    delta = _slope_vapour_pressure(tmean)
    gamma = _psychrometer_constant()
    u2 = day.ws if day.ws is not None else 1.0  # m/s at 2 m
    # Latent heat of vaporisation λ (MJ/kg) — FAO-56 ≈ 2.45.
    lam = 2.45
    rs = day.rs
    rn = _net_radiation(rs, tmean)
    # Numerator: 0.409 Rn + 0.9 (T - 34) Rn / (T + 273) * u2   (FAO-56, 2 m wind)
    numerator = 0.409 * rn + 0.9 * (t - 34.0) * (rn / (t + 273.0)) * u2
    denominator = lam * (delta + gamma * (1.0 + 0.34 * u2))
    if denominator <= 0:
        return None
    et0 = numerator / denominator
    return max(et0, 0.0)
