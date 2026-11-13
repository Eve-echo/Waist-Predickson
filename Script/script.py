from __future__ import annotations

import argparse
import json
import math
import random
import warnings
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import joblib
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from scipy.stats import pearsonr, chi2_contingency
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression
from sklearn.svm import LinearSVR
from sklearn.kernel_approximation import Nystroem
from sklearn.naive_bayes import GaussianNB
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)

warnings.filterwarnings("ignore")
torch.set_num_threads(1)

# -----------------------------------------------------------------------------
# USER CONFIGURATION — change these values if needed
# -----------------------------------------------------------------------------
DEFAULT_DATA_FILE = "Waste_Management_India_20K.csv"
DEFAULT_OUTPUT_DIR = "RESULT_4"
N_SPLITS = 5
TEST_FRACTION = 0.20
BIN_CAPACITY_KG = 100.0
COLLECTION_CYCLES_PER_WEEK_ASSUMED = True
RANDOM_SEED = 42
ANN_EPOCHS = 65
ANN_PATIENCE = 10
ANN_BATCH_SIZE = 256
MIN_SEGMENT_TRAIN_ROWS = 60
NYSTROEM_COMPONENTS = 200

TARGET_COL = "Daily_Waste_Generation_Tons"
CAPACITY_COL = "Waste_Processing_Capacity"
GROUP_COLS = ["City", "State", "Region", "Year", "Month"]

# Explicitly exclude columns that can be derived from waste generation or are
# outcome/performance labels. Source Waste_Per_Capita_KG is never a predictor.
RAW_NUMERIC_FEATURES = [
    "Population",
    "Population_Density",
    "Urbanization_Rate",
    "Collection_Efficiency_Percentage",
    "Waste_Segregation_Rate",
    "Recycling_Rate",
    "Composting_Rate",
    "Landfill_Dependency_Rate",
    "Waste_Processing_Capacity",
    "Municipal_Efficiency_Score",
    "Awareness_Campaigns_Count",
    "Smart_Bins_Count",
    "Waste_Collection_Vehicles",
    "Garbage_Collection_Frequency",
    "Worker_Count",
    "Waste_Management_Budget_INR",
    "Landfill_Capacity_Tons",
    "Landfill_Remaining_Capacity",
    "Latitude",
    "Longitude",
    "Air_Quality_Index",
    "Rainfall_MM",
    "Tourism_Impact_Score",
    "Industrial_Activity_Level",
    "Population_Growth_Rate",
]

RAW_CATEGORICAL_FEATURES = [
    "State",
    "Region",
    "City_Category",
    "Season",
    "Treatment_Method",
]


