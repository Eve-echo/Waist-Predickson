import streamlit as st
import plotly.graph_objects as go
from utils.styles import load_css, render_navbar

st.set_page_config(page_title="Waste Forecast - Region trend", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="collapsed")
load_css()
render_navbar("Region trend")

h_col, f1_col, f2_col = st.columns([2.2, 1, 1], gap="medium")
with h_col:
    st.markdown("<h1 style='margin-bottom:2px; font-size:2.2rem; font-weight:800; color:#16211D;'>Region trend</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#2B3934; font-size:1rem;'>History and forecast for one region.</p>", unsafe_allow_html=True)
with f1_col:
    region = st.selectbox("Region", ["Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata"])
with f2_col:
    horizon = st.selectbox("Forecast horizon", ["3 years", "5 years"])

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

region_data = {
    "Mumbai":    {"hist": [8, 6, 14, 17.5, 22.5, 26], "actual": 341, "next": 350, "mape": "3.5%"},
    "Delhi":     {"hist": [7, 6.5, 12, 15.5, 20.0, 24], "actual": 318, "next": 330, "mape": "3.8%"},
    "Bangalore": {"hist": [6, 5.5, 11, 14.0, 18.5, 22], "actual": 302, "next": 316, "mape": "3.2%"},
    "Chennai":   {"hist": [5, 4.8, 9.5, 12.5, 16.0, 19], "actual": 261, "next": 273, "mape": "4.1%"},
    "Kolkata":   {"hist": [5.5, 5.0, 9.0, 11.5, 14.5, 17], "actual": 232, "next": 243, "mape": "3.9%"},
}[region]

hist_years = [2019, 2020, 2021, 2022, 2023, 2024]
hist_vals = region_data["hist"]

fore_years = [2024, 2025, 2026, 2027] if horizon == "3 years" else [2024, 2025, 2026, 2027, 2028, 2029]
fore_vals = [hist_vals[-1] + (i * 2.2) for i in range(len(fore_years))]
upper = [v + (i * 4.8) for i, v in enumerate(fore_vals)]
lower = [max(0, v - (i * 4.8)) for i, v in enumerate(fore_vals)]

chart_col, kpi_col = st.columns([2.35, 1], gap="large")

with chart_col:
    with st.container(border=True):
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=fore_years + fore_years[::-1],
            y=upper + lower[::-1],
            fill="toself",
            fillcolor="rgba(30, 86, 59, 0.22)",
            line=dict(color="rgba(255,255,255,0)"),
            hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=hist_years, y=hist_vals, mode="lines",
            line=dict(color="#1E563B", width=3, shape="spline")
        ))
        fig.add_trace(go.Scatter(
            x=fore_years, y=fore_vals, mode="lines",
            line=dict(color="#1E563B", width=2.5, dash="dash")
        ))
        fig.update_layout(
            margin=dict(l=16, r=20, t=16, b=16),
            height=365,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            xaxis=dict(tickmode="linear", dtick=1, showgrid=False, tickfont=dict(color="#2B3934", size=12)),
            yaxis=dict(range=[0, 52], dtick=10, gridcolor="#E5EFEA", tickfont=dict(color="#2B3934", size=11))
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "staticPlot": True})

with kpi_col:
    st.markdown(f'<div class="kpi-card"><div class="kpi-header"><span>Latest actual (t/day):</span></div><div class="kpi-value">{region_data["actual"]}</div></div><div class="kpi-card"><div class="kpi-header"><span>Forecast next period:</span></div><div class="kpi-value">{region_data["next"]}</div></div><div class="kpi-card"><div class="kpi-header"><span>Backtest error (MAPE):</span></div><div class="kpi-value">{region_data["mape"]}</div></div>', unsafe_allow_html=True)
