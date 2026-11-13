"""Repair PRECTOTCORR in the local POWER CSVs.

Finding (verified 2026-11-11): in every file under
API_NASA_POWER/src/data_accusition/bangladesh_weather, PRECTOTCORR is exactly
24x the value NASA POWER returns for the same point and day. The other seven
parameters match the live API exactly. 40 samples across all 7 regions and 10
dates all gave a ratio of 24.00, so the factor is a constant, not noise.

This script writes corrected copies to Data/power_corrected/ and leaves the
original files untouched. Re-run after any re-download.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
SRC = BASE.parent / "API_NASA_POWER" / "src" / "data_accusition" / "bangladesh_weather"
OUT = BASE / "power_corrected"
FACTOR = 24.0
PARAMS = ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN", "PS"]


def main() -> int:
    OUT.mkdir(exist_ok=True)
    files = sorted(SRC.glob("*_20220101_to_*.csv"))
    files = [f for f in files if "units" not in f.name]
    if not files:
        print(f"no POWER csvs in {SRC}")
        return 1

    rows = []
    for path in files:
        df = pd.read_csv(path)
        if "PRECTOTCORR" not in df.columns:
            continue
        before_sum = float(df["PRECTOTCORR"].sum())
        before_max = float(df["PRECTOTCORR"].max())
        df["PRECTOTCORR_raw"] = df["PRECTOTCORR"]
        df["PRECTOTCORR"] = df["PRECTOTCORR"] / FACTOR
        target = OUT / path.name
        df.to_csv(target, index=False)
        rows.append(
            {
                "file": path.name,
                "rows": len(df),
                "raw_total_mm": round(before_sum, 1),
                "raw_max_mm_day": round(before_max, 1),
                "corrected_total_mm": round(float(df["PRECTOTCORR"].sum()), 1),
                "corrected_max_mm_day": round(float(df["PRECTOTCORR"].max()), 1),
                "mean_mm_day": round(float(df["PRECTOTCORR"].mean()), 2),
            }
        )

    report = pd.DataFrame(rows)
    report.to_csv(OUT / "power_precip_correction_report.csv", index=False)
    print(report.to_string(index=False))
    print(f"\nCorrected copies written to {OUT}")
    print("Original files were not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