# -----------------------------------------------------------------------------
# Reproducibility and small utilities
# -----------------------------------------------------------------------------
def set_seed(seed: int = RANDOM_SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def safe_divide(a, b):
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce").replace(0, np.nan)
    return a / b


def make_one_hot_encoder():
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:  # compatibility with older scikit-learn versions
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def benjamini_hochberg(p_values: List[float]) -> np.ndarray:
    """Benjamini-Hochberg false-discovery-rate adjustment."""
    p = np.asarray(p_values, dtype=float)
    if len(p) == 0:
        return p
    p = np.where(np.isfinite(p), p, 1.0)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    adjusted_ranked = ranked * n / np.arange(1, n + 1)
    adjusted_ranked = np.minimum.accumulate(adjusted_ranked[::-1])[::-1]
    out = np.empty(n, dtype=float)
    out[order] = np.minimum(adjusted_ranked, 1.0)
    return out


def date_split_by_month(df: pd.DataFrame, test_fraction: float = TEST_FRACTION):
    """Chronological split by distinct month; no month is divided across sets."""
    dates = np.array(sorted(pd.to_datetime(df["Date"]).dropna().unique()))
    if len(dates) < 10:
        raise ValueError("Not enough distinct months for a chronological split.")
    cutoff_index = int(len(dates) * (1.0 - test_fraction))
    cutoff_index = min(max(cutoff_index, 1), len(dates) - 1)
    cutoff_date = pd.Timestamp(dates[cutoff_index])
    train = df[df["Date"] < cutoff_date].copy().sort_values(["Date", "City"])
    test = df[df["Date"] >= cutoff_date].copy().sort_values(["Date", "City"])
    return train.reset_index(drop=True), test.reset_index(drop=True), cutoff_date


# -----------------------------------------------------------------------------
# Step 1 — aggregate monthly waste-type rows into city-month observations
# -----------------------------------------------------------------------------
def aggregate_and_engineer(raw: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    required = GROUP_COLS + [TARGET_COL, "Waste_Type", "Population", "Garbage_Collection_Frequency"]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    df = raw.copy()
    for c in ["Year", "Month", TARGET_COL, "Population", CAPACITY_COL]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df["Date"] = pd.to_datetime(
        dict(year=df["Year"], month=df["Month"], day=1), errors="coerce"
    )
    df = df.dropna(subset=GROUP_COLS + [TARGET_COL, "Date", "Population"])
    df = df[df["Month"].between(1, 12) & (df["Population"] > 0)].copy()

    today = pd.Timestamp.today().normalize()
    future_mask = df["Date"] > today
    future_rows_excluded = int(future_mask.sum())
    df = df.loc[~future_mask].copy()

    if df.empty:
        raise ValueError("No valid historical observations remain after date cleaning.")

    # City-month generation is the sum over the waste types present in the CSV.
    aggregations = {
        TARGET_COL: "sum",
        "Waste_Type": "nunique",
    }
    if CAPACITY_COL in df.columns:
        aggregations[CAPACITY_COL] = "sum"

    for col in RAW_NUMERIC_FEATURES:
        if col in df.columns and col not in aggregations:
            aggregations[col] = "mean"
    for col in RAW_CATEGORICAL_FEATURES:
        if col in df.columns and col not in GROUP_COLS:
            aggregations[col] = "first"

    monthly = (
        df.groupby(GROUP_COLS, dropna=False)
        .agg(aggregations)
        .reset_index()
        .rename(columns={"Waste_Type": "Observed_Waste_Type_Count"})
    )

    # Waste-type presence flags. They describe what was actually reported;
    # they do not assert that unobserved waste types generated zero waste.
    flags = (
        df.assign(_present=1)
        .pivot_table(
            index=GROUP_COLS,
            columns="Waste_Type",
            values="_present",
            aggfunc="max",
            fill_value=0,
        )
        .reset_index()
    )
    flags.columns = [
        f"Has_WasteType_{c}" if c not in GROUP_COLS else c for c in flags.columns
    ]
    monthly = monthly.merge(flags, on=GROUP_COLS, how="left")

    monthly["Date"] = pd.to_datetime(
        dict(
            year=monthly["Year"].astype(int),
            month=monthly["Month"].astype(int),
            day=1,
        )
    )
    monthly["Month_Sin"] = np.sin(2 * np.pi * monthly["Month"] / 12.0)
    monthly["Month_Cos"] = np.cos(2 * np.pi * monthly["Month"] / 12.0)
    monthly["Waste_Type_Coverage_Share"] = monthly["Observed_Waste_Type_Count"] / 9.0

    # Operational and demographic feature engineering.
    monthly["Processing_Capacity_per_1000_People"] = safe_divide(
        monthly[CAPACITY_COL], monthly["Population"]
    ) * 1000.0
    monthly["Smart_Bins_per_10000_People"] = safe_divide(
        monthly["Smart_Bins_Count"], monthly["Population"]
    ) * 10000.0
    monthly["Vehicles_per_10000_People"] = safe_divide(
        monthly["Waste_Collection_Vehicles"], monthly["Population"]
    ) * 10000.0
    monthly["Workers_per_10000_People"] = safe_divide(
        monthly["Worker_Count"], monthly["Population"]
    ) * 10000.0
    monthly["Budget_per_Person"] = safe_divide(
        monthly["Waste_Management_Budget_INR"], monthly["Population"]
    )
    monthly["Landfill_Remaining_Ratio"] = safe_divide(
        monthly["Landfill_Remaining_Capacity"], monthly["Landfill_Capacity_Tons"]
    )
    monthly["Population_Density_x_Urbanization"] = (
        monthly["Population_Density"] * monthly["Urbanization_Rate"] / 100.0
    )
    monthly["Collection_Efficiency_x_Segregation"] = (
        monthly["Collection_Efficiency_Percentage"]
        * monthly["Waste_Segregation_Rate"]
        / 100.0
    )
    monthly["Recycling_Composting_Rate"] = (
        monthly["Recycling_Rate"] + monthly["Composting_Rate"]
    )
    monthly["Industrial_Activity_x_Urbanization"] = (
        monthly["Industrial_Activity_Level"] * monthly["Urbanization_Rate"] / 100.0
    )

    # Target: log1p of kg/person/day. Source Waste_Per_Capita_KG is NOT used.
    monthly["Waste_Per_Capita_Target_KG"] = safe_divide(
        monthly[TARGET_COL] * 1000.0, monthly["Population"]
    )
    monthly["Target_Log1p_Per_Capita"] = np.log1p(
        monthly["Waste_Per_Capita_Target_KG"].clip(lower=0)
    )

    monthly = monthly.replace([np.inf, -np.inf], np.nan)
    monthly = monthly.dropna(subset=["Target_Log1p_Per_Capita", "Population"])
    monthly = monthly.sort_values(["Date", "City"]).reset_index(drop=True)
    return monthly, future_rows_excluded


# -----------------------------------------------------------------------------
# Step 2 — city-size tiers; cut points learned only from each training partition
# -----------------------------------------------------------------------------
def fit_city_size_boundaries(train_df: pd.DataFrame) -> Dict[str, float]:
    city_population = (
        train_df.groupby(["City", "State"], dropna=False)["Population"]
        .median()
        .dropna()
    )
    if city_population.empty:
        return {"q33": 0.0, "q67": 0.0}
    return {
        "q33": float(city_population.quantile(1 / 3)),
        "q67": float(city_population.quantile(2 / 3)),
    }


def apply_city_size_tiers(df: pd.DataFrame, boundaries: Dict[str, float]) -> pd.DataFrame:
    out = df.copy()
    p = pd.to_numeric(out["Population"], errors="coerce")
    q1, q2 = boundaries["q33"], boundaries["q67"]
    out["City_Size_Tier"] = np.where(p <= q1, "Small", np.where(p <= q2, "Medium", "Large"))
    out["City_Size_Tier"] = pd.Series(out["City_Size_Tier"], index=out.index).fillna("Medium")
    return out


def population_tier_weights(tiers: pd.Series) -> np.ndarray:
    """Give Small/Medium/Large tiers equal total training weight."""
    labels = tiers.astype(str).to_numpy()
    values, counts = np.unique(labels, return_counts=True)
    count_map = dict(zip(values, counts))
    n = len(labels)
    k = max(len(values), 1)
    w = np.array([n / (k * count_map[x]) for x in labels], dtype=np.float32)
    # Stabilize optimization while preserving relative tier weights.
    w = np.clip(w, 0.25, 5.0)
    w = w / np.mean(w)
    return w


# -----------------------------------------------------------------------------
# Step 3 — fold-local Pearson + Chi-square feature selection
# -----------------------------------------------------------------------------
def _pearson_safe(x: pd.Series, y: np.ndarray) -> Tuple[float, float]:
    xx = pd.to_numeric(x, errors="coerce").to_numpy(dtype=float)
    yy = np.asarray(y, dtype=float)
    mask = np.isfinite(xx) & np.isfinite(yy)
    if mask.sum() < 10 or np.unique(xx[mask]).size < 2 or np.unique(yy[mask]).size < 2:
        return 0.0, 1.0
    try:
        r, p = pearsonr(xx[mask], yy[mask])
        if not np.isfinite(r) or not np.isfinite(p):
            return 0.0, 1.0
        return float(r), float(p)
    except Exception:
        return 0.0, 1.0


def _chi_square_safe(feature: pd.Series, target_bins: pd.Series) -> Tuple[float, float]:
    x = feature.astype("string").fillna("__MISSING__")
    table = pd.crosstab(x, target_bins)
    if table.shape[0] < 2 or table.shape[1] < 2:
        return 0.0, 1.0
    try:
        stat, p, _, _ = chi2_contingency(table)
        return float(stat), float(p)
    except Exception:
        return 0.0, 1.0


def _quantile_bins(series: pd.Series, q: int = 4) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    ranked = x.rank(method="first")
    try:
        return pd.qcut(ranked, q=q, labels=False, duplicates="drop")
    except Exception:
        return pd.Series(np.nan, index=series.index)


def select_features_train_only(
    train_df: pd.DataFrame,
    y_train: np.ndarray,
    numeric_candidates: List[str],
    categorical_candidates: List[str],
    alpha: float = 0.05,
    min_abs_pearson: float = 0.03,
    redundancy_threshold: float = 0.95,
):
    """Select features using the current training partition only."""
    y = pd.Series(np.asarray(y_train, dtype=float), index=train_df.index)
    target_bins = pd.qcut(
        y.rank(method="first"), q=min(4, max(2, y.nunique())),
        labels=False, duplicates="drop"
    )

    report_rows = []
    selected_numeric = []
    selected_categorical = []

    # Pearson test for numeric variables.
    pearson_results = []
    for col in numeric_candidates:
        r, p = _pearson_safe(train_df[col], y.to_numpy())
        pearson_results.append((col, r, p))
    pearson_q = benjamini_hochberg([x[2] for x in pearson_results])
    pearson_keep = {}
    for (col, r, p), q in zip(pearson_results, pearson_q):
        keep = bool(q < alpha and abs(r) >= min_abs_pearson)
        pearson_keep[col] = keep
        report_rows.append({
            "feature": col, "test": "Pearson vs log-per-capita target",
            "statistic": r, "p_value": p, "q_value_BH": float(q), "selected": keep,
        })

    # Chi-square for numeric variables after training-fold quartile binning.
    chi_numeric_results = []
    for col in numeric_candidates:
        x_bins = _quantile_bins(train_df[col])
        table = pd.crosstab(x_bins, target_bins)
        if table.shape[0] < 2 or table.shape[1] < 2:
            stat, p = 0.0, 1.0
        else:
            try:
                stat, p, _, _ = chi2_contingency(table)
            except Exception:
                stat, p = 0.0, 1.0
        chi_numeric_results.append((col, float(stat), float(p)))
    chi_numeric_q = benjamini_hochberg([x[2] for x in chi_numeric_results])
    for (col, stat, p), q in zip(chi_numeric_results, chi_numeric_q):
        keep = bool(q < alpha)
        if keep or pearson_keep.get(col, False):
            selected_numeric.append(col)
        report_rows.append({
            "feature": col, "test": "Chi-square on numeric quartile bins",
            "statistic": stat, "p_value": p, "q_value_BH": float(q),
            "selected": keep,
        })

    # Categorical features: chi-square against target quartiles.
    categorical_results = []
    for col in categorical_candidates:
        stat, p = _chi_square_safe(train_df[col], target_bins)
        categorical_results.append((col, stat, p))
    categorical_q = benjamini_hochberg([x[2] for x in categorical_results])
    for (col, stat, p), q in zip(categorical_results, categorical_q):
        keep = bool(q < alpha)
        if keep:
            selected_categorical.append(col)
        report_rows.append({
            "feature": col, "test": "Chi-square categorical vs target quartiles",
            "statistic": stat, "p_value": p, "q_value_BH": float(q),
            "selected": keep,
        })

    # Prevent an empty or unusably small feature set.
    if not selected_numeric:
        correlations = []
        for col in numeric_candidates:
            r, _ = _pearson_safe(train_df[col], y.to_numpy())
            correlations.append((col, abs(r)))
        selected_numeric = [c for c, _ in sorted(correlations, key=lambda z: z[1], reverse=True)[:8]]

    # Pairwise redundancy pruning, fitted on the training partition only.
    selected_numeric = list(dict.fromkeys(selected_numeric))
    if len(selected_numeric) > 1:
        numeric_train = train_df[selected_numeric].apply(pd.to_numeric, errors="coerce")
        corr = numeric_train.corr().abs()
        target_strength = {
            c: abs(_pearson_safe(train_df[c], y.to_numpy())[0]) for c in selected_numeric
        }
        kept = []
        for col in sorted(selected_numeric, key=lambda c: target_strength[c], reverse=True):
            conflict = next(
                (k for k in kept if pd.notna(corr.loc[col, k]) and corr.loc[col, k] >= redundancy_threshold),
                None,
            )
            if conflict is None:
                kept.append(col)
            else:
                report_rows.append({
                    "feature": col, "test": "Redundancy pruning",
                    "statistic": float(corr.loc[col, conflict]),
                    "p_value": np.nan, "q_value_BH": np.nan,
                    "selected": False, "reason": f"Highly correlated with {conflict}",
                })
        selected_numeric = sorted(kept)

    # Retain tier if available so global models can learn tier-level effects.
    if "City_Size_Tier" in categorical_candidates and "City_Size_Tier" not in selected_categorical:
        selected_categorical.append("City_Size_Tier")
        report_rows.append({
            "feature": "City_Size_Tier", "test": "Operational inclusion",
            "statistic": np.nan, "p_value": np.nan, "q_value_BH": np.nan,
            "selected": True, "reason": "Kept to expose the population segment to global models",
        })

    return selected_numeric, sorted(set(selected_categorical)), pd.DataFrame(report_rows)


# -----------------------------------------------------------------------------
# Step 4 — fold-local preprocessing
# -----------------------------------------------------------------------------
def make_preprocessor(numeric_features: List[str], categorical_features: List[str]):
    transformers = []
    if numeric_features:
        numeric_pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
        ])
        transformers.append(("numeric", numeric_pipe, numeric_features))
    if categorical_features:
        categorical_pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent", keep_empty_features=True)),
            ("onehot", make_one_hot_encoder()),
        ])
        transformers.append(("categorical", categorical_pipe, categorical_features))
    if not transformers:
        raise ValueError("Feature selection returned no usable features.")
    return ColumnTransformer(transformers, remainder="drop")


