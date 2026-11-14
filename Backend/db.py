"""SQLite data layer for the Waste Forecast dashboard.

Mirrors the output of Script/script.py: monthly, city-level predictions from several
models, with bin counts that are scenario proxies. The database file is data/waste.db and
is built by Script/seed_db.py and Script/load_ml_output.py.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("WASTE_DB", ROOT / "data" / "waste.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'officer'            -- 'admin' | 'officer'
);

-- One row per city. (In the dashboard, "region" = city. The CSV's "Region" column is the
-- geographic zone such as North/South, stored here as `zone`.)
CREATE TABLE IF NOT EXISTS cities (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    city           TEXT NOT NULL,
    state          TEXT NOT NULL,
    zone           TEXT,
    city_category  TEXT,
    city_size_tier TEXT,                                      -- Small/Medium/Large, from the ML output
    latitude       REAL,
    longitude      REAL,
    UNIQUE (city, state)
);

-- Actual history: one row per city per month
-- (waste summed over the waste types present, other columns averaged).
CREATE TABLE IF NOT EXISTS city_months (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    city_id                    INTEGER NOT NULL REFERENCES cities(id),
    period_start               TEXT NOT NULL,                 -- 'YYYY-MM-01'
    waste_tons_per_day         REAL NOT NULL,
    observed_waste_types       INTEGER,                       -- how many of the 9 waste types were reported
    population                 REAL,
    collection_cycles_per_week REAL,                          -- from Garbage_Collection_Frequency
    processing_capacity        REAL,
    smart_bins                 REAL,
    UNIQUE (city_id, period_start)
);

-- One row each time the ML script's results are loaded.
CREATE TABLE IF NOT EXISTS model_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT NOT NULL,
    source_dir      TEXT,
    selected_model  TEXT,                                     -- chosen by the ML script using CV only
    selection_basis TEXT,
    bin_capacity_kg REAL,                                     -- assumption used by the ML script
    test_from       TEXT,
    test_through    TEXT,
    notes           TEXT
);

-- Accuracy per model per run (from holdout_model_comparison.csv).
CREATE TABLE IF NOT EXISTS model_metrics (
    run_id         INTEGER NOT NULL REFERENCES model_runs(id),
    model_name     TEXT NOT NULL,
    waste_mae      REAL,
    waste_rmse     REAL,
    waste_r2       REAL,
    waste_wape_pct REAL,
    bin_mae        REAL,
    bin_wape_pct   REAL,
    is_selected    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, model_name)
);

-- Predictions. kind='holdout' = model predictions for months whose actual value is known.
-- kind='future' = real forecasts (empty until added forecast-next-month step).
CREATE TABLE IF NOT EXISTS forecasts (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                 INTEGER NOT NULL REFERENCES model_runs(id),
    city_id                INTEGER NOT NULL REFERENCES cities(id),
    period_start           TEXT NOT NULL,
    model_name             TEXT NOT NULL,
    kind                   TEXT NOT NULL DEFAULT 'holdout' CHECK (kind IN ('holdout', 'future')),
    predicted_tons_per_day REAL,
    predicted_bins         REAL,                              -- weekly bins proxy computed by the ML script
    q10_bins               REAL,                              -- only the quantile model has these
    q90_bins               REAL,
    actual_tons_per_day    REAL,                              -- NULL for kind='future'
    UNIQUE (run_id, city_id, period_start, model_name, kind)
);

-- Bins currently deployed. The dataset has NO real bin inventory, so values start as
-- ASSUMPTIONS (source='assumed') until municipal staff edit them (source='municipal').
CREATE TABLE IF NOT EXISTS bin_inventory (
    city_id              INTEGER PRIMARY KEY REFERENCES cities(id),
    bins_deployed        INTEGER NOT NULL,
    kg_per_bin           REAL NOT NULL DEFAULT 100,
    collections_per_week REAL NOT NULL DEFAULT 7,
    source               TEXT NOT NULL DEFAULT 'assumed',
    updated_at           TEXT,
    updated_by           TEXT
);

CREATE INDEX IF NOT EXISTS idx_cm_city   ON city_months(city_id, period_start);
CREATE INDEX IF NOT EXISTS idx_fc_lookup ON forecasts(run_id, model_name, period_start);
"""


def get_conn(path: Path | str | None = None) -> sqlite3.Connection:
    p = Path(path or DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection, reset: bool = False) -> None:
    if reset:
        for t in ("forecasts", "model_metrics", "model_runs", "bin_inventory",
                  "city_months", "cities", "users"):
            conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.executescript(SCHEMA)
    conn.commit()


#  users / login
def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    return salt.hex() + "$" + hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()


def create_user(conn, username: str, password: str, role: str = "officer") -> None:
    conn.execute("INSERT OR REPLACE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                 (username, hash_password(password), role))
    conn.commit()


def verify_user(conn, username: str, password: str):
    """Return {'username','role'} if valid, else None."""
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        return None
    salt_hex, digest_hex = row["password_hash"].split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000).hex()
    return {"username": row["username"], "role": row["role"]} if hmac.compare_digest(digest, digest_hex) else None



def latest_run(conn):
    """The newest ML run, or None if no results were loaded yet."""
    return conn.execute("SELECT * FROM model_runs ORDER BY id DESC LIMIT 1").fetchone()


def _city_id(conn, city: str):
    r = conn.execute("SELECT id FROM cities WHERE city = ? ORDER BY id LIMIT 1", (city,)).fetchone()
    return r["id"] if r else None


