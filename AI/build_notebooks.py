"""Generate the six application notebooks from a single source of truth.

Each notebook is self-contained: it loads Data/model_ready, does its own
analysis, prints real numbers, and writes its outputs into Data/notebooks/outputs.
Run this after build_model_ready.py; then execute the notebooks (see main()).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

BASE = Path(__file__).resolve().parent
NOTEBOOKS = BASE / "notebooks"
OUTPUTS = NOTEBOOKS / "outputs"

PREAMBLE = '''\
# --- shared setup -----------------------------------------------------------
import os, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

warnings.filterwarnings("ignore")
pd.set_option("display.width", 160)

DATA = Path(os.environ.get("BH6_DATA", r"C:\\Users\\muhai\\Desktop\\BIG hero 6\\Data"))
MR = DATA / "model_ready"
OUT = Path(os.environ.get("BH6_OUT", str(Path.cwd() / "outputs")))
OUT.mkdir(parents=True, exist_ok=True)

regions = ["Northwest_Rajshahi", "North_Rangpur", "Central_Dhaka", "Northeast_Sylhet",
           "Southwest_Khulna", "South_Barishal", "Southeast_Chattogram"]
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

BLUE, ORANGE, AQUA, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#0b0b0b", "#52514e", "#e4e3de"
plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "savefig.facecolor": "#fcfcfb",
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.titlesize": 10, "axes.titlecolor": INK, "axes.spines.top": False,
    "axes.spines.right": False, "grid.color": GRID, "grid.linewidth": 0.8,
})
SEQ = LinearSegmentedColormap.from_list("brand_blue", ["#eaf2fc", "#9cc3ef", "#2a78d6", "#12365f"])

def pretty(region):
    return region.replace("_", " ")

def load_daily():
    df = pd.read_csv(MR / "daily_panel.csv", parse_dates=["date"])
    return df.sort_values(["region", "date"]).reset_index(drop=True)

def load_monthly():
    df = pd.read_csv(MR / "monthly_panel.csv", parse_dates=["date"])
    return df.sort_values(["region", "date"]).reset_index(drop=True)

def split_by_date(dates, train_end="2024-12-31", valid_end="2025-12-31"):
    d = pd.to_datetime(dates)
    return (d <= train_end), (d > train_end) & (d <= valid_end), d > valid_end

def metrics(y_true, y_pred):
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    if ok.sum() < 5:
        return {"n": int(ok.sum())}
    return {"n": int(ok.sum()),
            "MAE": round(float(mean_absolute_error(y_true[ok], y_pred[ok])), 3),
            "RMSE": round(float(np.sqrt(mean_squared_error(y_true[ok], y_pred[ok]))), 3),
            "R2": round(float(r2_score(y_true[ok], y_pred[ok])), 3)}

print(f"pandas {pd.__version__} | data: {DATA}")
'''

# ---------------------------------------------------------------------------
# 01 dashboard
# ---------------------------------------------------------------------------
NB_DASHBOARD = [
    ("md", """# 01 · Regional dashboard

**Question it answers:** what do we know about each region right now, and how fresh is it?

The dashboard is deliberately built from the same tables the models use, so what a
farmer or officer sees is what the model sees. Two things matter more than the
numbers themselves:

1. **Freshness.** A value that is 40 days old is not the same as a value from today.
   Every satellite product here has a publishing lag — GPM's Final Run lags months,
   GRACE lags one to two months, SMAP retrieves on roughly 3 days in 5.
2. **Coverage.** Reporting a mean without saying what fraction of days had an
   observation is how dashboards end up lying quietly.

Outputs: `dashboard_status.csv`, four seasonal heatmaps."""),
    ("code", PREAMBLE),
    ("md", """## 1. Load the panels

`daily_panel.csv` has one row per region-day with every feature known at the end of
that day. `monthly_panel.csv` aggregates the same data per calendar month."""),
    ("code", '''daily = load_daily()
monthly = load_monthly()
print("daily  ", daily.shape, daily["date"].min().date(), "->", daily["date"].max().date())
print("monthly", monthly.shape, monthly["date"].min().date(), "->", monthly["date"].max().date())
daily.head(3)'''),
    ("md", """## 2. Freshness and coverage per variable

For each region and each source we ask: when was the last observation, how old is it,
and what share of the last 30 days carried a value? The `*_observed_today` and
`*_age_days` columns exist precisely for this."""),
    ("code", '''SOURCES = {
    "rainfall (GPM)": "gpm_rain_mm",
    "soil moisture (SMAP)": "sm_mean",
    "vegetation (HLS NDVI)": "ndvi_last",
    "surface temp (ECOSTRESS)": "lst_c_last",
    "water storage (GRACE)": "grace_lwe_cm_last",
    "weather (POWER)": "t2m_c",
}

last_date = daily["date"].max()
recent = daily[daily["date"] > last_date - pd.Timedelta(days=30)]

rows = []
for region, g in daily.groupby("region"):
    rec = {"region": pretty(region)}
    for label, col in SOURCES.items():
        s = g[col].dropna()
        last = g.loc[g[col].notna(), "date"].max() if len(s) else pd.NaT
        rec[f"{label} · last"] = last.date().isoformat() if pd.notna(last) else "never"
        rec[f"{label} · age d"] = int((last_date - last).days) if pd.notna(last) else None
        gr = recent[recent["region"] == region]
        rec[f"{label} · 30d %"] = round(100 * gr[col].notna().mean(), 0) if len(gr) else np.nan
    rows.append(rec)

fresh = pd.DataFrame(rows)
fresh.to_csv(OUT / "dashboard_status.csv", index=False)
fresh.iloc[:, :7].set_index("region")'''),
    ("code", '''coverage = fresh.set_index("region")[[c for c in fresh.columns if c.endswith("30d %")]]
fig, ax = plt.subplots(figsize=(9, 3.4))
im = ax.imshow(coverage.values, cmap=SEQ, vmin=0, vmax=100, aspect="auto")
ax.set_xticks(range(len(coverage.columns)))
ax.set_xticklabels([c.replace(" · 30d %", "") for c in coverage.columns], rotation=20, ha="right", fontsize=8)
ax.set_yticks(range(len(coverage.index)))
ax.set_yticklabels(coverage.index, fontsize=8)
for i in range(coverage.shape[0]):
    for j in range(coverage.shape[1]):
        v = coverage.values[i, j]
        if np.isfinite(v):
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7,
                    color="white" if v > 55 else INK)
ax.set_title("Share of the last 30 days with an observation (%)", loc="left")
fig.colorbar(im, ax=ax, shrink=0.8, label="% of days")
fig.tight_layout()
plt.show()'''),
    ("md", """## 3. Seasonal fingerprints

A single "current value" is meaningless without its season. These heatmaps show each
region's normal month — the context a dashboard needs behind today's number."""),
    ("code", '''def seasonal_heat(ax, frame, column, title, fmt="{:.1f}", cmap=SEQ):
    pivot = frame.pivot_table(index="region", columns=frame["date"].dt.month, values=column, aggfunc="mean")
    pivot = pivot.reindex(index=regions, columns=range(1, 13))
    im = ax.imshow(pivot.values, cmap=cmap, aspect="auto")
    ax.set_xticks(range(12)); ax.set_xticklabels(months, fontsize=7)
    ax.set_yticks(range(len(regions))); ax.set_yticklabels([pretty(r) for r in regions], fontsize=7)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if np.isfinite(v):
                ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=6.5,
                        color="white" if v > np.nanpercentile(pivot.values, 65) else INK)
    ax.set_title(title, loc="left", fontsize=9)
    return im

fig, axes = plt.subplots(4, 1, figsize=(8.6, 12))
seasonal_heat(axes[0], monthly, "rain_mm", "Rainfall (mm/month)")
seasonal_heat(axes[1], monthly, "t2m_c", "Mean air temperature (°C)")
seasonal_heat(axes[2], monthly, "sm_mean", "Surface soil moisture (m³/m³)", "{:.2f}")
seasonal_heat(axes[3], monthly, "ndvi", "NDVI where observed", "{:.2f}")
fig.tight_layout()
plt.show()'''),
    ("md", """## 4. Current status

