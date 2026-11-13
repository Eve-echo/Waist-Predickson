import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.styles import load_css, render_navbar

st.set_page_config(page_title="Waste Forecast - Overview", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="collapsed")
load_css()
render_navbar("Overview")

st.markdown("<h1 style='margin-bottom:2px; font-size:2.2rem; font-weight:800; color:#16211D;'>Dashboard overview</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#2B3934; font-size:1rem; margin-bottom:24px;'>Where waste will rise next, and how many bins to add.</p>", unsafe_allow_html=True)

left_col, right_col = st.columns([1.3, 1], gap="large")

with left_col:
    r1c1, r1c2 = st.columns(2, gap="medium")
    with r1c1:
        st.markdown('<div class="kpi-card"><div class="kpi-header"><span>Bins deployed</span><div><span class="trend-icon">↗</span><span class="badge-green">+0.5%</span></div></div><div class="kpi-value">12,480</div></div>', unsafe_allow_html=True)
    with r1c2:
        st.markdown('<div class="kpi-card"><div class="kpi-header"><span>Capacity now (t/day)</span><span class="badge-green">+1.2%</span></div><div class="kpi-value">1,540</div></div>', unsafe_allow_html=True)

    r2c1, r2c2 = st.columns(2, gap="medium")
    with r2c1:
        st.markdown('<div class="kpi-card"><div class="kpi-header"><span>Capacity needed (t/day)</span><span class="badge-green">+2.1%</span></div><div class="kpi-value">1,610</div></div>', unsafe_allow_html=True)
    with r2c2:
        st.markdown('<div class="kpi-card-orange"><div class="kpi-header"><span>Bins to add</span><span class="badge-peach">+5%</span></div><div class="kpi-value" style="color:#6E2E04;">610</div></div>', unsafe_allow_html=True)

    building_svg = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#8C4A1C" stroke-width="1.8" style="vertical-align: middle; margin-right: 8px;"><path d="M3 21h18M5 21V7l5-3v17M10 21V11l4-2v12M14 21V5l5 2v14M7 10h1M7 14h1M11 14h1M16 9h1M16 13h1"/></svg>'
    st.markdown(f'<div class="peach-banner"><div style="display:flex; align-items:center; font-size:1rem; font-weight:500; color:#3D2E22; margin-bottom:4px;">{building_svg}<span>Highest predicted region:</span></div><div style="font-size:2.35rem; font-weight:800; color:#16211D; line-height:1.15; margin-bottom:6px;">Mumbai</div><div style="font-size:0.95rem; color:#2B3934;">351 t/day forecast. 65 more bins needed.</div></div>', unsafe_allow_html=True)

with right_col:
    cities = pd.DataFrame({
        "City": ["Mumbai", "Delhi", "Kolkata", "Bangalore", "Chennai"],
        "Lat": [19.0760, 28.7041, 22.5726, 12.9716, 13.0827],
        "Lon": [72.8777, 77.1025, 88.3639, 77.5946, 80.2707],
        "Color": ["#F47B20", "#1E563B", "#1E563B", "#1E563B", "#1E563B"],
        "Glow": ["rgba(244, 123, 32, 0.35)", "rgba(30, 86, 59, 0.25)", "rgba(30, 86, 59, 0.25)", "rgba(30, 86, 59, 0.25)", "rgba(30, 86, 59, 0.25)"],
        "TextPos": ["bottom left", "bottom left", "bottom center", "middle left", "middle right"]
    })

    fig = go.Figure()
    fig.add_trace(go.Scattergeo(
        lon=cities["Lon"], lat=cities["Lat"], mode="markers", hoverinfo="skip",
        marker=dict(size=24, color=cities["Glow"], line=dict(width=0))
    ))
    fig.add_trace(go.Scattergeo(
        lon=cities["Lon"], lat=cities["Lat"], text=cities["City"],
        mode="markers+text", textposition=cities["TextPos"],
        textfont=dict(size=12, color="#16211D", family="Inter"),
        marker=dict(size=11, color=cities["Color"], line=dict(width=0))
    ))
    fig.update_geos(
        scope="asia",
        center=dict(lat=21.2, lon=80.5),
        projection_scale=4.35,
        showland=True, landcolor="#9EB8AB",
        showcountries=True, countrycolor="#E6EFEA", countrywidth=1.2,
        showocean=True, oceancolor="#D7E5DE",
        showlakes=False, bgcolor="#D7E5DE"
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=395,
        showlegend=False,
        paper_bgcolor="#D7E5DE",
        dragmode=False
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})
    st.markdown("<div style='font-size:0.8rem; color:#2B3934; margin-top:-6px; padding-left:6px;'>Map: top predicted region (orange), other key cities (green)</div>", unsafe_allow_html=True)