# -----------------------------------------------------------------------------
# Step 5 — PyTorch ANN models
# -----------------------------------------------------------------------------
class TorchWasteANN:
    """Swish/Linear MLP with Huber loss or multi-quantile pinball loss."""
    def __init__(
        self,
        activation: str = "swish",
        quantiles: Optional[Tuple[float, ...]] = None,
        epochs: int = ANN_EPOCHS,
        patience: int = ANN_PATIENCE,
        learning_rate: float = 1e-3,
        batch_size: int = ANN_BATCH_SIZE,
        seed: int = RANDOM_SEED,
    ):
        self.activation = activation
        self.quantiles = quantiles
        self.epochs = epochs
        self.patience = patience
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.seed = seed
        self.model = None
        self.target_scaler = None

    def _build(self, input_dim: int):
        activation_layer = nn.SiLU() if self.activation == "swish" else nn.Identity()
        output_dim = len(self.quantiles) if self.quantiles else 1
        return nn.Sequential(
            nn.Linear(input_dim, 64), activation_layer,
            nn.Linear(64, 32), activation_layer,
            nn.Linear(32, output_dim),
        )

    def fit(self, X, y, sample_weight=None):
        set_seed(self.seed)
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=np.float32).reshape(-1, 1)
        if len(X) < 20:
            raise ValueError("At least 20 rows are required to train an ANN.")

        self.target_scaler = StandardScaler().fit(y)
        y_scaled = self.target_scaler.transform(y).astype(np.float32)
        weights = np.ones(len(y_scaled), dtype=np.float32) if sample_weight is None else np.asarray(sample_weight, dtype=np.float32)
        weights = np.clip(weights, 0.05, 20.0)

        # Keep the latest 15% of training observations for chronological early stopping.
        n_val = max(1, int(len(X) * 0.15))
        n_fit = len(X) - n_val
        n_fit = max(1, n_fit)
        X_fit, X_val = X[:n_fit], X[n_fit:]
        y_fit, y_val = y_scaled[:n_fit], y_scaled[n_fit:]
        w_fit, w_val = weights[:n_fit], weights[n_fit:]
        if len(X_val) == 0:
            X_val, y_val, w_val = X_fit[-1:], y_fit[-1:], w_fit[-1:]

        dataset = TensorDataset(
            torch.from_numpy(X_fit),
            torch.from_numpy(y_fit),
            torch.from_numpy(w_fit.reshape(-1, 1)),
        )
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        Xv = torch.from_numpy(X_val)
        yv = torch.from_numpy(y_val)
        wv = torch.from_numpy(w_val.reshape(-1, 1))

        self.model = self._build(X.shape[1])
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
        huber = nn.HuberLoss(reduction="none")
        qs = None
        if self.quantiles:
            qs = torch.tensor(self.quantiles, dtype=torch.float32).reshape(1, -1)

        best_loss = float("inf")
        best_state = None
        wait = 0

        for _epoch in range(self.epochs):
            self.model.train()
            for xb, yb, wb in loader:
                optimizer.zero_grad()
                pred = self.model(xb)
                if self.quantiles:
                    error = yb - pred
                    qloss = torch.maximum(qs * error, (qs - 1.0) * error)
                    per_row = qloss.mean(dim=1, keepdim=True)
                else:
                    per_row = huber(pred, yb)
                loss = (per_row * wb).sum() / torch.clamp(wb.sum(), min=1e-8)
                loss.backward()
                optimizer.step()

            self.model.eval()
            with torch.no_grad():
                val_pred = self.model(Xv)
                if self.quantiles:
                    error = yv - val_pred
                    val_loss_tensor = torch.maximum(qs * error, (qs - 1.0) * error).mean(dim=1, keepdim=True)
                else:
                    val_loss_tensor = huber(val_pred, yv)
                val_loss = float(((val_loss_tensor * wv).sum() / torch.clamp(wv.sum(), min=1e-8)).item())

            if val_loss < best_loss - 1e-6:
                best_loss = val_loss
                best_state = {k: v.detach().clone() for k, v in self.model.state_dict().items()}
                wait = 0
            else:
                wait += 1
                if wait >= self.patience:
                    break

        if best_state is not None:
            self.model.load_state_dict(best_state)
        return self

    def predict(self, X):
        if self.model is None or self.target_scaler is None:
            raise RuntimeError("Model has not been fitted.")
        self.model.eval()
        X = torch.tensor(np.asarray(X, dtype=np.float32))
        with torch.no_grad():
            raw = self.model(X).cpu().numpy()
        if self.quantiles:
            raw = np.sort(raw, axis=1)  # prevent crossed q10/q50/q90 predictions
            flat = raw.reshape(-1, 1)
            inv = self.target_scaler.inverse_transform(flat).reshape(raw.shape)
            return inv
        return self.target_scaler.inverse_transform(raw.reshape(-1, 1)).ravel()

    def save(self, path: Path):
        payload = {
            "state_dict": self.model.state_dict(),
            "activation": self.activation,
            "quantiles": self.quantiles,
            "input_dim": int(self.model[0].in_features),
            "target_mean": float(self.target_scaler.mean_[0]),
            "target_scale": float(self.target_scaler.scale_[0]),
        }
        torch.save(payload, path)