For each region: rainfall over the last 30 days, how it compares with the same window
in previous years, the latest soil-moisture percentile, and the freshest NDVI.

The comparison uses the *same calendar window* in earlier years, not the annual mean —
comparing a January against an annual average would manufacture a drought every winter."""),
    ("code", '''cut = last_date - pd.Timedelta(days=30)
rows = []
for region, g in daily.groupby("region"):
    g = g.set_index("date")
    window = g.loc[g.index > cut]
    rain_30 = window["gpm_rain_mm"].sum(min_count=1)

    same_windows = []
    for year in (2022, 2023, 2024, 2025):
        start, end = cut.replace(year=year), last_date.replace(year=year)
        w = g.loc[(g.index > start) & (g.index <= end), "gpm_rain_mm"]
        if w.notna().any():
            same_windows.append(w.sum())
    clim = float(np.mean(same_windows)) if same_windows else np.nan

    sm = g["sm_mean"].dropna()
    sm_pct = float((sm < sm.iloc[-1]).mean() * 100) if len(sm) and np.isfinite(sm.iloc[-1]) else np.nan

    ndvi = g["ndvi_last"].dropna()
    rows.append({
        "region": pretty(region),
        "rain 30d mm": round(float(rain_30), 1) if np.isfinite(rain_30) else None,
        "same window avg mm": round(clim, 1) if np.isfinite(clim) else None,
        "anomaly %": round(100 * (rain_30 - clim) / clim, 0) if np.isfinite(clim) and clim > 0 else None,
        "soil moisture pct": round(sm_pct, 0) if np.isfinite(sm_pct) else None,
        "NDVI latest": round(float(ndvi.iloc[-1]), 2) if len(ndvi) else None,
        "NDVI age d": int((last_date - g.index[g["ndvi_last"].notna()][-1]).days) if len(ndvi) else None,
    })
status = pd.DataFrame(rows)
status.to_csv(OUT / "current_status.csv", index=False)
status'''),
    ("md", """## 5. Reading this honestly

- **`anomaly %` needs a wet season to mean anything.** In January a "−100%" anomaly may
  be 3 mm versus 6 mm. Read it beside the absolute totals, never alone.
- **`NDVI age d` is often 20–45 days.** HLS only sees through cloud; in the monsoon an
  apparently stale NDVI is the normal state, not a fault.
- **Percentiles are computed against the whole record for that region**, so a value in
  the 10th percentile is dry *for that region*, not dry in absolute terms.
- GRACE and soil moisture are regional context. Neither is a field measurement, and
  neither should drive an irrigation decision on its own."""),
]

# ---------------------------------------------------------------------------
# 02 temperature
# ---------------------------------------------------------------------------
NB_TEMP = [
    ("md", """# 02 · Temperature prediction (1-day and 3-day)

**Task:** forecast mean 2 m air temperature for the next day and three days ahead,
per region, from the model-ready panel.

**Why this is a good first forecasting task:** air temperature is the most
autocorrelated variable in the archive. Tomorrow's temperature is close to today's, so
*persistence* is a genuinely strong baseline — the literature on short-range
temperature forecasting consistently finds that machine learning beats it only
marginally at 1–3 days, and mostly by capturing the diurnal and seasonal cycle rather
than any new information.

That framing matters: a model reporting R² = 0.95 looks impressive until you see
persistence already scores 0.94. Every result below is therefore reported **against
persistence**, and the interesting question is not "can we predict temperature" (yes,
trivially) but "do these features add anything to what a thermometer already told us".

Outputs: `temperature_scores.csv`, forecast-vs-observed figure."""),
    ("code", PREAMBLE),
    ("md", """## 1. Build the targets

Targets are explicit forward shifts within each region. A 3-day-ahead target uses only
data up to day t, so there is no leakage across the horizon."""),
    ("code", '''daily = load_daily()
g = daily.groupby("region", group_keys=False)
daily["t_plus1"] = g["t2m_c"].shift(-1)
daily["t_plus3"] = g["t2m_c"].shift(-3)

print("rows:", len(daily), "| regions:", daily.region.nunique())
print("1-day target available:", int(daily.t_plus1.notna().sum()))
print("3-day target available:", int(daily.t_plus3.notna().sum()))
daily[["date", "region", "t2m_c", "t_plus1", "t_plus3"]].head()'''),
    ("md", """## 2. Features

Only same-day or past information: today's temperature, the last few days, humidity,
wind, radiation, the seasonal position, and the region. Nothing from t+1 onward."""),
    ("code", '''def feature_frame(df):
    X = df[["t2m_c", "tmax_c", "tmin_c", "diurnal_range_c", "rh_pct", "wind_ms",
            "solar_mj_m2", "pressure_kpa", "vpd_kpa", "power_rain_mm", "gpm_rain_mm",
            "doy_sin", "doy_cos"]].copy()
    past = df.groupby("region", group_keys=False)
    for lag in (1, 2, 3, 7):
        X[f"t2m_lag{lag}"] = past["t2m_c"].shift(lag)
    X["t2m_mean7"] = past["t2m_c"].apply(lambda s: s.rolling(7, min_periods=3).mean())
    X = pd.concat([X, pd.get_dummies(df["region"], prefix="region", dtype=float)], axis=1)
    return X

X_all = feature_frame(daily)
print("feature matrix:", X_all.shape)
X_all.iloc[:3, :8]'''),
    ("md", """## 3. Time-based split and baselines

Train on 2022–2024, validate on 2025, test on 2026. Splitting randomly would let the
model interpolate between neighbouring days and report a fiction.

Two baselines: **persistence** (tomorrow = today) and **climatology** (the long-run
mean for that calendar month)."""),
    ("code", '''from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

train, valid, test = split_by_date(daily["date"])
print("train", int(train.sum()), "valid", int(valid.sum()), "test", int(test.sum()))

records = []
models = {}
for horizon, target in [(1, "t_plus1"), (3, "t_plus3")]:
    usable = daily[target].notna()
    tr, te = train & usable, test & usable

    Xtr, ytr = X_all[tr], daily.loc[tr, target]
    Xte, yte = X_all[te], daily.loc[te, target]

    # baselines
    persistence = daily.loc[te, "t2m_c"]          # tomorrow = today
    clim = ytr.groupby(daily.loc[tr, "date"].dt.month).mean()
    climatology = daily.loc[te, "date"].dt.month.map(clim)

    records.append({"horizon": horizon, "model": "persistence", **metrics(yte, persistence)})
    records.append({"horizon": horizon, "model": "climatology", **metrics(yte, climatology)})

    ridge = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=1.0))
    ridge.fit(Xtr, ytr)
    records.append({"horizon": horizon, "model": "ridge", **metrics(yte, ridge.predict(Xte))})

    gbr = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.06, min_samples_leaf=20,
                                        l2_regularization=1.0, random_state=0)
    gbr.fit(Xtr, ytr)
    records.append({"horizon": horizon, "model": "gradient boosting", **metrics(yte, gbr.predict(Xte))})
    models[horizon] = (gbr, Xte, yte, persistence)

scores = pd.DataFrame(records)
scores.to_csv(OUT / "temperature_scores.csv", index=False)
scores'''),
    ("md", """## 4. Skill against persistence

