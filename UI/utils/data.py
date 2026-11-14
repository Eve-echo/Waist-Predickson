"""Cached, read-only access to the dashboard database for the Streamlit pages."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from Backend import db  # noqa: E402


def _stamp() -> int:
    """Changes whenever the database file is written, which invalidates cached reads."""
    return db.DB_PATH.stat().st_mtime_ns if db.DB_PATH.exists() else 0


def _query(fn, *args, **kwargs):
    conn = db.get_conn()
    try:
        return fn(conn, *args, **kwargs)
    finally:
        conn.close()


@st.cache_data(show_spinner=False)
def _run_info(stamp: int) -> dict | None:
    run = _query(db.latest_run)
    return dict(run) if run else None


@st.cache_data(show_spinner=False)
def _periods(stamp: int, model: str | None) -> list[str]:
    return _query(db.get_periods, model)


@st.cache_data(show_spinner=False)
def _capacity(stamp: int, period: str | None, model: str | None) -> pd.DataFrame:
    return _query(db.get_capacity_summary, period, model)


@st.cache_data(show_spinner=False)
def _history(stamp: int, city: str) -> pd.DataFrame:
    return _query(db.get_history, city)


@st.cache_data(show_spinner=False)
def _predictions(stamp: int, city: str, model: str | None) -> pd.DataFrame:
    return _query(db.get_predictions, city, model)


@st.cache_data(show_spinner=False)
def _metrics(stamp: int) -> pd.DataFrame:
    return _query(db.get_model_metrics)


def run_info() -> dict | None:
    return _run_info(_stamp())


def periods(model: str | None = None) -> list[str]:
    return _periods(_stamp(), model)


def capacity(period: str | None = None, model: str | None = None) -> pd.DataFrame:
    return _capacity(_stamp(), period, model)


def history(city: str) -> pd.DataFrame:
    return _history(_stamp(), city)


def predictions(city: str, model: str | None = None) -> pd.DataFrame:
    return _predictions(_stamp(), city, model)


def model_metrics() -> pd.DataFrame:
    return _metrics(_stamp())


def save_bins(changes: dict[str, int], user: str) -> int:
    return _query(db.update_bins_many, changes, user)


def authenticate(username: str, password: str) -> dict | None:
    if not db.DB_PATH.exists():
        return None
    return _query(db.verify_user, username, password)


def ensure_ready() -> dict:
    """Stop the page with setup instructions if the database has no model results yet."""
    run = run_info() if db.DB_PATH.exists() else None
    if run is None:
        st.error("No forecast data found. Build the database first:")
        st.code(
            "python Script/seed_db.py --reset\n"
            "python Script/load_ml_output.py --ml-dir RESULT_4",
            language="bash",
        )
        st.stop()
    return run


def month_label(period_start: str) -> str:
    return pd.Timestamp(period_start).strftime("%b %Y")