# -----------------------------------------------------------------------------
# Step 6 — targets, inverse transform, bins, and metrics
# -----------------------------------------------------------------------------
def target_log_per_capita(df: pd.DataFrame) -> np.ndarray:
    per_capita = (df[TARGET_COL].to_numpy(dtype=float) * 1000.0) / np.maximum(
        df["Population"].to_numpy(dtype=float), 1.0
    )
    return np.log1p(np.maximum(per_capita, 0.0))


def log_per_capita_to_daily_tons(pred_log_pc, population) -> np.ndarray:
    pc = np.expm1(np.clip(np.asarray(pred_log_pc, dtype=float), -20.0, 20.0))
    tons = pc * np.asarray(population, dtype=float) / 1000.0
    return np.maximum(tons, 0.0)


def bins_from_daily_tons(daily_tons, collection_cycles):
    tons = np.maximum(np.asarray(daily_tons, dtype=float), 0.0)
    cycles = np.asarray(collection_cycles, dtype=float)
    result = np.full(len(tons), np.nan, dtype=float)
    valid = np.isfinite(cycles) & (cycles > 0) & np.isfinite(tons)
    result[valid] = np.ceil(
        tons[valid] * 1000.0 * 7.0 / (BIN_CAPACITY_KG * cycles[valid])
    )
    return result


def calculate_metrics(df: pd.DataFrame, predicted_tons: np.ndarray) -> Dict[str, float]:
    actual_tons = df[TARGET_COL].to_numpy(dtype=float)
    predicted_tons = np.asarray(predicted_tons, dtype=float)
    valid_waste = np.isfinite(actual_tons) & np.isfinite(predicted_tons)
    actual_bins = bins_from_daily_tons(actual_tons, df["Garbage_Collection_Frequency"])
    predicted_bins = bins_from_daily_tons(predicted_tons, df["Garbage_Collection_Frequency"])
    valid_bins = np.isfinite(actual_bins) & np.isfinite(predicted_bins)

    out = {
        "Waste_MAE_tons_day": float(mean_absolute_error(actual_tons[valid_waste], predicted_tons[valid_waste])),
        "Waste_RMSE_tons_day": float(np.sqrt(mean_squared_error(actual_tons[valid_waste], predicted_tons[valid_waste]))),
        "Waste_R2": float(r2_score(actual_tons[valid_waste], predicted_tons[valid_waste])) if valid_waste.sum() > 1 else np.nan,
        "Waste_WAPE_pct": float(np.sum(np.abs(actual_tons[valid_waste] - predicted_tons[valid_waste])) / max(np.sum(np.abs(actual_tons[valid_waste])), 1e-9) * 100.0),
        "Bin_MAE_proxy": float(mean_absolute_error(actual_bins[valid_bins], predicted_bins[valid_bins])) if valid_bins.any() else np.nan,
        "Bin_RMSE_proxy": float(np.sqrt(mean_squared_error(actual_bins[valid_bins], predicted_bins[valid_bins]))) if valid_bins.any() else np.nan,
        "Bin_WAPE_proxy_pct": float(np.sum(np.abs(actual_bins[valid_bins] - predicted_bins[valid_bins])) / max(np.sum(actual_bins[valid_bins]), 1.0) * 100.0) if valid_bins.any() else np.nan,
    }

    near = valid_bins & (actual_bins >= 90) & (actual_bins <= 110)
    if near.any():
        errors = predicted_bins[near] - actual_bins[near]
        out.update({
            "Bin90_110_n": int(near.sum()),
            "Bin90_110_MAE": float(np.mean(np.abs(errors))),
            "Bin90_110_RMSE": float(np.sqrt(np.mean(errors ** 2))),
            "Bin90_110_WAPE_pct": float(np.sum(np.abs(errors)) / max(np.sum(actual_bins[near]), 1.0) * 100.0),
            "Bin90_110_within10_pct": float(np.mean(np.abs(errors) <= 10.0) * 100.0),
            "Bin90_110_underprediction_pct": float(np.mean(errors < 0) * 100.0),
            "Bin90_110_actual_mean": float(np.mean(actual_bins[near])),
            "Bin90_110_prediction_mean": float(np.mean(predicted_bins[near])),
            "Bin90_110_prediction_median": float(np.median(predicted_bins[near])),
        })
    else:
        out.update({
            "Bin90_110_n": 0,
            "Bin90_110_MAE": np.nan,
            "Bin90_110_RMSE": np.nan,
            "Bin90_110_WAPE_pct": np.nan,
            "Bin90_110_within10_pct": np.nan,
            "Bin90_110_underprediction_pct": np.nan,
            "Bin90_110_actual_mean": np.nan,
            "Bin90_110_prediction_mean": np.nan,
            "Bin90_110_prediction_median": np.nan,
        })
    return out


def tier_metrics(df: pd.DataFrame, predicted_tons: np.ndarray) -> Dict[str, float]:
    actual_bins = bins_from_daily_tons(df[TARGET_COL], df["Garbage_Collection_Frequency"])
    pred_bins = bins_from_daily_tons(predicted_tons, df["Garbage_Collection_Frequency"])
    out = {}
    for tier in ["Small", "Medium", "Large"]:
        mask = (df["City_Size_Tier"].astype(str).to_numpy() == tier) & np.isfinite(actual_bins) & np.isfinite(pred_bins)
        out[f"{tier}_n"] = int(mask.sum())
        out[f"{tier}_Bin_MAE"] = float(np.mean(np.abs(pred_bins[mask] - actual_bins[mask]))) if mask.any() else np.nan
        out[f"{tier}_Bin_RMSE"] = float(np.sqrt(np.mean((pred_bins[mask] - actual_bins[mask]) ** 2))) if mask.any() else np.nan
    return out


# -----------------------------------------------------------------------------
# Step 7 — sklearn model helpers
# -----------------------------------------------------------------------------
def make_svm_model():
    return Pipeline([
        ("rbf_features", Nystroem(kernel="rbf", gamma=None, n_components=NYSTROEM_COMPONENTS, random_state=RANDOM_SEED)),
        ("svr", LinearSVR(C=1.0, epsilon=0.05, random_state=RANDOM_SEED, max_iter=20000)),
    ])


def fit_svm_with_target_scaling(X_train, y_train):
    y_scaler = StandardScaler().fit(np.asarray(y_train).reshape(-1, 1))
    y_scaled = y_scaler.transform(np.asarray(y_train).reshape(-1, 1)).ravel()
    model = make_svm_model()
    model.fit(X_train, y_scaled)
    return model, y_scaler