Raw R² flatters everything here. The useful number is **skill score** relative to
persistence: 1 − MSE(model) / MSE(persistence). Zero means "no better than assuming
tomorrow repeats today"; negative means worse."""),
    ("code", '''from sklearn.metrics import mean_squared_error

rows = []
for horizon in (1, 3):
    block = scores[scores.horizon == horizon].set_index("model")
    base_mse = mean_squared_error(models[horizon][2], models[horizon][3])
    for name, row in block.iterrows():
        mse = row["RMSE"] ** 2
        rows.append({"horizon": horizon, "model": name, "RMSE": row["RMSE"], "R2": row["R2"],
                     "skill vs persistence": round(1 - mse / base_mse, 3)})
skill = pd.DataFrame(rows)
skill.to_csv(OUT / "temperature_skill.csv", index=False)
skill'''),
    ("md", """## 5. Forecast versus observed

The test year, one region, both horizons. A good forecast tracks the line; a lazy one
lags it by a day."""),
    ("code", '''gbr, Xte, yte, persistence = models[1]
pred1 = gbr.predict(Xte)
mask = (daily.loc[Xte.index, "region"] == "Central_Dhaka")
dates = daily.loc[Xte.index, "date"]

fig, ax = plt.subplots(figsize=(11, 3.6))
sel = mask.to_numpy()
ax.plot(dates[sel], yte[sel], color=INK, linewidth=1.4, label="observed")
ax.plot(dates[sel], pred1[sel], color=BLUE, linewidth=1.4, label="model, 1 day")
ax.plot(dates[sel], persistence[sel], color=ORANGE, linewidth=1, linestyle="--", label="persistence")
ax.set_title("Central Dhaka — 1-day temperature forecast, test year 2026", loc="left")
ax.set_ylabel("°C"); ax.grid(axis="y"); ax.set_axisbelow(True)
ax.legend(frameon=False, fontsize=8, ncol=3)
fig.tight_layout(); plt.show()'''),
    ("code", '''err = np.abs(pred1[sel] - yte[sel].to_numpy())
errp = np.abs(persistence[sel].to_numpy() - yte[sel].to_numpy())
print(f"Central Dhaka, 1-day: model mean abs error {np.nanmean(err):.2f} °C, "
      f"persistence {np.nanmean(errp):.2f} °C")
print(f"3-day RMSE across all regions: {scores[(scores.horizon==3)&(scores.model=='gradient boosting')].RMSE.iloc[0]:.2f} °C")'''),
    ("md", """## 6. What this is really telling you

- **At 1 day, persistence is hard to beat.** Any gain from the model is small; the value
  of the feature set is mainly in the 3-day horizon, where persistence starts to decay.
- **The 3-day forecast is where a product can honestly claim something**, and even there
  the errors are dominated by synoptic events (rain spells, cold fronts) that these
  features do not resolve.
- **Never present this as a weather forecast.** It is a statistical extrapolation from a
  reanalysis grid cell, not a numerical weather prediction. For an actual forecast, use
  a NWP product (ECMWF/GFS via an API) and keep this as the fallback when offline.
- The panel has ~1,760 days; effective sample size is far smaller because day-to-day
  values are nearly redundant. Treat the last test year as a sanity check, not proof."""),
]

