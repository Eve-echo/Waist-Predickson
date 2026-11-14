"""STEP 1 - create data/waste.db from the  Waste_Management_India_20K.csv the ML script uses.

    python Script/seed_db.py --data data/Waste_Management_India_20K.csv --reset

Fills: cities, city_months, bin_inventory, users (demo).
The aggregation copies the ML script (sum waste over waste types, mean the rest)
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from Backend import db  # noqa: E402

TARGET = "Daily_Waste_Generation_Tons"
GROUP = ["City", "State", "Region", "Year", "Month"]
BIN_KG = 100.0  

p = argparse.ArgumentParser()
p.add_argument("--data", default=str(ROOT / "data" / "Waste_Management_India_20K.csv"))
p.add_argument("--reset", action="store_true", help="drop and re-create all tables first")
a = p.parse_args()

raw = pd.read_csv(a.data)
missing = [c for c in GROUP + [TARGET, "Waste_Type", "Population"] if c not in raw.columns]
if missing:
    sys.exit(f"CSV is missing columns {missing}.\nColumns found: {list(raw.columns)}\n"
             "Are you using Waste_Management_India_20K.csv (the file the ML script reads)?")

#same cleaning as the ML script 
df = raw.copy()
for c in ["Year", "Month", TARGET, "Population"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df["Date"] = pd.to_datetime(dict(year=df["Year"], month=df["Month"], day=1), errors="coerce")
df = df.dropna(subset=GROUP + [TARGET, "Date", "Population"])
df = df[df["Month"].between(1, 12) & (df["Population"] > 0)]
n_future = int((df["Date"] > pd.Timestamp.today().normalize()).sum())
df = df[df["Date"] <= pd.Timestamp.today().normalize()]

agg = {TARGET: "sum", "Waste_Type": "nunique", "Population": "mean"}
for col, fn in [("Garbage_Collection_Frequency", "mean"), ("Waste_Processing_Capacity", "sum"),
                ("Smart_Bins_Count", "mean"), ("Latitude", "mean"), ("Longitude", "mean"),
                ("City_Category", "first")]:
    if col in df.columns:
        agg[col] = fn
m = df.groupby(GROUP, as_index=False).agg(agg)
m["period_start"] = pd.to_datetime(dict(year=m["Year"].astype(int), month=m["Month"].astype(int), day=1)
                                   ).dt.strftime("%Y-%m-%d")
for col in ["Garbage_Collection_Frequency", "Waste_Processing_Capacity", "Smart_Bins_Count",
            "Latitude", "Longitude", "City_Category"]:
    if col not in m.columns:
        m[col] = np.nan

conn = db.get_conn()
db.init_db(conn, reset=a.reset)

#cities 
cities = (m.groupby(["City", "State"], as_index=False)
            .agg(zone=("Region", "first"), city_category=("City_Category", "first"),
                 latitude=("Latitude", "mean"), longitude=("Longitude", "mean")))
conn.executemany(
    "INSERT OR IGNORE INTO cities (city, state, zone, city_category, latitude, longitude) VALUES (?,?,?,?,?,?)",
    [(r.City, r.State, r.zone, None if pd.isna(r.city_category) else r.city_category,
      None if pd.isna(r.latitude) else float(r.latitude),
      None if pd.isna(r.longitude) else float(r.longitude)) for r in cities.itertuples()])
conn.commit()
ids = {(r["city"], r["state"]): r["id"] for r in conn.execute("SELECT id, city, state FROM cities")}


def nn(x):
    return None if pd.isna(x) else float(x)


#city_months (real history)
conn.execute("DELETE FROM city_months")
conn.executemany(
    """INSERT INTO city_months (city_id, period_start, waste_tons_per_day, observed_waste_types, population,
                                collection_cycles_per_week, processing_capacity, smart_bins)
       VALUES (?,?,?,?,?,?,?,?)""",
    [(ids[(r.City, r.State)], r.period_start, float(getattr(r, TARGET)), int(r.Waste_Type), nn(r.Population),
      nn(r.Garbage_Collection_Frequency), nn(r.Waste_Processing_Capacity), nn(r.Smart_Bins_Count))
     for r in m.itertuples()])
conn.commit()

#bin_inventory (ASSUMPTION) 
# The dataset has no real bin inventory (Smart_Bins_Count is NOT total bins). For the demo we
# assume each city has ~85-110% of the bins its latest month needed (ML formula, 100 kg bins).
# These rows are tagged source='assumed'. Replace with real numbers or edit them in the app.
rng = np.random.default_rng(42)
latest = m.sort_values("period_start").groupby(["City", "State"]).tail(1)
for r in latest.itertuples():
    cycles = r.Garbage_Collection_Frequency
    cycles = 7.0 if (pd.isna(cycles) or cycles <= 0) else float(cycles)
    need = np.ceil(getattr(r, TARGET) * 1000 * 7 / (BIN_KG * cycles))
    conn.execute("INSERT OR IGNORE INTO bin_inventory (city_id, bins_deployed, kg_per_bin, collections_per_week, source) "
                 "VALUES (?,?,?,?, 'assumed')",
                 (ids[(r.City, r.State)], int(np.ceil(need * rng.uniform(0.85, 1.10))), BIN_KG, cycles))
conn.commit()

# demo users 
db.create_user(conn, "admin", "admin123", "admin")
db.create_user(conn, "officer", "officer123", "officer")

# summary 
q = lambda s: conn.execute(s).fetchone()[0]
print(f"Database: {db.DB_PATH}")
print(f"  raw rows read        {len(raw):,}  (future-dated rows dropped: {n_future})")
print(f"  cities               {q('SELECT COUNT(*) FROM cities')}")
print(f"  city_months          {q('SELECT COUNT(*) FROM city_months')}   "
      f"({q('SELECT MIN(period_start) FROM city_months')} to {q('SELECT MAX(period_start) FROM city_months')})")
print(f"  bin_inventory        {q('SELECT COUNT(*) FROM bin_inventory')}   (ASSUMED values)")
print(f"  avg waste types reported per city-month: {q('SELECT AVG(observed_waste_types) FROM city_months'):.1f} of 9")
print("  -> if this is well below 9, city totals undercount waste (the ML README warns about this).")
print("\nDemo logins: admin / admin123, officer / officer123 (change before any real use)")
print("Next: run the ML script, then  python Script/load_ml_output.py --ml-dir RESULT_4")
