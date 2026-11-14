"""STEP 2 - load the ML script's results into the database. 

    python Script/load_ml_output.py --ml-dir RESULT_4

Reads from the ML output folder:
    result4_report.json          -> model_runs (which model was selected, assumptions, test period)
    holdout_model_comparison.csv -> model_metrics (MAE / RMSE / R2 / WAPE per model)
    holdout_predictions.csv      -> forecasts (per city, month and model)
Each run adds a new model_runs row; the dashboard always uses the newest one.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from Backend import db  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--ml-dir", default=str(ROOT / "RESULT_4"))
a = p.parse_args()
d = Path(a.ml_dir)
need = ["result4_report.json", "holdout_model_comparison.csv", "holdout_predictions.csv"]
absent = [f for f in need if not (d / f).exists()]
if absent:
    sys.exit(f"Missing {absent} in {d}. Run the ML script first (python Script/script.py).")

report = json.loads((d / "result4_report.json").read_text())
metrics = pd.read_csv(d / "holdout_model_comparison.csv")
pred = pd.read_csv(d / "holdout_predictions.csv")

conn = db.get_conn()
db.init_db(conn)
ids = {(r["city"], r["state"]): r["id"] for r in conn.execute("SELECT id, city, state FROM cities")}
if not ids:
    sys.exit("No cities in the database. Run Script/seed_db.py first.")

selected = report.get("best_model_selected_using_cv_only")
split = report.get("split", {})
kg = report.get("bin_proxy_assumptions", {}).get("bin_capacity_kg")
cur = conn.execute(
    "INSERT INTO model_runs (created_at, source_dir, selected_model, selection_basis, bin_capacity_kg, test_from, test_through) "
    "VALUES (?,?,?,?,?,?,?)",
    (datetime.now().isoformat(timespec="seconds"), str(d), selected, report.get("selection_basis"),
     kg, split.get("test_from"), split.get("test_through")))
run_id = cur.lastrowid


def nn(x):
    return None if pd.isna(x) else float(x)


#model_metrics 
col = lambda r, k: nn(r[k]) if k in r.index else None
conn.executemany(
    "INSERT INTO model_metrics (run_id, model_name, waste_mae, waste_rmse, waste_r2, waste_wape_pct, bin_mae, bin_wape_pct, is_selected) "
    "VALUES (?,?,?,?,?,?,?,?,?)",
    [(run_id, r["model"], col(r, "Waste_MAE_tons_day"), col(r, "Waste_RMSE_tons_day"), col(r, "Waste_R2"),
      col(r, "Waste_WAPE_pct"), col(r, "Bin_MAE_proxy"), col(r, "Bin_WAPE_proxy_pct"),
      int(r["model"] == selected)) for _, r in metrics.iterrows()])

#forecasts (one row per city x month x model) 
pred["period_start"] = pd.to_datetime(pred["Date"]).dt.strftime("%Y-%m-%d")
pred["city_id"] = [ids.get((c, s)) for c, s in zip(pred["City"], pred["State"])]
unknown = int(pred["city_id"].isna().sum())
pred = pred.dropna(subset=["city_id"])

models = [c.split("__", 1)[1] for c in pred.columns if c.startswith("pred_daily_tons__")]
rows = []
for name in models:
    is_q = name.startswith("Quantile")
    q10 = pred["q10_bins__Quantile_ANN"] if is_q and "q10_bins__Quantile_ANN" in pred else pd.Series(np.nan, index=pred.index)
    q90 = pred["q90_bins__Quantile_ANN"] if is_q and "q90_bins__Quantile_ANN" in pred else pd.Series(np.nan, index=pred.index)
    bins = pred.get(f"pred_bins__{name}", pd.Series(np.nan, index=pred.index))
    for cid, per, tons, b, lo, hi, act in zip(pred["city_id"], pred["period_start"], pred[f"pred_daily_tons__{name}"],
                                              bins, q10, q90, pred["Daily_Waste_Generation_Tons"]):
        rows.append((run_id, int(cid), per, name, "holdout", nn(tons), nn(b), nn(lo), nn(hi), nn(act)))
conn.executemany(
    "INSERT OR REPLACE INTO forecasts (run_id, city_id, period_start, model_name, kind, predicted_tons_per_day, "
    "predicted_bins, q10_bins, q90_bins, actual_tons_per_day) VALUES (?,?,?,?,?,?,?,?,?,?)", rows)

#city size tier (Small / Medium / Large) 
if "City_Size_Tier" in pred.columns:
    tier = pred.sort_values("period_start").groupby("city_id")["City_Size_Tier"].last()
    conn.executemany("UPDATE cities SET city_size_tier = ? WHERE id = ?", [(t, int(i)) for i, t in tier.items()])
conn.commit()

print(f"Loaded run #{run_id} from {d}")
print(f"  selected model : {selected}")
print(f"  models stored  : {len(models)}   forecast rows: {len(rows):,}   (rows with unknown city skipped: {unknown})")
print(f"  test period    : {split.get('test_from')} to {split.get('test_through')}")
s = db.get_capacity_summary(conn)
print("\nTop of the dashboard summary:")
print(s[["rank", "city", "period_start", "predicted_tons_per_day", "predicted_bins", "bins_deployed", "bins_to_add", "priority"]]
      .head(5).round(1).to_string(index=False))