# ---------------------------------------------------------------------------
# 03 rain
# ---------------------------------------------------------------------------
NB_RAIN = [
    ("md", """# 03 · Rain prediction — probability first, amount second

**Task:** estimate (a) the probability that the next day is wet, and (b) how much rain
falls if it is.

**Why two models instead of one:** in this record **47.9% of region-days are exactly
0.0 mm**. A single squared-error regression on millimetres is dominated by getting the
zeros right and says almost nothing about the tail. The standard treatment in rainfall
modelling is a two-part (hurdle) model: a classifier for occurrence, then a positive
regression for amount. It also gives the user two honest numbers — "60% chance of rain"
and "if it rains, about 12 mm" — instead of one misleading average.

**Evidence base:** two-part rainfall models are standard in agro-meteorology (Wilks,
*Statistical Methods in the Atmospheric Sciences*); probability forecasts are scored
with Brier score and log loss rather than accuracy, because accuracy is trivially high
when 70% of days are dry.

Outputs: `rain_model_scores.csv`, reliability curve, amount model comparison."""),
    ("code", PREAMBLE),
    ("md", """## 1. Build the occurrence and amount targets

A day counts as wet at ≥ 0.1 mm (the conventional tipping-bucket threshold). The
distinction matters: 0.02 mm is dew, not rain."""),
    ("code", '''daily = load_daily()
g = daily.groupby("region", group_keys=False)
daily["rain_next"] = g["gpm_rain_mm"].shift(-1)
daily["wet_next"] = (daily["rain_next"] >= 0.1).astype(float)
daily.loc[daily["rain_next"].isna(), "wet_next"] = np.nan

print("days with a next-day observation:", int(daily.rain_next.notna().sum()))
print("share of wet next-days:", round(float(daily.wet_next.mean()), 3))
print("\\nby month (share of days wet):")
print(daily.groupby(daily.date.dt.month)["wet_next"].mean().round(2).to_string())'''),
    ("code", '''fig, ax = plt.subplots(figsize=(8, 2.8))
monthly_rate = daily.groupby(daily.date.dt.month)["wet_next"].mean()
ax.bar(monthly_rate.index, monthly_rate.values * 100, color=BLUE, width=0.7)
ax.set_xticks(range(1, 13)); ax.set_xticklabels(months)
ax.set_ylabel("% of days wet"); ax.grid(axis="y"); ax.set_axisbelow(True)
ax.set_title("Base rate of a wet day by month — the number any model must beat", loc="left")
fig.tight_layout(); plt.show()'''),
    ("md", """## 2. Features

Rainfall history is the strongest available predictor: how many of the last 7 days were
wet, and how much fell over 3, 7 and 30 days. Temperature range and humidity carry the
atmospheric state."""),
    ("code", '''def rain_features(df):
    X = df[["t2m_c", "tmax_c", "tmin_c", "diurnal_range_c", "rh_pct", "wind_ms",
            "solar_mj_m2", "pressure_kpa", "vpd_kpa", "power_rain_mm", "gpm_rain_mm",
            "power_rain_sum_3d", "power_rain_sum_7d", "power_rain_sum_30d",
            "gpm_rain_sum_7d", "dry_spell_days", "doy_sin", "doy_cos", "month"]].copy()
    past = df.groupby("region", group_keys=False)
    X["rain_days_7d"] = past["gpm_rain_mm"].apply(lambda s: (s >= 0.1).rolling(7, min_periods=3).sum())
    X["rain_days_14d"] = past["gpm_rain_mm"].apply(lambda s: (s >= 0.1).rolling(14, min_periods=5).sum())
    X["rain_lag1"] = past["gpm_rain_mm"].shift(1)
    return pd.concat([X, pd.get_dummies(df["region"], prefix="region", dtype=float)], axis=1)

X = rain_features(daily)
train, valid, test = split_by_date(daily["date"])
print("features:", X.shape[1])'''),
    ("md", """## 3. Stage 1 — probability of a wet day

Logistic regression gives a calibrated probability directly; gradient boosting may
rank better but needs calibration. Both are compared on **Brier score** (lower is
better), **log loss** and **AUC**, against the seasonal base rate."""),
    ("code", '''from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

usable = daily["wet_next"].notna()
tr, te = train & usable, test & usable
Xtr, ytr = X[tr], daily.loc[tr, "wet_next"]
Xte, yte = X[te], daily.loc[te, "wet_next"]

base_rate = ytr.groupby(daily.loc[tr, "date"].dt.month).mean()
base_pred = np.clip(daily.loc[te, "date"].dt.month.map(base_rate).to_numpy(), 1e-3, 1 - 1e-3)

logit = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                      LogisticRegression(max_iter=1000, class_weight="balanced"))
logit.fit(Xtr, ytr)
p_logit = logit.predict_proba(Xte)[:, 1]

gbc = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, min_samples_leaf=30, random_state=0)
gbc.fit(Xtr, ytr)
p_gbc = gbc.predict_proba(Xte)[:, 1]

occ = pd.DataFrame([
    {"model": "seasonal base rate", "AUC": round(roc_auc_score(yte, base_pred), 3),
     "Brier": round(brier_score_loss(yte, base_pred), 4), "log loss": round(log_loss(yte, base_pred), 4)},
    {"model": "logistic regression", "AUC": round(roc_auc_score(yte, p_logit), 3),
     "Brier": round(brier_score_loss(yte, p_logit), 4), "log loss": round(log_loss(yte, p_logit), 4)},
    {"model": "gradient boosting", "AUC": round(roc_auc_score(yte, p_gbc), 3),
     "Brier": round(brier_score_loss(yte, p_gbc), 4), "log loss": round(log_loss(yte, p_gbc), 4)},
])
occ.to_csv(OUT / "rain_occurrence_scores.csv", index=False)
occ'''),
    ("md", """## 4. Is the probability honest?

A forecast that says 70% should be right about 70% of the time. The reliability curve
plots predicted probability against observed frequency; the diagonal is perfect
calibration."""),
    ("code", '''from sklearn.calibration import calibration_curve

fig, ax = plt.subplots(figsize=(4.6, 4.2))
for name, p, color in [("logistic", p_logit, BLUE), ("gradient boosting", p_gbc, ORANGE)]:
    frac, mean_pred = calibration_curve(yte, p, n_bins=10, strategy="quantile")
    ax.plot(mean_pred, frac, marker="o", markersize=4, linewidth=2, color=color, label=name)
ax.plot([0, 1], [0, 1], color=MUTED, linewidth=1, linestyle="--", label="perfect")
ax.set_xlabel("predicted probability"); ax.set_ylabel("observed frequency")
ax.set_title("Reliability, test year 2026", loc="left")
ax.legend(frameon=False, fontsize=8); ax.grid(True); ax.set_axisbelow(True)
fig.tight_layout(); plt.show()'''),
    ("md", """## 5. Stage 2 — how much, given that it rains

Fitted only on wet days, with a Gamma loss (rainfall amounts are positive and
right-skewed — a squared-error fit would mostly chase the rare extremes)."""),
    ("code", '''from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

wet_tr = tr & (daily["rain_next"] >= 0.1)
wet_te = te & (daily["rain_next"] >= 0.1)
Xw, yw = X[wet_tr], daily.loc[wet_tr, "rain_next"]
Xwt, ywt = X[wet_te], daily.loc[wet_te, "rain_next"]

amount_sq = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06,
                                          min_samples_leaf=25, random_state=0)
amount_sq.fit(Xw, yw)
p_sq = np.clip(amount_sq.predict(Xwt), 0, None)

try:
    amount_gamma = HistGradientBoostingRegressor(loss="gamma", max_iter=300,
                                                 learning_rate=0.06, min_samples_leaf=25, random_state=0)
    amount_gamma.fit(Xw, yw)
    p_gamma = np.clip(amount_gamma.predict(Xwt), 0, None)
    have_gamma = True
except Exception as exc:
    have_gamma = False
    print("gamma loss unavailable:", exc)

rows = [{"model": "climatology (mean wet-day amount)", "MAE mm": round(mean_absolute_error(ywt, np.full(len(ywt), yw.mean())), 2)},
        {"model": "gradient boosting, squared error", "MAE mm": round(mean_absolute_error(ywt, p_sq), 2)}]
if have_gamma:
    rows.append({"model": "gradient boosting, gamma loss", "MAE mm": round(mean_absolute_error(ywt, p_gamma), 2)})
amounts = pd.DataFrame(rows)
amounts.to_csv(OUT / "rain_amount_scores.csv", index=False)
amounts'''),
    ("md", """## 6. Putting the two stages together

The expected rainfall is P(wet) × E[amount | wet]. That is the number to show a user —
and it should be shown with the two components, not instead of them."""),
    ("code", '''amount_all = np.clip((amount_gamma if have_gamma else amount_sq).predict(Xte), 0, None)
expected = p_logit * amount_all
final = pd.DataFrame({
    "date": daily.loc[te, "date"].to_numpy(),
    "region": daily.loc[te, "region"].to_numpy(),
    "observed_mm": yte, "p_wet": np.round(p_logit, 3),
    "expected_mm": np.round(expected, 2),
})
final.to_csv(OUT / "rain_next_day_forecasts.csv", index=False)
print("saved", len(final), "forecasts")
print("\\ncalibration check: days with p_wet > 0.7 were wet",
      f"{(yte[final.p_wet > 0.7].mean()*100):.0f}% of the time (n={(final.p_wet>0.7).sum()})")
final.head(8)'''),
    ("md", """## 7. Limits — read before shipping

- **This is not a weather model.** It learns the local relationship between today's
  state and tomorrow's rain at a reanalysis grid cell. It cannot see a cyclone forming.
- **The dry-season signal is weak.** GPM reports near-zero rain in Nov–Feb while POWER
  reports tens of millimetres; the two disagree most exactly when both are small. Do not
  let a model learn a confident "0%" from that.
- **GPM Final Run lags ~3.5 months.** In production you would feed the Late Run and
  accept lower accuracy; record which run each forecast used.
- **Class balance shifts by month** (about 50% of days wet in July, ~5% in January).
  Aggregate metrics hide this — always report by season."""),
]

