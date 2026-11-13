# Application notebooks

Six runnable notebooks, one per use case, all reading `../model_ready/`. Every cell has
been executed and the outputs are stored in the files, so they read correctly on GitHub,
in VS Code, or in Jupyter without re-running.

| Notebook | Question it answers | Writes |
|---|---|---|
| `01_regional_dashboard.ipynb` | What do we know about each region now, and how fresh is it? | `outputs/dashboard_status.csv`, `current_status.csv` |
| `02_temperature_prediction.ipynb` | Can we forecast temperature 1 and 3 days ahead, and does it beat persistence? | `temperature_scores.csv`, `temperature_skill.csv` |
| `03_rain_prediction.ipynb` | How likely is rain tomorrow, and how much if it comes? | `rain_occurrence_scores.csv`, `rain_amount_scores.csv`, `rain_next_day_forecasts.csv` |
| `04_evaporation_demand.ipynb` | What is reference ET₀, how seasonal is it, and can it be forecast? | `et0_scores.csv`, `et0_anomaly_scores.csv` |
| `05_soil_water_monitoring.ipynb` | What is the filtered soil-moisture trend, and where does today sit in the record? | `soil_moisture_trends.csv`, `soil_moisture_state.csv` |
| `06_crop_rotation_planning.ipynb` | Which rotations need the least irrigation and carry the least heat risk? | `rotation_water_balance.csv`, `rotation_irrigation_matrix.csv` |

## Running them

```powershell
cd "C:\Users\muhai\Desktop\BIG hero 6\Data"
.\.venv\Scripts\python.exe -m ipykernel install --user --name bh6 --display-name "BIG hero data"   # once
.\.venv\Scripts\python.exe build_notebooks.py --run      # rebuild + execute all six
```

Or open the folder in VS Code / Jupyter and pick the **BIG hero data** kernel.

Rebuild the panels first if the source CSVs changed:

```powershell
.\.venv\Scripts\python.exe build_model_ready.py
```

## Conventions every notebook follows

- **Time-based splits.** Train 2022–2024, validation 2025, test 2026. No shuffling — daily
  environmental series are strongly autocorrelated and a random split leaks the future.
- **A baseline in every table.** Persistence and climatology are always reported beside
  the model. A score with no baseline is not a result.
- **Missing stays missing.** No zero-filling and no blanket interpolation; sparse
  satellite values carry an age column and are filtered, not invented.
- **Outputs are files, not just printed numbers**, so results can be diffed and cited.

## What the numbers say

| Notebook | Headline result |
|---|---|
| 01 Dashboard | Every region shows the same seasonal shape but a 2.8× range in rainfall; NDVI has genuine gaps in June and August (monsoon cloud). |
| 02 Temperature | Persistence is strong at 1 day (R² 0.96); models add skill mainly at 3 days (+0.16 skill score). |
| 03 Rain | Wet-day probability is well calibrated (AUC 0.90, Brier 0.126 vs 0.150 base rate). Gamma-loss amount model beats squared error (MAE 8.2 vs 10.9 mm). |
| 04 ET₀ | Ridge R² 0.57 raw; on the anomaly (season removed) still 0.61 vs 0.51 persistence — a one-day persistence effect, which disappears at monthly scale. |
| 05 Soil moisture | All seven regions trend downward ~0.005–0.038 m³/m³ per year over this short window; treat as descriptive, not climate. |
| 06 Rotations | Boro rice needs 450–620 mm of irrigation in every region; aman rice needs none except in Rajshahi. |

## Caveats that apply to all six

The record is under five years, the seven points are single coordinates, and no value is a
measurement at a farm. These notebooks demonstrate method and give defensible regional
context; they do not constitute validated agronomic advice.