def predict_svm(model, y_scaler, X):
    pred_scaled = model.predict(X).reshape(-1, 1)
    return y_scaler.inverse_transform(pred_scaled).ravel()


def majority_classifier_metrics(y_true, y_pred):
    return {
        "Accuracy": float(accuracy_score(y_true, y_pred)),
        "Precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "Recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "F1": float(f1_score(y_true, y_pred, zero_division=0)),
        "Majority_Baseline_Accuracy": float(max(np.mean(y_true), 1.0 - np.mean(y_true))),
        "Positive_Prevalence": float(np.mean(y_true)),
        "Confusion_Matrix": confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
    }


# -----------------------------------------------------------------------------
# Step 8 — one fold: all models, all preprocessing fitted on fold train only
# -----------------------------------------------------------------------------
def train_and_predict_fold(train_df: pd.DataFrame, valid_df: pd.DataFrame, fold_id: int):
    boundaries = fit_city_size_boundaries(train_df)
    tr = apply_city_size_tiers(train_df, boundaries)
    va = apply_city_size_tiers(valid_df, boundaries)

    y_train = target_log_per_capita(tr)
    y_valid = target_log_per_capita(va)

    numeric_candidates = [
        c for c in RAW_NUMERIC_FEATURES + [
            "Year", "Month_Sin", "Month_Cos", "Observed_Waste_Type_Count",
            "Waste_Type_Coverage_Share", "Processing_Capacity_per_1000_People",
            "Smart_Bins_per_10000_People", "Vehicles_per_10000_People",
            "Workers_per_10000_People", "Budget_per_Person", "Landfill_Remaining_Ratio",
            "Population_Density_x_Urbanization", "Collection_Efficiency_x_Segregation",
            "Recycling_Composting_Rate", "Industrial_Activity_x_Urbanization",
        ] + [x for x in tr.columns if x.startswith("Has_WasteType_")]
        if c in tr.columns
    ]
    categorical_candidates = [c for c in RAW_CATEGORICAL_FEATURES + ["City_Size_Tier"] if c in tr.columns]

    selected_num, selected_cat, feature_report = select_features_train_only(
        tr, y_train, numeric_candidates, categorical_candidates
    )
    selected = selected_num + selected_cat
    preprocessor = make_preprocessor(selected_num, selected_cat)
    X_train = np.asarray(preprocessor.fit_transform(tr[selected]), dtype=np.float32)
    X_valid = np.asarray(preprocessor.transform(va[selected]), dtype=np.float32)

    fold_rows = []
    pred_frames = []
    model_predictions = {}

    def record(name: str, pred_target: np.ndarray, extras: Optional[dict] = None):
        pred_tons = log_per_capita_to_daily_tons(pred_target, va["Population"])
        metrics = calculate_metrics(va, pred_tons)
        metrics.update(tier_metrics(va, pred_tons))
        row = {"fold": fold_id, "model": name, "train_rows": len(tr), "validation_rows": len(va), "features_used": len(selected), **metrics}
        if extras:
            row.update(extras)
        fold_rows.append(row)
        model_predictions[name] = pred_tons
        return pred_tons

    # 1. Linear Regression baseline.
    linear = LinearRegression()
    linear.fit(X_train, y_train)
    record("Global Linear Regression", linear.predict(X_valid))

    # 2. SVM approximation baseline.
    svm, svm_y_scaler = fit_svm_with_target_scaling(X_train, y_train)
    record("Global SVM RBF approximation", predict_svm(svm, svm_y_scaler, X_valid))

    # 3. Global ANN Swish.
    ann_swish = TorchWasteANN("swish", seed=RANDOM_SEED + fold_id)
    ann_swish.fit(X_train, y_train)
    record("Global ANN Swish Huber Adam", ann_swish.predict(X_valid))

    # 4. Global ANN Linear.
    ann_linear = TorchWasteANN("linear", seed=RANDOM_SEED + 100 + fold_id)
    ann_linear.fit(X_train, y_train)
    record("Global ANN Linear Huber Adam", ann_linear.predict(X_valid))

    # 5. Population-tier-balanced ANN Swish.
    weights = population_tier_weights(tr["City_Size_Tier"])
    ann_weighted = TorchWasteANN("swish", seed=RANDOM_SEED + 200 + fold_id)
    ann_weighted.fit(X_train, y_train, sample_weight=weights)
    record("Population-weighted ANN Swish", ann_weighted.predict(X_valid))

    # 6. Separate ANN per city-size segment.
    segmented_prediction = np.full(len(va), np.nan, dtype=float)
    global_fallback = ann_swish.predict(X_valid)
    for tier in ["Small", "Medium", "Large"]:
        train_mask = tr["City_Size_Tier"].astype(str).to_numpy() == tier
        valid_mask = va["City_Size_Tier"].astype(str).to_numpy() == tier
        if not valid_mask.any():
            continue
        if train_mask.sum() < MIN_SEGMENT_TRAIN_ROWS:
            segmented_prediction[valid_mask] = global_fallback[valid_mask]
            continue
        segment_model = TorchWasteANN("swish", seed=RANDOM_SEED + fold_id + {"Small": 10, "Medium": 20, "Large": 30}[tier])
        segment_model.fit(X_train[train_mask], y_train[train_mask])
        segmented_prediction[valid_mask] = segment_model.predict(X_valid[valid_mask])
    segmented_prediction = np.where(np.isfinite(segmented_prediction), segmented_prediction, global_fallback)
    record("Segmented ANN Swish", segmented_prediction)

    # 7. Quantile ANN Swish; q50 is its point estimate, q10/q90 form an interval.
    quantile_model = TorchWasteANN("swish", quantiles=(0.10, 0.50, 0.90), seed=RANDOM_SEED + 300 + fold_id)
    quantile_model.fit(X_train, y_train)
    quantile_predictions = quantile_model.predict(X_valid)
    q10_tons = log_per_capita_to_daily_tons(quantile_predictions[:, 0], va["Population"])
    q50_tons = log_per_capita_to_daily_tons(quantile_predictions[:, 1], va["Population"])
    q90_tons = log_per_capita_to_daily_tons(quantile_predictions[:, 2], va["Population"])
    q_metrics = calculate_metrics(va, q50_tons)
    actual_bins = bins_from_daily_tons(va[TARGET_COL], va["Garbage_Collection_Frequency"])
    q10_bins = bins_from_daily_tons(q10_tons, va["Garbage_Collection_Frequency"])
    q90_bins = bins_from_daily_tons(q90_tons, va["Garbage_Collection_Frequency"])
    q_valid = np.isfinite(actual_bins) & np.isfinite(q10_bins) & np.isfinite(q90_bins)
    q_metrics.update(tier_metrics(va, q50_tons))
    q_metrics.update({
        "Quantile_80pct_Coverage_Bin_pct": float(np.mean((actual_bins[q_valid] >= q10_bins[q_valid]) & (actual_bins[q_valid] <= q90_bins[q_valid])) * 100.0) if q_valid.any() else np.nan,
        "Quantile_Mean_Interval_Width_Bins": float(np.mean(q90_bins[q_valid] - q10_bins[q_valid])) if q_valid.any() else np.nan,
    })
    fold_rows.append({"fold": fold_id, "model": "Quantile ANN Swish q50", "train_rows": len(tr), "validation_rows": len(va), "features_used": len(selected), **q_metrics})
    model_predictions["Quantile ANN Swish q50"] = q50_tons

    # Naive Bayes overload classifier. It is NOT a continuous/bin predictor.
    if CAPACITY_COL in tr.columns:
        y_cls_train = (tr[TARGET_COL].to_numpy(float) > tr[CAPACITY_COL].to_numpy(float)).astype(int)
        y_cls_valid = (va[TARGET_COL].to_numpy(float) > va[CAPACITY_COL].to_numpy(float)).astype(int)
        if np.unique(y_cls_train).size >= 2:
            nb = GaussianNB()
            nb.fit(X_train, y_cls_train)
            nb_pred = nb.predict(X_valid)
            fold_rows.append({"fold": fold_id, "model": "Gaussian Naive Bayes (overload classifier)", **majority_classifier_metrics(y_cls_valid, nb_pred)})

    # Keep predictions at row-level for OOF diagnostics.
    ids = va[GROUP_COLS + ["Date", "Population", TARGET_COL, "Garbage_Collection_Frequency", "City_Size_Tier"]].copy()
    ids["fold"] = fold_id
    ids["actual_bins_proxy"] = actual_bins
    for name, pred_tons in model_predictions.items():
        ids[f"pred_bins__{name}"] = bins_from_daily_tons(pred_tons, va["Garbage_Collection_Frequency"])
    pred_frames.append(ids)

    return fold_rows, feature_report.assign(fold=fold_id), pd.concat(pred_frames, ignore_index=True)


