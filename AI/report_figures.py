"""Render the figures used in the data report.

Palette: the validated reference categorical slots (blue / orange / aqua) on
the light surface, single hue per panel, recessive grid, no dual axes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

BASE = Path(__file__).resolve().parent
OUT = BASE / "_report"
OUT.mkdir(exist_ok=True)

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3de"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK2,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "axes.titlesize": 10,
        "axes.titlecolor": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
    }
)

MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
REGION_ORDER = [
    "Northwest_Rajshahi",
    "North_Rangpur",
    "Central_Dhaka",
    "Northeast_Sylhet",
    "Southwest_Khulna",
    "South_Barishal",
    "Southeast_Chattogram",
]


def pretty(region: str) -> str:
    return region.replace("_", " ")


def load(name, datecol, cols):
    files = [p for p in sorted((BASE / name).glob("*all_regions*.csv")) if "provenance" not in p.name]
    df = pd.read_csv(files[-1], usecols=cols + [datecol])
    df[datecol] = pd.to_datetime(df[datecol])
    df["month"] = df[datecol].dt.month
    df["year"] = df[datecol].dt.year
    return df


def fig_rainfall_small_multiples() -> Path:
    rain = load("GPM_IMERG_Rainfall", "date", ["region", "precipitation_mm_day"])
    monthly = rain.groupby(["region", "month"])["precipitation_mm_day"].mean()
    full = rain[rain["year"].isin([2022, 2023, 2024, 2025])]
    annual = full.groupby("region")["precipitation_mm_day"].sum() / full["year"].nunique()

    fig, axes = plt.subplots(3, 3, figsize=(7.9, 5.6), sharey=True)
    axes = axes.ravel()
    top = float(monthly.max()) * 1.18
    for ax, region in zip(axes, REGION_ORDER):
        vals = monthly.loc[region].reindex(range(1, 13))
        ax.plot(range(1, 13), vals.values, color=BLUE, linewidth=2)
        ax.fill_between(range(1, 13), 0, vals.values, color=BLUE, alpha=0.10, linewidth=0)
        ax.axvspan(5.5, 9.5, color=GRID, alpha=0.55, linewidth=0, zorder=0)
        ax.set_title(pretty(region), pad=5, fontsize=9)
        ax.set_ylim(0, top)
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(MONTHS, fontsize=6.5)
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(axis="y")
        ax.set_axisbelow(True)
        ax.annotate(
            f"{annual[region]:,.0f} mm/yr",
            xy=(0.04, 0.88),
            xycoords="axes fraction",
            fontsize=7,
            color=INK2,
        )
    axes[6].set_xlabel("Month", fontsize=8)
    fig.delaxes(axes[-1])
    fig.delaxes(axes[-2])
    fig.text(
        0.70,
        0.16,
        "Grey band = Jun-Sep monsoon." + chr(10) + "Annual totals are 2022-2025 means.",
        fontsize=8,
        color=INK2,
        ha="left",
    )
    for ax in (axes[0], axes[3], axes[6]):
        ax.set_ylabel("mm/day", fontsize=8)
    fig.suptitle("Mean daily rainfall by month, 2022-2026", fontsize=11.5, color=INK, y=0.985)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    path = OUT / "fig1_rainfall_seasonality.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def fig_seasonal_coupling() -> Path:
    rain = load("GPM_IMERG_Rainfall", "date", ["region", "precipitation_mm_day"])
    smap = load("SMAP_SoilMoisture", "date", ["region", "soil_moisture_m3_m3"])
    hls = load("HLS_Vegetation_Indices", "observed_utc", ["region", "ndvi", "valid_coverage"])

    r = rain.groupby("month")["precipitation_mm_day"].mean()
    s = smap.groupby("month")["soil_moisture_m3_m3"].mean()
    n = hls.dropna(subset=["ndvi"]).groupby("month")["ndvi"].mean()

    fig, axes = plt.subplots(3, 1, figsize=(7.4, 7.6), sharex=True)
    series = [
        (axes[0], r, BLUE, "Rainfall", "mm/day", "{:.1f}"),
        (axes[1], s, ORANGE, "Soil moisture (0-5 cm)", "m³/m³", "{:.2f}"),
        (axes[2], n, AQUA, "NDVI from HLS", "index", "{:.2f}"),
    ]
    for ax, data, color, title, unit, fmt in series:
        vals = data.reindex(range(1, 13))
        ax.plot(range(1, 13), vals.values, color=color, linewidth=2, marker="o", markersize=5)
        ax.set_title(title, loc="left", pad=4)
        ax.set_ylabel(unit, fontsize=8)
        ax.grid(axis="y")
        ax.set_axisbelow(True)
        ax.set_ylim(bottom=min(vals.min() * 0.85, vals.min() - 0.05) if "sm" in title or "NDVI" in title else 0)
        peak = int(vals.idxmax())
        ax.annotate(
            fmt.format(vals.max()),
            xy=(peak, vals.max()),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color=INK2,
        )
    axes[-1].set_xticks(range(1, 13))
    axes[-1].set_xticklabels(MONTHS)
    axes[-1].set_xlabel("Month", fontsize=8)
    fig.suptitle(
        "Seasonal cycle of rainfall, soil moisture and vegetation\n(mean of the seven regions)",
        fontsize=11,
        color=INK,
        y=0.98,
    )
    fig.text(
        0.5,
        0.005,
        "Rainfall and surface soil moisture peak in August; NDVI peaks a month later.",
        ha="center",
        fontsize=8,
        color=INK2,
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.93])
    path = OUT / "fig2_seasonal_coupling.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def fig_grace_trend() -> Path:
    grace = load("GRACE_WaterStorage", "date", ["region", "lwe_thickness_cm"])
    rows = []
    for region, g in grace.groupby("region"):
        g = g.sort_values("date")
        years = (g["date"] - g["date"].min()).dt.days / 365.25
        rows.append((region, float(np.polyfit(years, g["lwe_thickness_cm"], 1)[0])))
    df = pd.DataFrame(rows, columns=["region", "slope"]).sort_values("slope")

    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    colors = [ORANGE if v < 0 else BLUE for v in df["slope"]]
    bars = ax.barh([pretty(r) for r in df["region"]], df["slope"], color=colors, height=0.62)
    ax.axvline(0, color=INK2, linewidth=1)
    for bar, value in zip(bars, df["slope"]):
        offset = 0.12 if value >= 0 else -0.12
        ax.text(
            value + offset,
            bar.get_y() + bar.get_height() / 2,
            f"{value:+.1f}",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=8.5,
            color=INK2,
        )
    ax.set_xlabel("Water-storage trend, cm per year", fontsize=8)
    ax.grid(axis="x")
    ax.set_axisbelow(True)
    ax.set_xlim(df["slope"].min() - 1.2, df["slope"].max() + 1.2)
    ax.set_title("GRACE water-storage trend, 2022-2026", loc="left", fontsize=11, color=INK)
    fig.text(
        0.5,
        0.005,
        "Regions sharing a 0.5° mascon cell carry identical values. Four years is too short to read as climate.",
        ha="center",
        fontsize=7.5,
        color=INK2,
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.97])
    path = OUT / "fig3_grace_trend.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def main() -> int:
    paths = [fig_rainfall_small_multiples(), fig_seasonal_coupling(), fig_grace_trend()]
    for p in paths:
        print(p.name, f"{p.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