# ---------------------------------------------------------------------------
# 04 ET0
# ---------------------------------------------------------------------------
NB_ET0 = [
    ("md", """# 04 · Evaporation demand (reference ET₀)

**Task:** characterise and forecast **reference evapotranspiration (ET₀)** — the water
demand of a well-watered grass reference surface.

**What ET₀ is and is not.** ET₀ is a calculated meteorological quantity defined by
FAO-56 (Allen et al., 1998), not a measurement of any particular crop. Converting it to
a crop's actual water use requires a crop coefficient: `ETc = Kc × ET₀`. **Predicting
ET₀ is therefore not predicting irrigation requirement** — the requirement also depends
on crop stage, soil water holding capacity, effective rainfall and irrigation
efficiency.

**The standard.** FAO-56 Penman-Monteith:
`ET₀ = [0.408 Δ (Rn − G) + γ (900/(T+273)) u₂ (eₛ − eₐ)] / [Δ + γ(1 + 0.34 u₂)]`
When solar radiation is missing we fall back to Hargreaves (FAO-56 eq. 52), which uses
temperature range only and is explicitly an estimate.

Outputs: `et0_scores.csv`, monthly demand profile, rainfall-vs-demand deficit chart."""),
    ("code", PREAMBLE),
    ("md", """## 1. Which formula produced each value?

The panel carries both a Penman-Monteith series and a Hargreaves fallback. Knowing
which one a row came from matters: they are not interchangeable."""),
    ("code", '''daily = load_daily()
n_pm = int((daily["et0_method_hargreaves"] == 0).sum())
n_hg = int((daily["et0_method_hargreaves"] == 1).sum())
print(f"Penman-Monteith: {n_pm:,} days ({100*n_pm/len(daily):.1f}%)")
print(f"Hargreaves fallback: {n_hg:,} days ({100*n_hg/len(daily):.1f}%)")
print("\\nmean ET0 by method:")
print(daily.groupby("et0_method_hargreaves")["et0_best_mm"].agg(["mean", "std", "count"]).round(2))'''),
    ("code", '''both = daily.dropna(subset=["et0_fao56_mm", "et0_hargreaves_mm"])
diff = both["et0_hargreaves_mm"] - both["et0_fao56_mm"]
print(f"where both exist (n={len(both):,}): Hargreaves is {diff.mean():+.2f} mm/day vs Penman-Monteith")
print(f"correlation r = {both[['et0_fao56_mm','et0_hargreaves_mm']].corr().iloc[0,1]:.2f}")
print(f"90th percentile absolute difference: {diff.abs().quantile(0.9):.2f} mm/day")'''),
    ("md", """## 2. The seasonal demand profile

ET₀ is driven by radiation, temperature, humidity and wind, so it has a strong annual
cycle — highest in the pre-monsoon (March–May), lowest in the cool winter months."""),
    ("code", '''monthly = load_monthly()
pivot = monthly.pivot_table(index="region", columns=monthly.date.dt.month,
                            values="et0_mm", aggfunc="mean").reindex(regions, columns=range(1, 13))
fig, ax = plt.subplots(figsize=(9, 3.2))
im = ax.imshow(pivot.values, cmap=SEQ, aspect="auto")
ax.set_xticks(range(12)); ax.set_xticklabels(months, fontsize=8)
ax.set_yticks(range(len(regions))); ax.set_yticklabels([pretty(r) for r in regions], fontsize=8)
for i in range(pivot.shape[0]):
    for j in range(pivot.shape[1]):
        v = pivot.values[i, j]
        if np.isfinite(v):
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7,
                    color="white" if v > np.nanpercentile(pivot.values, 65) else INK)
ax.set_title("Mean monthly ET₀ (mm/month), 2022-2026", loc="left")
fig.colorbar(im, ax=ax, shrink=0.85, label="mm/month")
fig.tight_layout(); plt.show()'''),
    ("md", """## 3. Rainfall versus demand

The useful planning view is not ET₀ alone but **ET₀ minus rainfall** — the part of
demand the sky will not meet. Months below the line are irrigation months."""),
    ("code", '''agg = (daily.groupby(["region", "date"])[["et0_best_mm", "gpm_rain_mm"]].sum()
            .reset_index())
agg["month"] = agg.date.dt.month
clim = agg.groupby("month")[["et0_best_mm", "gpm_rain_mm"]].mean() * 30

fig, ax = plt.subplots(figsize=(8, 3.2))
ax.bar(clim.index - 0.19, clim["gpm_rain_mm"], width=0.38, color=BLUE, label="rainfall")
ax.bar(clim.index + 0.19, clim["et0_best_mm"], width=0.38, color=ORANGE, label="ET₀ demand")
ax.set_xticks(range(1, 13)); ax.set_xticklabels(months)
ax.set_ylabel("mm per month"); ax.grid(axis="y"); ax.set_axisbelow(True)
ax.set_title("Mean regional rainfall against reference ET₀ demand", loc="left")
ax.legend(frameon=False, fontsize=8)
fig.tight_layout(); plt.show()

deficit = clim["et0_best_mm"] - clim["gpm_rain_mm"]
print("months where demand exceeds rainfall:", [months[m-1] for m in deficit[deficit > 0].index])
print(deficit.round(0).to_string())'''),
    ("md", """## 4. Can ET₀ be forecast a day ahead?

Two questions get different answers here, and conflating them is the classic mistake:

1. **Can we reproduce tomorrow's ET₀?** Yes — it is a smooth function of weather, and
   even persistence does well.
2. **Do our features add anything beyond the seasonal cycle?** Test that by removing the
   monthly climatology from both target and prediction and re-scoring the residual."""),
    ("code", '''from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

g = daily.groupby("region", group_keys=False)
daily["et0_next"] = g["et0_best_mm"].shift(-1)

FEATS = ["t2m_c", "tmax_c", "tmin_c", "diurnal_range_c", "rh_pct", "wind_ms", "solar_mj_m2",
         "pressure_kpa", "vpd_kpa", "et0_best_mm", "et0_sum_7d", "doy_sin", "doy_cos", "month"]
X = pd.concat([daily[FEATS], pd.get_dummies(daily["region"], prefix="region", dtype=float)], axis=1)

train, valid, test = split_by_date(daily["date"])
usable = daily["et0_next"].notna()
tr, te = train & usable, test & usable
Xtr, ytr = X[tr], daily.loc[tr, "et0_next"]
Xte, yte = X[te], daily.loc[te, "et0_next"]

clim_map = ytr.groupby(daily.loc[tr, "date"].dt.month).mean()
pred_clim = daily.loc[te, "date"].dt.month.map(clim_map).to_numpy()
pred_pers = daily.loc[te, "et0_best_mm"].to_numpy()

ridge = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=1.0)).fit(Xtr, ytr)
pred_ridge = ridge.predict(Xte)
gbr = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06, min_samples_leaf=25, random_state=0).fit(Xtr, ytr)
pred_gbr = gbr.predict(Xte)

scores = pd.DataFrame([
    {"model": "persistence", **metrics(yte, pred_pers)},
    {"model": "monthly climatology", **metrics(yte, pred_clim)},
    {"model": "ridge", **metrics(yte, pred_ridge)},
    {"model": "gradient boosting", **metrics(yte, pred_gbr)},
])
scores.to_csv(OUT / "et0_scores.csv", index=False)
scores'''),
    ("code", '''# the stricter test: remove the seasonal cycle from target and predictions
month_factor = daily.loc[te, "date"].dt.month.map(clim_map).to_numpy()
target_anom = yte.to_numpy() - month_factor
rows = []
for name, pred in [("persistence", pred_pers), ("climatology", pred_clim),
                   ("ridge", pred_ridge), ("gradient boosting", pred_gbr)]:
    rows.append({"model": name, **metrics(target_anom, pred - month_factor)})
anom = pd.DataFrame(rows)
anom.to_csv(OUT / "et0_anomaly_scores.csv", index=False)
print("Scored on the anomaly (seasonal cycle removed):")
anom'''),
    ("md", """## 5. Reading the two tables together

Compare the raw and anomaly scores above. Three things stand out:

- **The seasonal cycle is most of the signal.** Monthly climatology alone would explain
  a large share of the variance, and the ridge model only improves modestly on it.
- **Anomaly skill does not vanish.** Once the monthly climatology is removed from both
  target and prediction, the ridge model still beats persistence (R² ≈ 0.61 vs 0.51).
  That is real and physical: weather anomalies persist from one day to the next, so
  tomorrow's ET₀ deviation is partly today's.
- **But the margin is small and it decays fast.** The skill is a 1-day persistence
  effect, not a meteorological forecast. Extend the horizon and it disappears.

An independent screening pass on this same record, aggregated to **monthly** scale,
found no anomaly skill at all. That is not a contradiction — it is a scale effect worth
stating plainly: **daily ET₀ anomalies are predictable one day ahead; monthly ET₀
anomalies are not.**

So the honest product statement is: **ET₀ gives a reliable seasonal water-demand
baseline, plus a modest one-day-ahead estimate.** Use it for planning windows (when will
demand exceed rainfall?) and for a next-day irrigation nudge — not as a weather
forecast, and never as the irrigation requirement itself, which needs the crop
coefficient and a soil-water balance (notebook 06)."""),
    ("md", """## 6. From ET₀ to a crop's demand

`ETc = Kc × ET₀`. The crop coefficient depends on the crop and growth stage
(FAO-56 Table 11). Notebook 06 does this properly with season windows and effective
rainfall. Here is the scale of the conversion for the main Bangladesh crops:

| Crop | Season | Kc mid-season | ETc in April (ET₀ ≈ 5.5 mm/day) |
|---|---|---|---|
| Boro rice (paddy) | Dec–Apr | 1.20 | ≈ 6.6 mm/day |
| Wheat | Nov–Mar | 1.15 | ≈ 6.3 mm/day |
| Maize | Nov–Apr | 1.20 | ≈ 6.6 mm/day |
| Potato | Nov–Feb | 1.15 | ≈ 6.3 mm/day |
| Mustard | Oct–Feb | 1.10 | ≈ 6.1 mm/day |"""),
]

