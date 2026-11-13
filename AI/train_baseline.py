"""Reference models for the model-ready panels.

Not a product model - a check that the feature tables are usable and an honest
baseline to beat. Time-based split, persistence and climatology baselines,
then ridge and gradient boosting, with permutation importance.

Writes model_ready/baseline_results.json and prints a summary table.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

BASE = Path(__file__).resolve().parent
OUT = BASE / "model_ready"

TARGETS = {
    "rain_next_day": ("daily_panel.csv", "target_rain_next_day_mm", "gpm_rain_mm"),
    "soil_moisture_next_day": ("daily_panel.csv", "target_sm_next_day", "sm_mean"),
    "et0_next_day": ("daily_panel.csv", "target_et0_next_day_mm", "et0_best_mm"),
    "ndvi_next_month": ("monthly_panel.csv", "ndvi_next_month", "ndvi"),
}

SPLIT = {
    "train": ("2022-01-01", "2024-12-31"),
    "valid": ("2025-01-01", "2025-12-31"),
    "test": ("2026-01-01", "2026-12-31"),
}


def prepare(table: str, target: str) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    df = pd.read_csv(OUT / table, parse_dates=["date"])
    df = df.sort_values(["region", "date"]).reset_index(drop=True)

    feature_cols = [
        c
        for c in df.columns
        if c not in ("region", "date", "season")
        and not c.startswith(("target_", "ndvi_next_month", "sm_next_month", "rain_next_month"))
        and pd.api.types.is_numeric_dtype(df[c])
    ]
    X = df[feature_cols].copy()
    # region as one-hot: climate differences are real, not noise
    region_dummies = pd.get_dummies(df["region"], prefix="region", dtype=float)
    X = pd.concat([X, region_dummies], axis=1)

    y = df[target]
    return X, y, df["date"]


def evaluate(name: str, y_true, y_pred) -> dict:
    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    if ok.sum() < 10:
        return {}
    return {
        "n": int(ok.sum()),
        "mae": round(float(mean_absolute_error(y_true[ok], y_pred[ok])), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true[ok], y_pred[ok]))), 4),
        "r2": round(float(r2_score(y_true[ok], y_pred[ok])), 4),
    }


def run_target(key: str, table: str, target: str, persistence_col: str) -> dict:
    X, y, dates = prepare(table, target)
    tr = (dates >= SPLIT["train"][0]) & (dates <= SPLIT["train"][1])
    va = (dates >= SPLIT["valid"][0]) & (dates <= SPLIT["valid"][1])
    te = (dates >= SPLIT["test"][0]) & (dates <= SPLIT["test"][1])
    usable = y.notna()
    tr, va, te = tr & usable, va & usable, te & usable

    if tr.sum() < 100 or te.sum() < 20:
        return {"skipped": f"not enough rows (train={int(tr.sum())}, test={int(te.sum())})"}

    result = {"rows": {"train": int(tr.sum()), "valid": int(va.sum()), "test": int(te.sum())}}

    # --- persistence baseline: tomorrow looks like today
    if persistence_col in X.columns:
        persistence = X[persistence_col].to_numpy()
        result["persistence"] = evaluate(key, y[te].to_numpy(), persistence[te.to_numpy()])

    # --- climatology baseline: the average for that calendar month
    train_df = pd.DataFrame({"m": dates[tr].dt.month, "y": y[tr]})
    clim = train_df.groupby("m")["y"].mean()
    clim_pred = dates[te].dt.month.map(clim).to_numpy(dtype=float)
    result["climatology"] = evaluate(key, y[te].to_numpy(), clim_pred)

    # --- ridge on median-imputed, scaled features
    ridge = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=1.0))
    ridge.fit(X[tr], y[tr])
    result["ridge"] = evaluate(key, y[te].to_numpy(), ridge.predict(X[te]))

    # --- gradient boosting handles NaN natively
    gbr = HistGradientBoostingRegressor(
        max_iter=400,
        learning_rate=0.06,
        max_depth=None,
        min_samples_leaf=20,
        l2_regularization=1.0,
        random_state=0,
    )
    gbr.fit(X[tr], y[tr])
    result["gradient_boosting"] = evaluate(key, y[te].to_numpy(), gbr.predict(X[te]))

    # --- what the model actually leans on
    sample = X[te].sample(min(1500, int(te.sum())), random_state=0)
    idx = sample.index
    y_sample = y.loc[idx]
    imp = permutation_importance(
        gbr, sample, y_sample, n_repeats=5, random_state=0, scoring="neg_mean_absolute_error"
    )
    order = np.argsort(imp.importances_mean)[::-1][:12]
    result["top_features"] = [
        {"feature": X.columns[i], "importance": round(float(imp.importances_mean[i]), 4)}
        for i in order
        if imp.importances_mean[i] > 0
    ]
    return result


def main() -> int:
    results = {}
    for key, (table, target, persistence) in TARGETS.items():
        print(f"--- {key} ---")
        try:
            results[key] = run_target(key, table, target, persistence)
        except Exception as exc:  # noqa: BLE001
            results[key] = {"error": str(exc)}
            print(f"  failed: {exc}")

    (OUT / "baseline_results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")

    print(f"\n{'target':26s} {'model':20s} {'n':>6s} {'MAE':>8s} {'RMSE':>8s} {'R2':>7s}")
    for key, res in results.items():
        if "skipped" in res or "error" in res:
            print(f"{key:26s} {str(res)[:60]}")
            continue
        for model in ("persistence", "climatology", "ridge", "gradient_boosting"):
            if model in res and res[model]:
                m = res[model]
                print(f"{key:26s} {model:20s} {m['n']:6d} {m['mae']:8.3f} {m['rmse']:8.3f} {m['r2']:7.3f}")
    print(f"\nSaved {OUT / 'baseline_results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