# -----------------------------------------------------------------------------
# Step 9 — final holdout fit and model persistence
# -----------------------------------------------------------------------------
def final_holdout_training(train_df: pd.DataFrame, test_df: pd.DataFrame, out_dir: Path):
    boundaries = fit_city_size_boundaries(train_df)
    tr = apply_city_size_tiers(train_df, boundaries)
    te = apply_city_size_tiers(test_df, boundaries)
    y_train = target_log_per_capita(tr)

    numeric_candidates = [
        c for c in RAW_NUMERIC_FEATURES + [
            "Year", "Month_Sin", "Month_Cos", "Observed_Waste_Type_Count",
            "Waste_Type_Coverage_Share", "Processing_Capacity_per_1000_People",
            "Smart_Bins_per_10000_People", "Vehicles_per_10000_People",
            "Workers_per_10000_People", "Budget_per_Person", "Landfill_Remaining_Ratio",
            "Population_Density_x_Urbanization", "Collection_Efficiency_x_Segregation",
            "Recycling_Composting_Rate", "Industrial_Activity_x_Urbanization",
        ] + [x for x in tr.columns if x.startswith("Has_WasteType_")]
        if c in tr.columns
    ]
    categorical_candidates = [c for c in RAW_CATEGORICAL_FEATURES + ["City_Size_Tier"] if c in tr.columns]
    selected_num, selected_cat, final_feature_report = select_features_train_only(
        tr, y_train, numeric_candidates, categorical_candidates
    )
    selected = selected_num + selected_cat

    preprocessor = make_preprocessor(selected_num, selected_cat)
    X_train = np.asarray(preprocessor.fit_transform(tr[selected]), dtype=np.float32)
    X_test = np.asarray(preprocessor.transform(te[selected]), dtype=np.float32)
    joblib.dump(preprocessor, out_dir / "final_preprocessor.joblib")
    (out_dir / "final_selected_features.json").write_text(
        json.dumps({"numeric": selected_num, "categorical": selected_cat}, indent=2)
    )
    (out_dir / "city_size_boundaries.json").write_text(json.dumps(boundaries, indent=2))
    final_feature_report.to_csv(out_dir / "final_feature_selection_report.csv", index=False)

    holdout_rows = []
    pred_table = te[GROUP_COLS + ["Date", "Population", TARGET_COL, "Garbage_Collection_Frequency", "City_Size_Tier"]].copy()
    pred_table["actual_per_capita_kg_day"] = te["Waste_Per_Capita_Target_KG"].to_numpy(float)
    actual_bins = bins_from_daily_tons(te[TARGET_COL], te["Garbage_Collection_Frequency"])
    pred_table["actual_bins_proxy"] = actual_bins

    def save_and_record(name, pred_target, model, filename=None, q_info=None):
        pred_tons = log_per_capita_to_daily_tons(pred_target, te["Population"])
        metrics = calculate_metrics(te, pred_tons)
        metrics.update(tier_metrics(te, pred_tons))
        holdout_rows.append({"model": name, **metrics})
        pred_table[f"pred_daily_tons__{name}"] = pred_tons
        pred_table[f"pred_bins__{name}"] = bins_from_daily_tons(pred_tons, te["Garbage_Collection_Frequency"])
        pred_table[f"bin_error__{name}"] = pred_table[f"pred_bins__{name}"] - actual_bins
        if filename and isinstance(model, TorchWasteANN):
            model.save(out_dir / filename)
        elif filename and model is not None:
            joblib.dump(model, out_dir / filename)
        if q_info:
            q10_tons, q90_tons = q_info
            q10_bins = bins_from_daily_tons(q10_tons, te["Garbage_Collection_Frequency"])
            q90_bins = bins_from_daily_tons(q90_tons, te["Garbage_Collection_Frequency"])
            pred_table["q10_bins__Quantile_ANN"] = q10_bins
            pred_table["q90_bins__Quantile_ANN"] = q90_bins
            valid_interval = np.isfinite(actual_bins) & np.isfinite(q10_bins) & np.isfinite(q90_bins)
            if valid_interval.any():
                holdout_rows[-1]["Quantile_80pct_Coverage_Bin_pct"] = float(
                    np.mean((actual_bins[valid_interval] >= q10_bins[valid_interval]) &
                            (actual_bins[valid_interval] <= q90_bins[valid_interval])) * 100.0
                )
                holdout_rows[-1]["Quantile_Mean_Interval_Width_Bins"] = float(
                    np.mean(q90_bins[valid_interval] - q10_bins[valid_interval])
                )
        return pred_tons

    # Global Linear Regression
    linear = LinearRegression().fit(X_train, y_train)
    save_and_record("Global Linear Regression", linear.predict(X_test), linear, "linear_regression.joblib")

    # Global SVM with target scaling
    svm, svm_y_scaler = fit_svm_with_target_scaling(X_train, y_train)
    svm_bundle = {"model": svm, "target_scaler": svm_y_scaler}
    save_and_record("Global SVM RBF approximation", predict_svm(svm, svm_y_scaler, X_test), svm_bundle, "svm_rbf.joblib")

    # Global ANN Swish
    ann_swish = TorchWasteANN("swish", seed=RANDOM_SEED + 900)
    ann_swish.fit(X_train, y_train)
    save_and_record("Global ANN Swish Huber Adam", ann_swish.predict(X_test), ann_swish, "global_ann_swish.pt")

    # Global ANN Linear
    ann_linear = TorchWasteANN("linear", seed=RANDOM_SEED + 901)
    ann_linear.fit(X_train, y_train)
    save_and_record("Global ANN Linear Huber Adam", ann_linear.predict(X_test), ann_linear, "global_ann_linear.pt")

    # Population-tier-balanced ANN Swish
    weights = population_tier_weights(tr["City_Size_Tier"])
    ann_weighted = TorchWasteANN("swish", seed=RANDOM_SEED + 902)
    ann_weighted.fit(X_train, y_train, sample_weight=weights)
    save_and_record("Population-weighted ANN Swish", ann_weighted.predict(X_test), ann_weighted, "weighted_ann_swish.pt")

    # Segmented ANN Swish: one independent model for each city-size tier.
    global_fallback = ann_swish.predict(X_test)
    segmented_target = np.full(len(te), np.nan, dtype=float)
    for tier in ["Small", "Medium", "Large"]:
        train_mask = tr["City_Size_Tier"].astype(str).to_numpy() == tier
        test_mask = te["City_Size_Tier"].astype(str).to_numpy() == tier
        if not test_mask.any():
            continue
        if train_mask.sum() < MIN_SEGMENT_TRAIN_ROWS:
            segmented_target[test_mask] = global_fallback[test_mask]
            continue
        model = TorchWasteANN("swish", seed=RANDOM_SEED + 910 + {"Small": 1, "Medium": 2, "Large": 3}[tier])
        model.fit(X_train[train_mask], y_train[train_mask])
        segmented_target[test_mask] = model.predict(X_test[test_mask])
        model.save(out_dir / f"segmented_ann_swish_{tier.lower()}.pt")
    segmented_target = np.where(np.isfinite(segmented_target), segmented_target, global_fallback)
    save_and_record("Segmented ANN Swish", segmented_target, None)

    # Quantile ANN: q50 point output, q10-q90 operational range.
    quantile_ann = TorchWasteANN("swish", quantiles=(0.10, 0.50, 0.90), seed=RANDOM_SEED + 920)
    quantile_ann.fit(X_train, y_train)
    q_pred = quantile_ann.predict(X_test)
    q10_tons = log_per_capita_to_daily_tons(q_pred[:, 0], te["Population"])
    q50_tons = log_per_capita_to_daily_tons(q_pred[:, 1], te["Population"])
    q90_tons = log_per_capita_to_daily_tons(q_pred[:, 2], te["Population"])
    save_and_record("Quantile ANN Swish q50", q_pred[:, 1], quantile_ann, "quantile_ann_swish.pt", (q10_tons, q90_tons))

    # Separate Naive Bayes overload classifier.
    if CAPACITY_COL in tr.columns and tr[CAPACITY_COL].notna().any():
        y_cls_train = (tr[TARGET_COL].to_numpy(float) > tr[CAPACITY_COL].to_numpy(float)).astype(int)
        y_cls_test = (te[TARGET_COL].to_numpy(float) > te[CAPACITY_COL].to_numpy(float)).astype(int)
        if np.unique(y_cls_train).size >= 2:
            nb = GaussianNB().fit(X_train, y_cls_train)
            nb_pred = nb.predict(X_test)
            nb_metrics = majority_classifier_metrics(y_cls_test, nb_pred)
            (out_dir / "naive_bayes_overload_metrics.json").write_text(json.dumps(nb_metrics, indent=2))
            joblib.dump(nb, out_dir / "gaussian_nb_overload.joblib")

    # Store outputs. Holdout is not used to choose the winner.
    holdout_df = pd.DataFrame(holdout_rows)
    holdout_df.to_csv(out_dir / "holdout_model_comparison.csv", index=False)
    pred_table.to_csv(out_dir / "holdout_predictions.csv", index=False)

    near = pred_table[pred_table["actual_bins_proxy"].between(90, 110)].copy()
    near.to_csv(out_dir / "holdout_90_110_bin_cases.csv", index=False)
    exact = pred_table[pred_table["actual_bins_proxy"].eq(100)].copy()
    exact.to_csv(out_dir / "holdout_exact_100_bin_cases.csv", index=False)

    return holdout_df, pred_table, boundaries, selected_num, selected_cat