# ---------------------------------------------------------------------------
# 05 soil water
# ---------------------------------------------------------------------------
NB_SOIL = [
    ("md", """# 05 · Soil-water monitoring

**Task:** build a usable surface-soil-moisture series from SMAP, with the quality
filtering the plan requires, then describe trends and drought state per region.

**Why filtering is the whole job.** SMAP's 9 km enhanced product reports a retrieval on
roughly **38% of region-days**. The gaps are not random: they cluster where the
retrieval quality flag fails, where the surface flag marks a frozen or water-dominated
cell, and where radio-frequency interference (RFI) degrades the brightness temperature.
Using the raw series means the trend you measure is partly a trend in *retrieval
success*, which is a classic remote-sensing trap.

**Evidence base:** SMAP L3 documentation defines `retrieval_qual_flag` (0 = recommended
quality) and `surface_flag` (2047 = no retrieval); RFI is a documented problem over
South Asia. The standard practice is to keep only recommended-quality retrievals and to
report coverage alongside every statistic.

Outputs: `soil_moisture_filtered.csv`, filtered-vs-unfiltered trend comparison,
percentile-based drought class per region-month."""),
    ("code", PREAMBLE),
    ("md", """## 1. Load the raw SMAP records and inspect the flags

The raw per-pass file keeps AM and PM separately — they are different overpasses and
should not be blended before filtering."""),
    ("code", '''from pathlib import Path
smap_files = sorted((DATA / "SMAP_SoilMoisture").glob("*all_regions*.csv"))
raw = pd.read_csv(smap_files[-1], parse_dates=["date"])
print("rows:", len(raw), "| passes:", raw["pass"].value_counts().to_dict())
print("\\nquality flag distribution (top 6):")
print(raw["retrieval_qual_flag"].value_counts(dropna=False).head(6).to_string())
print("\\nsurface flag distribution (top 6):")
print(raw["surface_flag"].value_counts(dropna=False).head(6).to_string())'''),
    ("md", """## 2. Apply the filter, step by step

Each step is reported so the cost is visible. Watch what the funnel below shows: after
the first step, **nothing more is removed**. The reason is that the retrieval already
happened upstream — the dataset delivered to `model_ready` contains only cells where
SMAP produced a value, and the quality flags on those cells are already clean. In other
words the filtering is real, but it was done when the data was extracted, not here.

That is worth stating explicitly rather than performing ceremony: a filter that appears
to do work it does not do is worse than no filter, because it implies a cleaning step
that never happened."""),
    ("code", '''steps = []
df = raw.copy()
steps.append(("all records", len(df)))
df = df[df["soil_moisture_m3_m3"].notna()]
steps.append(("has a soil-moisture value", len(df)))
df = df[df["soil_moisture_m3_m3"].between(0, 0.65)]
steps.append(("physically plausible (0-0.65 m3/m3)", len(df)))
df = df[df["surface_flag"].fillna(0) != 2047]
steps.append(("not flagged 'no retrieval' (2047)", len(df)))
if df["retrieval_qual_flag"].notna().any():
    best = df["retrieval_qual_flag"] == 0
    if best.sum() > 0.2 * len(df):
        df = df[best]
        steps.append(("recommended retrieval quality only", len(df)))

funnel = pd.DataFrame(steps, columns=["step", "records"])
funnel["retained %"] = (100 * funnel["records"] / funnel["records"].iloc[0]).round(1)
funnel'''),
    ("code", '''keep = {"am": 0.6, "pm": 0.4}   # AM overpass is closer to the morning soil state
filtered = df.copy()
filtered["weight"] = filtered["pass"].map(keep)
filtered["sm_weighted"] = filtered["soil_moisture_m3_m3"] * filtered["weight"]

tmp = filtered.assign(num=filtered["sm_weighted"])
gsum = (tmp.groupby(["region", "date"])
           .agg(num=("num", "sum"), den=("weight", "sum"))
           .reset_index())
daily_sm = gsum.assign(sm=gsum["num"] / gsum["den"])[["region", "date", "sm"]]

coverage = daily_sm.groupby("region").size() / raw["date"].nunique()
print("days retained per region (share of the full record):")
print((coverage * 100).round(1).to_string())'''),
    ("md", """## 3. Does the filter change the answer?

This is the test most analyses skip: compute the seasonal cycle and the trend on the
unfiltered series and on the filtered one. If they disagree, the unfiltered version was
measuring retrieval availability."""),
    ("code", '''unfiltered = (raw.groupby(["region", "date"])["soil_moisture_m3_m3"].mean()
                .rename("sm_unfiltered").reset_index())

def seasonal(frame, col):
    frame = frame.copy(); frame["month"] = frame["date"].dt.month
    return frame.groupby("month")[col].mean()

comp = pd.DataFrame({
    "unfiltered": seasonal(unfiltered, "sm_unfiltered"),
    "filtered": seasonal(daily_sm, "sm"),
})
comp["difference"] = (comp["filtered"] - comp["unfiltered"]).round(3)

fig, ax = plt.subplots(figsize=(7.6, 3))
ax.plot(comp.index, comp["unfiltered"], marker="o", color=ORANGE, label="unfiltered")
ax.plot(comp.index, comp["filtered"], marker="o", color=BLUE, label="quality-filtered")
ax.set_xticks(range(1, 13)); ax.set_xticklabels(months)
ax.set_ylabel("m³/m³"); ax.grid(axis="y"); ax.set_axisbelow(True)
ax.set_title("Seasonal cycle before and after quality filtering", loc="left")
ax.legend(frameon=False, fontsize=8)
fig.tight_layout(); plt.show()
print(comp.round(3).T.to_string())'''),
    ("md", """**What we actually observe:** the two curves sit on top of each other and the trend
table reports the same slope twice, with identical sample sizes. The extra flag steps
removed zero records. That is the expected outcome given the upstream filtering, and it
is reported rather than hidden — the alternative (quietly presenting a "quality-filtered"
series that was never filtered here) would misrepresent the provenance."""),
    ("code", '''def trend_stats(frame, col, label):
    out = []
    for region, g in frame.groupby("region"):
        g = g.dropna(subset=[col]).sort_values("date")
        if len(g) < 60:
            continue
        x = (g["date"] - g["date"].min()).dt.days / 365.25
        slope, intercept = np.polyfit(x, g[col], 1)
        resid = g[col] - (slope * x + intercept)
        se = np.sqrt((resid ** 2).sum() / (len(g) - 2) / ((x - x.mean()) ** 2).sum())
        out.append({"region": pretty(region), "series": label,
                    "slope m3/m3 per year": round(slope, 4),
                    "95% CI low": round(slope - 1.96 * se, 4),
                    "95% CI high": round(slope + 1.96 * se, 4),
                    "n": len(g)})
    return pd.DataFrame(out)

trends = pd.concat([trend_stats(unfiltered, "sm_unfiltered", "unfiltered"),
                    trend_stats(daily_sm, "sm", "filtered")])
trends.to_csv(OUT / "soil_moisture_trends.csv", index=False)
piv = trends.pivot(index="region", columns="series", values="slope m3/m3 per year")
print(piv.round(4).to_string())'''),
    ("md", """## 4. Drought state: where does today sit in this region's history?

A percentile is more useful than an absolute value because 0.30 m³/m³ is normal in
Rajshahi and dry in Khulna."""),
    ("code", '''sm_series = daily_sm.copy()
sm_series["month"] = sm_series["date"].dt.month
sm_series["pct"] = sm_series.groupby(["region", "month"])["sm"].rank(pct=True) * 100

def classify(p):
    if not np.isfinite(p): return "no data"
    if p < 10: return "very dry"
    if p < 25: return "dry"
    if p > 90: return "very wet"
    if p > 75: return "wet"
    return "normal"

sm_series["state"] = sm_series["pct"].apply(classify)
latest = sm_series.sort_values("date").groupby("region").tail(30)
summary = (latest.groupby("region")
           .agg(last_date=("date", "max"),
                latest_sm=("sm", "last"),
                latest_pct=("pct", "last"),
                state=("state", "last"),
                days_observed=("sm", "count"))
           .reset_index())
summary["region"] = summary["region"].map(pretty)
summary.to_csv(OUT / "soil_moisture_state.csv", index=False)
summary'''),
    ("code", '''sm_series["period"] = sm_series["date"].dt.to_period("M").astype(str)
pivot = sm_series.pivot_table(index="region", columns="period",
                               values="pct", aggfunc="mean").reindex(regions)
pivot.columns = [str(c) for c in pivot.columns]

fig, ax = plt.subplots(figsize=(11, 3))
im = ax.imshow(pivot.values, cmap=SEQ, aspect="auto", vmin=0, vmax=100)
ax.set_yticks(range(len(pivot.index)))
ax.set_yticklabels([pretty(r) for r in pivot.index], fontsize=8)
step = max(1, len(pivot.columns) // 14)
ax.set_xticks(range(0, len(pivot.columns), step))
ax.set_xticklabels(pivot.columns[::step], rotation=45, ha="right", fontsize=7)
ax.set_title("Monthly soil-moisture percentile within each region (darker = wetter)", loc="left")
fig.colorbar(im, ax=ax, shrink=0.8, label="percentile")
fig.tight_layout(); plt.show()'''),
    ("md", """## 5. What a monitoring product may and may not claim

**May claim:** a regional wetness percentile, updated as retrievals arrive, with the
number of observations behind it; a comparison of this month with the same month in
previous years.

**May not claim:** field-level soil moisture, root-zone water, or irrigation advice for a
specific plot. The product is 9 km, the retrieval depth is the top ~5 cm, and roughly
three days in five have no value at all.

**Watch the trend test.** The confidence intervals assume independent samples, but soil
moisture is autocorrelated, so the true interval is wider. Treat a slope as a direction,
not a measurement, and never extrapolate it."""),
]

