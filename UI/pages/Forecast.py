import plotly.graph_objects as go
import streamlit as st

from utils import data
from utils.styles import load_css, page_header, render_navbar, require_login

st.set_page_config(page_title="Waste Forecast - Forecast", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="collapsed")
load_css()
require_login()
render_navbar("Forecast")

run = data.ensure_ready()
page_header("Forecast", "Predicted waste for every region, ranked.")

metrics = data.model_metrics()
models = metrics["model_name"].tolist()
months = data.periods()

f1, f2, f3, _ = st.columns([0.9, 0.9, 1.4, 1.6], gap="medium")
period = f1.selectbox("Month", months, format_func=data.month_label)
model = f3.selectbox("Model", models, index=models.index(run["selected_model"]))

summary = data.capacity(period, model)
zone = f2.selectbox("Zone", ["All zones"] + sorted(summary["zone"].dropna().unique()))
view = summary if zone == "All zones" else summary[summary["zone"] == zone]

st.caption("Rank and priority compare all regions for the month: High is the top third by predicted waste, Medium the middle third.")

col_chart, col_table = st.columns([1.15, 1], gap="large")

with col_chart:
    with st.container(border=True):
        st.markdown("<div style='font-size:1.05rem; font-weight:700; color:#16211D; padding:8px 12px 4px 12px;'>Forecast waste, t/day (top 10)</div>", unsafe_allow_html=True)
        top = view.head(10).iloc[::-1]
        colors = ["#235D41"] * (len(top) - 1) + ["#E37829"]
        fig = go.Figure(go.Bar(
            x=top["predicted_tons_per_day"].round(0),
            y=[f"{r}   {c}" for r, c in zip(top["rank"], top["city"])],
            orientation="h", width=0.62,
            marker=dict(color=colors, cornerradius=6),
            text=top["predicted_tons_per_day"].round(0).astype(int), textposition="outside",
            textfont=dict(size=13, color="#16211D", family="Inter"),
        ))
        fig.update_layout(
            margin=dict(l=12, r=42, t=8, b=12), height=420,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False, range=[0, top["predicted_tons_per_day"].max() * 1.18]),
            yaxis=dict(tickfont=dict(size=13.5, color="#16211D", family="Inter")),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "staticPlot": True})

BADGES = {"High": ("#1E563B", "#FFFFFF"), "Medium": ("#9CC1B0", "#16211D"), "Low": ("#D4E5DD", "#2B3934")}

with col_table:
    with st.container(border=True):
        rows_html = ""
        for row in view.itertuples():
            bg, fg = BADGES[row.priority]
            actual = "-" if row.actual_tons_per_day != row.actual_tons_per_day else f"{row.actual_tons_per_day:,.0f}"
            rows_html += (
                '<tr style="border-bottom:1px solid #EBF2EE;">'
                f'<td style="padding:11px 10px; color:#2B3934;">{row.rank}</td>'
                f'<td style="padding:11px 10px; font-weight:500; color:#16211D;">{row.city}</td>'
                f'<td style="padding:11px 10px; color:#16211D;">{row.predicted_tons_per_day:,.0f}</td>'
                f'<td style="padding:11px 10px; color:#16211D;">{actual}</td>'
                f'<td style="padding:11px 10px;"><span style="background:{bg}; color:{fg}; padding:3px 12px; border-radius:999px; font-size:0.78rem; font-weight:600; display:inline-block;">{row.priority}</span></td>'
                '</tr>'
            )
        head = "".join(f'<th style="padding:10px; position:sticky; top:0; background:#FFFFFF;">{h}</th>' for h in ["Rank", "Region", "Forecast", "Actual", "Priority"])
        st.markdown(
            '<div style="padding:6px 10px; max-height:455px; overflow-y:auto;">'
            '<table style="width:100%; border-collapse:collapse; text-align:left; font-size:0.95rem;">'
            f'<thead><tr style="border-bottom:1.5px solid #DCE8E2; color:#2B3934; font-weight:600;">{head}</tr></thead>'
            f'<tbody>{rows_html}</tbody></table></div>',
            unsafe_allow_html=True,
        )