# -----------------------------------------------------------------------------
# Step 10 — main experiment runner
# -----------------------------------------------------------------------------
def run_experiment(data_path: Path, output_dir: Path, n_splits: int = N_SPLITS):
    set_seed(RANDOM_SEED)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading CSV...", flush=True)
    raw = pd.read_csv(data_path)
    monthly, future_excluded = aggregate_and_engineer(raw)
    monthly.to_csv(output_dir / "city_month_engineered.csv", index=False)

    train, test, cutoff = date_split_by_month(monthly, TEST_FRACTION)
    split_info = {
        "raw_rows": int(len(raw)),
        "city_month_rows": int(len(monthly)),
        "future_dated_raw_rows_excluded": int(future_excluded),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_from": str(train["Date"].min().date()),
        "train_through": str(train["Date"].max().date()),
        "test_from": str(test["Date"].min().date()),
        "test_through": str(test["Date"].max().date()),
        "cutoff_date": str(cutoff.date()),
        "test_90_110_bin_proxy_cases": int(pd.Series(
            bins_from_daily_tons(test[TARGET_COL], test["Garbage_Collection_Frequency"])
        ).between(90, 110).sum()),
        "test_exact_100_bin_proxy_cases": int((bins_from_daily_tons(test[TARGET_COL], test["Garbage_Collection_Frequency"]) == 100).sum()),
        "bin_capacity_kg_assumption": BIN_CAPACITY_KG,
        "collection_frequency_assumption": "Garbage_Collection_Frequency interpreted as collections/emptying cycles per week.",
    }
    (output_dir / "split_info.json").write_text(json.dumps(split_info, indent=2))

    # Check for enough distinct train months.
    unique_train_dates = np.array(sorted(train["Date"].unique()))
    if len(unique_train_dates) <= n_splits:
        raise ValueError(f"Need more than {n_splits} distinct training months for TimeSeriesSplit.")

    print(f"Raw rows: {len(raw):,} | City-month rows: {len(monthly):,}", flush=True)
    print(f"Train: {len(train):,} | Test: {len(test):,} | cutoff: {cutoff.date()}", flush=True)
    print("Starting expanding-window time-series cross-validation...", flush=True)

    splitter = TimeSeriesSplit(n_splits=n_splits)
    cv_rows, feature_reports, cv_prediction_frames = [], [], []
    for fold, (train_date_idx, valid_date_idx) in enumerate(splitter.split(unique_train_dates), start=1):
        train_dates = set(unique_train_dates[train_date_idx])
        valid_dates = set(unique_train_dates[valid_date_idx])
        fold_train = train[train["Date"].isin(train_dates)].copy().sort_values(["Date", "City"]).reset_index(drop=True)
        fold_valid = train[train["Date"].isin(valid_dates)].copy().sort_values(["Date", "City"]).reset_index(drop=True)
        fold_rows, feature_report, pred_frame = train_and_predict_fold(fold_train, fold_valid, fold)
        cv_rows.extend(fold_rows)
        feature_reports.append(feature_report)
        cv_prediction_frames.append(pred_frame)
        print(f"Completed CV fold {fold}/{n_splits} — train={len(fold_train):,}, validation={len(fold_valid):,}", flush=True)

    cv_df = pd.DataFrame(cv_rows)
    cv_df.to_csv(output_dir / "cv_fold_metrics.csv", index=False)
    feature_df = pd.concat(feature_reports, ignore_index=True)
    feature_df.to_csv(output_dir / "feature_selection_by_fold.csv", index=False)
    cv_pred = pd.concat(cv_prediction_frames, ignore_index=True)
    cv_pred.to_csv(output_dir / "cv_out_of_fold_predictions.csv", index=False)

    # Aggregate CV means and standard deviations. Classifier rows are kept apart.
    regression_cv = cv_df[cv_df["Waste_MAE_tons_day"].notna()].copy()
    numeric_metrics = [
        "Waste_MAE_tons_day", "Waste_RMSE_tons_day", "Waste_R2", "Waste_WAPE_pct",
        "Bin_MAE_proxy", "Bin_RMSE_proxy", "Bin_WAPE_proxy_pct",
        "Bin90_110_MAE", "Bin90_110_RMSE", "Bin90_110_WAPE_pct",
        "Bin90_110_within10_pct", "Bin90_110_underprediction_pct",
        "Small_Bin_MAE", "Medium_Bin_MAE", "Large_Bin_MAE",
    ]
    available_metrics = [c for c in numeric_metrics if c in regression_cv.columns]
    cv_summary = regression_cv.groupby("model")[available_metrics].agg(["mean", "std"])
    cv_summary.columns = [f"{a}_{b}" for a, b in cv_summary.columns]
    cv_summary = cv_summary.reset_index()
    cv_summary.to_csv(output_dir / "cv_model_comparison.csv", index=False)

    # Feature stability across folds.
    if not feature_df.empty:
        stability = (
            feature_df.groupby(["feature", "test"], dropna=False)["selected"]
            .agg(selected_folds="sum", folds="count")
            .reset_index()
        )
        stability["selection_frequency"] = stability["selected_folds"] / stability["folds"]
        stability.to_csv(output_dir / "feature_selection_stability.csv", index=False)

    print("\nTraining final models and evaluating untouched holdout...", flush=True)
    holdout_df, holdout_predictions, boundaries, selected_num, selected_cat = final_holdout_training(train, test, output_dir)

    # Winner is chosen from CV only, not from holdout. Prioritize the 90–110 bin
    # range, then overall bin RMSE if a fold has no observations in that range.
    cv_pick = cv_summary.copy()
    focus_col = "Bin90_110_RMSE_mean"
    fallback_col = "Bin_RMSE_proxy_mean"
    if focus_col in cv_pick.columns and cv_pick[focus_col].notna().any():
        cv_pick["selection_metric"] = cv_pick[focus_col]
        selection_basis = "Mean CV RMSE on 90–110 bin-proxy subset"
    else:
        cv_pick["selection_metric"] = cv_pick[fallback_col]
        selection_basis = "Mean CV overall bin RMSE proxy (no usable 90–110 fold metric)"
    cv_pick = cv_pick[np.isfinite(cv_pick["selection_metric"])].sort_values("selection_metric")
    best_model = str(cv_pick.iloc[0]["model"]) if not cv_pick.empty else "Global ANN Swish Huber Adam"

    # Quantile interval diagnostics on holdout.
    quantile_coverage = np.nan
    quantile_width = np.nan
    if "q10_bins__Quantile_ANN" in holdout_predictions.columns:
        q10 = holdout_predictions["q10_bins__Quantile_ANN"].to_numpy(float)
        q90 = holdout_predictions["q90_bins__Quantile_ANN"].to_numpy(float)
        actual = holdout_predictions["actual_bins_proxy"].to_numpy(float)
        valid = np.isfinite(q10) & np.isfinite(q90) & np.isfinite(actual)
        if valid.any():
            quantile_coverage = float(np.mean((actual[valid] >= q10[valid]) & (actual[valid] <= q90[valid])) * 100.0)
            quantile_width = float(np.mean(q90[valid] - q10[valid]))

    report = {
        "result": "Result 4 — region-size-aware per-capita waste prediction",
        "best_model_selected_using_cv_only": best_model,
        "selection_basis": selection_basis,
        "target": "log1p(kg/person/day)",
        "reconstruction": "daily_tons = expm1(predicted_log_per_capita) * population / 1000",
        "city_size_segmentation": "Small/Medium/Large terciles from median population per City+State, fitted on each training partition only.",
        "weighting": "Each population tier is assigned approximately equal total training weight, capped for numerical stability.",
        "quantile_model": "Swish MLP with q10/q50/q90 pinball loss; q50 is the point estimate and q10-q90 is the interval.",
        "bin_proxy_assumptions": {
            "bin_capacity_kg": BIN_CAPACITY_KG,
            "collection_frequency": "Garbage_Collection_Frequency interpreted as collection / emptying cycles per week.",
            "weekly_bins_formula": "ceil(daily_waste_tons * 1000 * 7 / (bin_capacity_kg * collection_cycles_per_week))",
            "ground_truth_warning": "The input CSV has no measured required-bin target, total physical-bin inventory, or confirmed usable bin capacity. All bin metrics are scenario-derived proxies.",
        },
        "data_granularity_warning": "Source data is monthly and may contain only one or two waste categories per city-month. This is not a validated weekly all-waste total.",
        "leakage_controls": [
            "Chronological 80:20 split is based on distinct city-month dates; all cities in a month stay together.",
            "Five-fold expanding-window TimeSeriesSplit is applied only inside the training period.",
            "Population tercile boundaries are fitted from training cities only in each fold.",
            "Pearson, Chi-square, FDR correction and redundancy filtering are fitted only on each fold training data.",
            "Imputation, one-hot encoding and standardization are fitted only on each fold training data.",
            "Population-tier sample weights are calculated only from each fold training data.",
            "Source Waste_Per_Capita_KG, Carbon_Emission_From_Waste, Sustainability_Index and performance labels are excluded from predictors.",
            "Final holdout is evaluated after CV model selection and is not used to choose features or hyperparameters.",
        ],
        "split": split_info,
        "selected_features_final_train": {"numeric": selected_num, "categorical": selected_cat},
        "city_size_boundaries_final_train": boundaries,
        "quantile_holdout_coverage_percent": quantile_coverage,
        "quantile_holdout_mean_interval_width_bins": quantile_width,
        "holdout_metrics_file": "holdout_model_comparison.csv",
        "cv_metrics_file": "cv_model_comparison.csv",
    }
    (output_dir / "result4_report.json").write_text(json.dumps(report, indent=2, default=str))

    # Compact ranked model table for terminal and file output.
    ranking = cv_pick[["model", "selection_metric"]].copy()
    ranking.to_csv(output_dir / "cv_model_ranking.csv", index=False)

    print("\n================ RESULT 4: CV RANKING ================")
    print(ranking.to_string(index=False))
    print("\n================ HOLDOUT COMPARISON ==================")
    print(holdout_df.to_string(index=False))
    print("\n================ 90–110 BIN HOLDOUT SUBSET ============")
    near = holdout_predictions[holdout_predictions["actual_bins_proxy"].between(90, 110)]
    display_cols = ["City", "Region", "Date", "actual_bins_proxy"]
    for col in [
        "pred_bins__Global ANN Swish Huber Adam",
        "pred_bins__Segmented ANN Swish",
        "pred_bins__Population-weighted ANN Swish",
        "pred_bins__Quantile ANN Swish q50",
    ]:
        if col in near.columns:
            display_cols.append(col)
    print(near[display_cols].head(40).to_string(index=False))
    print("\nSelected model based on CV only:", best_model)
    print("\nAll outputs saved to:", output_dir.resolve())


def main():
    parser = argparse.ArgumentParser(description="Result 4 — region-size-aware waste forecasting")
    parser.add_argument("--data", default=DEFAULT_DATA_FILE, help="Path to the source CSV")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Folder for outputs/models")
    parser.add_argument("--folds", type=int, default=N_SPLITS, help="Number of expanding-window CV folds")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(
            f"Could not find {data_path}. Put the CSV beside this script or pass --data with its path."
        )
    run_experiment(data_path, Path(args.output_dir), args.folds)


if __name__ == "__main__":
    main()