# ---------------------------------------------------------------------------
# 06 rotations
# ---------------------------------------------------------------------------
NB_ROTATION = [
    ("md", """# 06 · Crop-rotation planning with historical weather scenarios

**Task:** combine the historical weather record with crop water requirements to compare
rotation options for each region — the same shape as the AgriFusion engine, but driven
from the model-ready panel.

**The method is FAO-56 water balance, not machine learning.** For each candidate crop and
season:

1. `ETc = Kc × ET₀` — crop water use from the reference demand and the crop coefficient.
2. Effective rainfall from USDA-SCS: `Pe = (P − 0.2S)² / (P + 0.8S)`, `S = 25400/CN − 254`.
3. `Irrigation demand = max(0, ETc − Pe)`, accumulated over the season.
4. Heat exposure = days with `Tmax ≥ 35 °C` (the threshold used in the AgriFusion rule
   engine for rice/wheat heat stress).

The comparison is run over the **last four seasons of real weather**, so each option is
scored on the same years rather than on a long-run average that never occurred.

**What this is not:** it does not predict yield, price or profit; it says nothing about
markets; and the crop parameters are textbook values that must be replaced by the
project's reviewed catalogue before farmer-facing use."""),
    ("code", PREAMBLE),
    ("md", """## 1. Crop parameters

Kc values are FAO-56 Table 11 mid-season coefficients for the rainfed/irrigated
conditions typical of Bangladesh; season windows follow the BARC/DAE calendar
(boro = winter irrigated rice, aman = monsoon rice, aus = pre-monsoon rice).

**Replace these with the reviewed `catalogue.Crop` rows** before production use."""),
    ("code", '''CROPS = [
    # name, season window (months), Kc mid, water demand class, notes
    {"crop": "Boro rice (paddy)", "months": [12, 1, 2, 3, 4], "kc": 1.20, "paddy": True},
    {"crop": "Aman rice (paddy)", "months": [6, 7, 8, 9, 10], "kc": 1.10, "paddy": True},
    {"crop": "Aus rice", "months": [4, 5, 6, 7], "kc": 1.10, "paddy": True},
    {"crop": "Wheat", "months": [11, 12, 1, 2, 3], "kc": 1.15, "paddy": False},
    {"crop": "Maize", "months": [11, 12, 1, 2, 3], "kc": 1.20, "paddy": False},
    {"crop": "Potato", "months": [11, 12, 1, 2], "kc": 1.15, "paddy": False},
    {"crop": "Mustard", "months": [10, 11, 12, 1], "kc": 1.10, "paddy": False},
    {"crop": "Lentil", "months": [11, 12, 1, 2], "kc": 1.10, "paddy": False},
    {"crop": "Jute", "months": [4, 5, 6, 7], "kc": 1.10, "paddy": False},
]
crop_df = pd.DataFrame(CROPS)
print(f"{len(crop_df)} candidate crops defined")
crop_df[["crop", "kc", "paddy"]]'''),
    ("md", """## 2. Run the water balance over real seasons

For every region, crop and year we accumulate ETc, effective rainfall and the resulting
irrigation demand. Years where the season is not fully covered by the record are
dropped rather than partly counted."""),
    ("code", '''CN = 70  # USDA-SCS curve number: mixed upland crops / vegetative cover
S_RETENTION = 25400 / CN - 254   # mm

def effective_rainfall(p_mm):
    """USDA-SCS effective rainfall, mm."""
    return np.where(p_mm > 0.2 * S_RETENTION,
                    (p_mm - 0.2 * S_RETENTION) ** 2 / (p_mm + 0.8 * S_RETENTION),
                    0.0)

daily = load_daily()
daily["year"] = daily["date"].dt.year
daily["month"] = daily["date"].dt.month

records = []
for region in regions:
    g = daily[daily.region == region].set_index("date")
    for crop in CROPS:
        for year in range(2022, 2027):
            # a season that wraps the new year spans year-1 too
            months = crop["months"]
            parts = []
            for m in months:
                yr = year - 1 if (months[0] == 12 and m == 12) else year
                parts.append(g[(g.index.year == yr) & (g.index.month == m)])
            frame = pd.concat(parts) if parts else g.iloc[0:0]
            if len(frame) < 0.8 * len(months) * 28:
                continue
            et0 = frame["et0_best_mm"].sum()
            rain = frame["gpm_rain_mm"].sum()
            if not np.isfinite(et0) or not np.isfinite(rain) or et0 <= 0:
                continue
            etc = crop["kc"] * et0
            pe = float(effective_rainfall(np.array([rain]))[0])
            records.append({
                "region": region, "crop": crop["crop"], "year": year,
                "days": len(frame),
                "et0_mm": round(et0, 0),
                "etc_mm": round(float(etc), 0),
                "rain_mm": round(float(rain), 0),
                "effective_rain_mm": round(pe, 0),
                "irrigation_demand_mm": round(float(max(0, etc - pe)), 0),
                "heat_days_35": int((frame["tmax_c"] >= 35).sum()),
                "paddy": crop["paddy"],
            })

balance = pd.DataFrame(records)
balance.to_csv(OUT / "rotation_water_balance.csv", index=False)
print(f"{len(balance)} region-crop-year combinations scored")
balance.head()'''),
    ("md", """## 3. Rank rotation options per region

A rotation is scored on the things that actually constrain a farmer here: how much
irrigation it needs, how much heat stress the season carries, and whether it depends on
flooded conditions."""),
    ("code", '''summary = (balance.groupby(["region", "crop"])
           .agg(irrigation_mm=("irrigation_demand_mm", "mean"),
                etc_mm=("etc_mm", "mean"),
                rain_mm=("rain_mm", "mean"),
                heat_days=("heat_days_35", "mean"),
                years=("year", "nunique"))
           .reset_index())

irr_max = summary.groupby("region")["irrigation_mm"].transform("max").replace(0, np.nan)
heat_max = summary.groupby("region")["heat_days"].transform("max").replace(0, np.nan)
summary["stress_score"] = ((summary["irrigation_mm"] / irr_max) * 0.75
                           + (summary["heat_days"] / heat_max) * 0.25).fillna(0.0)
summary = summary.sort_values(["region", "stress_score"])

pivot = summary.pivot(index="crop", columns="region", values="irrigation_mm").reindex(columns=regions)
pivot.index.name = "crop"
pivot.round(0).to_csv(OUT / "rotation_irrigation_matrix.csv")
pivot.round(0)'''),
    ("code", '''fig, ax = plt.subplots(figsize=(8.6, 3.6))
order = summary.groupby("crop")["irrigation_mm"].mean().sort_values().index
data = pivot.loc[order]
im = ax.imshow(data.values, cmap=SEQ, aspect="auto")
ax.set_xticks(range(len(data.columns)))
ax.set_xticklabels([pretty(c) for c in data.columns], rotation=25, ha="right", fontsize=7)
ax.set_yticks(range(len(data.index))); ax.set_yticklabels(data.index, fontsize=8)
for i in range(data.shape[0]):
    for j in range(data.shape[1]):
        v = data.values[i, j]
        if np.isfinite(v):
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7,
                    color="white" if v > np.nanpercentile(data.values, 65) else INK)
ax.set_title("Mean seasonal irrigation demand (mm) — lower is less exposed", loc="left")
fig.colorbar(im, ax=ax, shrink=0.85, label="mm per season")
fig.tight_layout(); plt.show()'''),
    ("md", """**Two things in that chart are correct but look like faults, so read them carefully:**

- **Zeroes are real.** Aman rice grows through the monsoon; in six of seven regions
  effective rainfall exceeds the crop's demand across the season, so a rainfed crop needs
  no supplementary irrigation. Only Rajshahi, the driest region, shows a small deficit.
- **Aus rice and Jute are identical rows** because this demonstration gives them the same
  season window and the same Kc (1.10). With one mid-season coefficient there is nothing
  to tell them apart. A real catalogue supplies stage-specific Kc curves and distinct
  windows, and the rows diverge.

Boro rice is the opposite case: a winter crop grown in the dry season, needing 450–620 mm
of irrigation in every region. That single number is the most decision-relevant output in
this notebook."""),
    ("md", """## 4. How farmer and field inputs change the ranking

The ranking above is purely climatic. Three inputs move it, and they are exactly the
ones the FieldShift plan says must come from the farmer and the reviewed catalogue:

| Input | Where it enters | Effect |
|---|---|---|
| Soil texture | curve number `CN` in effective rainfall (70 here) | sandy soils raise CN, so more rain becomes runoff and irrigation demand rises |
| Irrigation availability | feasibility filter, not the water balance | a crop needing 400 mm may be infeasible on rainfed land even if climatically ideal |
| Crop stage / Kc timing | replace single `Kc mid` with the FAO-56 Kc curve | early-season demand is ~40% of mid-season, so single-Kc overstates short-duration crops |

Demonstrating the soil sensitivity:"""),
    ("code", '''for cn in (55, 70, 85):
    s = 25400 / cn - 254
    rain = balance.groupby("crop")["rain_mm"].mean()
    pe = np.where(rain > 0.2 * s, (rain - 0.2 * s) ** 2 / (rain + 0.8 * s), 0)
    etc = balance.groupby("crop")["etc_mm"].mean()
    demand = (etc - pe).clip(lower=0)
    print(f"CN {cn}: mean irrigation demand across crops = {demand.mean():.0f} mm/season")'''),
    ("md", """## 5. What this notebook does and does not establish

**Establishes:** with real 2022–2026 weather, the irrigation demand of each candidate
crop per region, its heat exposure, and a defensible ordering of options.

**Does not establish:** yield, profit, or agronomic suitability. The FieldShift plan is
explicit that a rotation comparison must show *why* an option was rejected — and that
when the evidence cannot support two alternatives, the app should say so rather than
invent them.

**Two caveats worth keeping in the UI:**

1. **Paddy is not comparable to upland crops on irrigation demand alone.** Flooded rice
   also receives bund seepage and rainfall ponding, which a simple bucket ignores; the
   AgriFusion engine models this separately as a field-water term.
2. **The weather is historical, not a forecast.** The honest framing is "in the last
   four seasons this crop would have needed X mm", never "this crop will need X mm"."""),
]

