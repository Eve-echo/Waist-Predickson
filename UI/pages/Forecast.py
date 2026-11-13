import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.styles import load_css, render_navbar

st.set_page_config(page_title="Waste Forecast - Forecast", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="collapsed")
load_css()
render_navbar("Forecast")

st.markdown("<h1 style='margin-bottom:2px; font-size:2.2rem; font-weight:800; color:#16211D;'>Forecast</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#2B3934; font-size:1rem; margin-bottom:20px;'>Predicted waste for every region, ranked.</p>", unsafe_allow_html=True)

f1, f2, _ = st.columns([0.9, 1.1, 2.5], gap="medium")
with f1:
    target_year = st.selectbox("Target year", ["2026", "2027", "2028"])
with f2:
    region_group = st.selectbox("Region group", ["All regions", "Metro Tier-1", "Coastal Cities"])

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

mult = 1.0 if target_year == "2026" else (1.04 if target_year == "2027" else 1.08)
df = pd.DataFrame({
    "Rank": [1, 2, 3, 4, 5, 6],
    "Region": ["Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata", "Pune"],
    "Forecast": [int(x * mult) for x in [351, 330, 316, 273, 243, 225]],
    "Priority": ["High", "High", "Medium", "Medium", "Medium", "Low"]
})

if region_group == "Metro Tier-1":
    df = df[df["Region"].isin(["Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata"])]
elif region_group == "Coastal Cities":
    df = df[df["Region"].isin(["Mumbai", "Chennai", "Kolkata"])]

col_chart, col_table = st.columns([1.15, 1], gap="large")

with col_chart:
    with st.container(border=True):
        st.markdown("<div style='font-size:1.05rem; font-weight:700; color:#16211D; padding:8px 12px 4px 12px;'>Forecast waste, t/day (ranked)</div>", unsafe_allow_html=True)
        df_rev = df.iloc[::-1]
        colors = ["#235D41"] * (len(df_rev) - 1) + ["#E37829"]

        fig = go.Figure(go.Bar(
            x=df_rev["Forecast"],
            y=[f"{r}   {reg}" for r, reg in zip(df_rev["Rank"], df_rev["Region"])],
            orientation="h",
            width=0.62,
            marker=dict(color=colors, cornerradius=6),
            text=df_rev["Forecast"],
            textposition="outside",
            textfont=dict(size=13, color="#16211D", family="Inter")
        ))
        fig.update_layout(
            margin=dict(l=12, r=42, t=8, b=12),
            height=305,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False, range=[0, max(df["Forecast"]) * 1.18]),
            yaxis=dict(tickfont=dict(size=13.5, color="#16211D", family="Inter"))
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "staticPlot": True})

with col_table:
    with st.container(border=True):
        rows_html = ""
        for _, row in df.iterrows():
            if row["Priority"] == "High":
                badge_bg, badge_fg = "#1E563B", "#FFFFFF"
            elif row["Priority"] == "Medium":
                badge_bg, badge_fg = "#9CC1B0", "#16211D"
            else:
                badge_bg, badge_fg = "#D4E5DD", "#2B3934"

            rows_html += f'<tr style="border-bottom:1px solid #EBF2EE;"><td style="padding:11px 10px; color:#2B3934;">{row["Rank"]}</td><td style="padding:11px 10px; font-weight:500; color:#16211D;">{row["Region"]}</td><td style="padding:11px 10px; color:#16211D;">{row["Forecast"]}</td><td style="padding:11px 10px;"><span style="background:{badge_bg}; color:{badge_fg}; padding:3px 12px; border-radius:999px; font-size:0.78rem; font-weight:600; display:inline-block;">{row["Priority"]}</span></td></tr>'

        table_html = f'<div style="padding:6px 10px;"><table style="width:100%; border-collapse:collapse; text-align:left; font-size:0.95rem;"><thead><tr style="border-bottom:1.5px solid #DCE8E2; color:#2B3934; font-weight:600;"><th style="padding:10px;">Rank</th><th style="padding:10px;">Region</th><th style="padding:10px;">Forecast</th><th style="padding:10px;">Priority</th></tr></thead><tbody>{rows_html}</tbody></table></div>'
        st.markdown(table_html, unsafe_allow_html=True)