def get_periods(conn, model_name: str | None = None) -> list[str]:
    """Months with predictions in the latest run, newest first."""
    run = latest_run(conn)
    if run is None:
        return []
    rows = conn.execute(
        "SELECT DISTINCT period_start FROM forecasts WHERE run_id = ? AND model_name = ? "
        "ORDER BY period_start DESC", (run["id"], model_name or run["selected_model"])).fetchall()
    return [r["period_start"] for r in rows]


#  reads for the dashboard
def get_cities(conn) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM cities ORDER BY city", conn)


def get_history(conn, city: str) -> pd.DataFrame:
    """Actual monthly waste for one city (for the Region trend chart)."""
    return pd.read_sql(
        """SELECT m.period_start, m.waste_tons_per_day, m.observed_waste_types
           FROM city_months m JOIN cities c ON c.id = m.city_id
           WHERE c.city = ? ORDER BY m.period_start""", conn, params=(city,))


def get_predictions(conn, city: str | None = None, model_name: str | None = None,
                    kind: str | None = None) -> pd.DataFrame:
    """Predictions from the latest run (default model = the one the ML script selected)."""
    run = latest_run(conn)
    if run is None:
        return pd.DataFrame()
    model_name = model_name or run["selected_model"]
    q = """SELECT c.city, f.period_start, f.kind, f.predicted_tons_per_day, f.predicted_bins,
                  f.q10_bins, f.q90_bins, f.actual_tons_per_day
           FROM forecasts f JOIN cities c ON c.id = f.city_id
           WHERE f.run_id = ? AND f.model_name = ?"""
    params: list = [run["id"], model_name]
    if city:
        q += " AND c.city = ?"; params.append(city)
    if kind:
        q += " AND f.kind = ?"; params.append(kind)
    return pd.read_sql(q + " ORDER BY c.city, f.period_start", conn, params=params)


def get_model_metrics(conn) -> pd.DataFrame:
    """Accuracy of every model in the latest run (selected model flagged)."""
    run = latest_run(conn)
    if run is None:
        return pd.DataFrame()
    return pd.read_sql("SELECT * FROM model_metrics WHERE run_id = ? ORDER BY waste_wape_pct",
                       conn, params=(run["id"],))


def get_capacity_summary(conn, period_start: str | None = None, model_name: str | None = None,
                         kind: str | None = None) -> pd.DataFrame:
    """One row per city for one month: predicted waste, bins needed (ML proxy), bins deployed,
    bins to add, priority. Powers the Overview, Forecast and Bin capacity pages."""
    run = latest_run(conn)
    if run is None:
        return pd.DataFrame()
    model_name = model_name or run["selected_model"]
    where, params = "f.run_id = ? AND f.model_name = ?", [run["id"], model_name]
    if kind:
        where += " AND f.kind = ?"; params.append(kind)
    if period_start is None:
        r = conn.execute(f"SELECT MAX(f.period_start) AS p FROM forecasts f WHERE {where}", params).fetchone()
        period_start = r["p"]
    t = pd.read_sql(
        f"""SELECT c.city, c.state, c.zone, c.city_size_tier, c.latitude, c.longitude,
                   f.period_start, f.predicted_tons_per_day, f.predicted_bins,
                   f.q10_bins, f.q90_bins, f.actual_tons_per_day,
                   cm.processing_capacity,
                   b.bins_deployed, b.source AS bins_source
            FROM forecasts f
            JOIN cities c ON c.id = f.city_id
            LEFT JOIN city_months cm ON cm.city_id = c.id AND cm.period_start = f.period_start
            LEFT JOIN bin_inventory b ON b.city_id = c.id
            WHERE {where} AND f.period_start = ?""", conn, params=params + [period_start])
    if t.empty:
        return t
    t["bins_to_add"] = (t["predicted_bins"] - t["bins_deployed"].fillna(0)).clip(lower=0).fillna(0)
    t = t.sort_values("predicted_tons_per_day", ascending=False).reset_index(drop=True)
    t.insert(0, "rank", t.index + 1)
    n = len(t)
    t["priority"] = np.where(t.index < np.ceil(n / 3), "High",
                             np.where(t.index < np.ceil(2 * n / 3), "Medium", "Low"))
    return t


#  writes
def update_bins_many(conn, changes: dict[str, int], user: str = "officer") -> int:
    """Save edited bin counts ({city: bins_deployed}) in one transaction. Returns rows written."""
    now = datetime.now().isoformat(timespec="seconds")
    rows = []
    for city, bins in changes.items():
        cid = _city_id(conn, city)
        if cid is None:
            raise ValueError(f"Unknown city: {city!r}")
        if int(bins) < 0:
            raise ValueError(f"Bins deployed cannot be negative ({city}: {bins})")
        rows.append((cid, int(bins), now, user))
    with conn:
        conn.executemany(
            """INSERT INTO bin_inventory (city_id, bins_deployed, source, updated_at, updated_by)
               VALUES (?, ?, 'municipal', ?, ?)
               ON CONFLICT(city_id) DO UPDATE SET
                   bins_deployed = excluded.bins_deployed, source = 'municipal',
                   updated_at = excluded.updated_at, updated_by = excluded.updated_by""", rows)
    return len(rows)


def update_bins(conn, city: str, bins_deployed: int, user: str = "officer") -> None:
    update_bins_many(conn, {city: bins_deployed}, user)