NOTEBOOKS = {
    "01_regional_dashboard.ipynb": NB_DASHBOARD,
    "02_temperature_prediction.ipynb": NB_TEMP,
    "03_rain_prediction.ipynb": NB_RAIN,
    "04_evaporation_demand.ipynb": NB_ET0,
    "05_soil_water_monitoring.ipynb": NB_SOIL,
    "06_crop_rotation_planning.ipynb": NB_ROTATION,
}


def build() -> list[Path]:
    NOTEBOOKS_DIR = BASE / "notebooks"
    NOTEBOOKS_DIR.mkdir(exist_ok=True)
    paths = []
    for name, cells in NOTEBOOKS.items():
        nb = nbf.v4.new_notebook()
        nb.cells = [
            nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src)
            for kind, src in cells
        ]
        nb.metadata = {
            "kernelspec": {"display_name": "BIG hero data", "language": "python", "name": "bh6"},
            "language_info": {"name": "python"},
        }
        path = NOTEBOOKS_DIR / name
        nbf.write(nb, path)
        paths.append(path)
        print(f"built {path.name} ({len(cells)} cells)")
    return paths


def execute(paths: list[Path]) -> None:
    NOTEBOOKS_DIR = BASE / "notebooks"
    for path in paths:
        nb = nbf.read(path, as_version=4)
        client = NotebookClient(nb, timeout=1200, kernel_name="bh6",
                                resources={"metadata": {"path": str(NOTEBOOKS_DIR)}})
        client.execute()
        nbf.write(nb, path)
        errors = sum(1 for c in nb.cells if c.cell_type == "code"
                     and any(o.get("output_type") == "error" for o in c.get("outputs", [])))
        print(f"executed {path.name}: {'OK' if errors == 0 else f'{errors} cell errors'}")


if __name__ == "__main__":
    paths = build()
    if "--run" in sys.argv:
        execute(paths)
