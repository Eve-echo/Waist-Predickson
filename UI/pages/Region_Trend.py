import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import data
from utils.styles import kpi_card, load_css, page_header, render_navbar, require_login

st.set_page_config(page_title="Waste Forecast - Region trend", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="collapsed")
load_css()
require_login()
render_navbar("Region trend")

run = data.ensure_ready()
ranked = data.capacity(data.periods()[0])
cities = sorted(ranked["city"])

h_col, f1_col, f2_col = st.columns([2.2, 1, 1], gap="medium")
with h_col:
    page_header("Region trend", "Actual waste history with the model's predictions for one region.")
with f1_col:
    region = st.selectbox("Region", cities, index=cities.index(ranked.iloc[0]["city"]))
with f2_col:
    window = st.selectbox("History window", ["2 years", "5 years", "All"])

hist = data.history(region)
pred = data.predictions(region)
if pred.empty:
    st.info(f"No model predictions are stored for {region}.")
    st.stop()
hist["date"] = pd.to_datetime(hist["period_start"])
pred["date"] = pd.to_datetime(pred["period_start"])

if window != "All":
    hist = hist[hist["date"] >= hist["date"].max() - pd.DateOffset(years=int(window[0]))]
shown_pred = pred[pred["date"] >= hist["date"].min()]

# Error over every held-out month for this region, not just the visible window.
wape = (pred["predicted_tons_per_day"] - pred["actual_tons_per_day"]).abs().sum() / pred["actual_tons_per_day"].sum() * 100
latest = pred.iloc[-1]

chart_col, kpi_col = st.columns([2.35, 1], gap="large")

with chart_col:
    with st.container(border=True):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist["date"], y=hist["waste_tons_per_day"], name="Actual", mode="lines",
                                 line=dict(color="#1E563B", width=3)))
        fig.add_trace(go.Scatter(x=shown_pred["date"], y=shown_pred["predicted_tons_per_day"], name="Model prediction", mode="lines",
                                 line=dict(color="#E37829", width=2.5, dash="dash")))
        fig.update_layout(
            margin=dict(l=16, r=20, t=16, b=16), height=365,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=1.08, x=0),
            xaxis=dict(showgrid=False, tickfont=dict(color="#2B3934", size=12)),
            yaxis=dict(title="tons / day", rangemode="tozero", gridcolor="#E5EFEA", tickfont=dict(color="#2B3934", size=11)),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "staticPlot": True})

with kpi_col:
    bins_range = f"{latest['q10_bins']:,.0f} - {latest['q90_bins']:,.0f}" if pd.notna(latest["q10_bins"]) else "n/a"
    st.markdown(
        kpi_card("Latest actual (t/day):", f"{latest['actual_tons_per_day']:,.1f}")
        + kpi_card(f"Model estimate, {data.month_label(latest['period_start'])}:", f"{latest['predicted_tons_per_day']:,.1f}")
        + kpi_card("Backtest error (WAPE):", f"{wape:.1f}%")
        + kpi_card("Bins needed, likely range:", bins_range),
        unsafe_allow_html=True,
    )

st.caption(
    f"Predictions are the {run['selected_model']} model's output for held-out months "
    f"({data.month_label(run['test_from'])} to {data.month_label(run['test_through'])}); they are not a future forecast. "
    "Region totals sum only the waste types reported that month, so they can undercount."
)