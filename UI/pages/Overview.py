import numpy as np
import plotly.graph_objects as go
import streamlit as st

from utils import data
from utils.styles import fmt_change, kpi_card, load_css, page_header, render_navbar, require_login

st.set_page_config(page_title="Waste Forecast - Overview", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="collapsed")
load_css()
require_login()
render_navbar("Overview")

run = data.ensure_ready()
months = data.periods()
period = months[0]
summary = data.capacity(period)
previous = data.capacity(months[1]) if len(months) > 1 else None

page_header("Dashboard overview", "Where waste will rise next, and how many bins to add.")
st.caption(f"{data.month_label(period)} · model: {run['selected_model']} · bins are weekly proxies at {run['bin_capacity_kg']:.0f} kg per bin")

total_deployed = int(summary["bins_deployed"].sum())
needed_tons = summary["predicted_tons_per_day"].sum()
needed_change = fmt_change(needed_tons, previous["predicted_tons_per_day"].sum()) if previous is not None else None
bins_to_add = int(summary["bins_to_add"].sum())
short_regions = int((summary["bins_to_add"] > 0).sum())
assumed = (summary["bins_source"] != "municipal").all()

top = summary.iloc[0]
left_col, right_col = st.columns([1.3, 1], gap="large")

with left_col:
    c1, c2 = st.columns(2, gap="medium")
    c1.markdown(kpi_card("Bins deployed", f"{total_deployed:,}", "Assumed" if assumed else "Municipal data"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Capacity now (t/day)", f"{summary['processing_capacity'].sum():,.0f}"), unsafe_allow_html=True)
    c3, c4 = st.columns(2, gap="medium")
    c3.markdown(kpi_card("Capacity needed (t/day)", f"{needed_tons:,.0f}", needed_change), unsafe_allow_html=True)
    c4.markdown(kpi_card("Bins to add", f"{bins_to_add:,}", f"{short_regions} regions", accent=True), unsafe_allow_html=True)

    building_svg = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#8C4A1C" stroke-width="1.8" style="vertical-align: middle; margin-right: 8px;"><path d="M3 21h18M5 21V7l5-3v17M10 21V11l4-2v12M14 21V5l5 2v14M7 10h1M7 14h1M11 14h1M16 9h1M16 13h1"/></svg>'
    st.markdown(
        f'<div class="peach-banner"><div style="display:flex; align-items:center; font-size:1rem; font-weight:500; color:#3D2E22; margin-bottom:4px;">{building_svg}<span>Highest predicted region:</span></div>'
        f'<div style="font-size:2.35rem; font-weight:800; color:#16211D; line-height:1.15; margin-bottom:6px;">{top["city"]}</div>'
        f'<div style="font-size:0.95rem; color:#2B3934;">{top["predicted_tons_per_day"]:,.0f} t/day forecast. {int(top["bins_to_add"]):,} more bins needed.</div></div>',
        unsafe_allow_html=True,
    )

with right_col:
    geo = summary.dropna(subset=["latitude", "longitude"]).copy()
    is_top = geo["city"] == top["city"]
    sizes = 7 + 22 * np.sqrt(geo["predicted_tons_per_day"] / geo["predicted_tons_per_day"].max())
    labelled = geo["rank"] <= 8

    fig = go.Figure()
    fig.add_trace(go.Scattergeo(
        lon=geo["longitude"], lat=geo["latitude"], mode="markers", hoverinfo="skip",
        marker=dict(size=sizes + 12, color=np.where(is_top, "rgba(244, 123, 32, 0.35)", "rgba(30, 86, 59, 0.2)"), line=dict(width=0)),
    ))
    fig.add_trace(go.Scattergeo(
        lon=geo["longitude"], lat=geo["latitude"], text=np.where(labelled, geo["city"], ""),
        mode="markers+text", textposition="bottom center",
        textfont=dict(size=11, color="#16211D", family="Inter"),
        marker=dict(size=sizes, color=np.where(is_top, "#F47B20", "#1E563B"), line=dict(width=0)),
    ))
    fig.update_geos(
        scope="asia", lataxis_range=[6.5, 37.5], lonaxis_range=[67.5, 98.0],
        showland=True, landcolor="#9EB8AB", showcountries=True, countrycolor="#E6EFEA", countrywidth=1.2,
        showocean=True, oceancolor="#D7E5DE", showlakes=False, bgcolor="#D7E5DE",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=430, showlegend=False, paper_bgcolor="#D7E5DE", dragmode=False)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "staticPlot": True})
    st.markdown("<div style='font-size:0.8rem; color:#2B3934; margin-top:-6px; padding-left:6px;'>Marker size shows predicted waste: top region in orange, the rest in green.</div>", unsafe_allow_html=True)