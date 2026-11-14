import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import data
from utils.styles import fmt_change, kpi_card, load_css, page_header, render_navbar, require_login

st.set_page_config(page_title="Waste Forecast - Home", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="collapsed")
load_css()
require_login()
render_navbar("Home")

# The shared stylesheet hides the Plotly toolbar; bring it back here so the map has zoom buttons.
st.markdown('''
<style>
    .modebar-container, .modebar { display: block !important; }
    .modebar-btn { font-size: 18px !important; }
    .st-key-save_bins button {
        background-color: #1E563B !important; color: #FFFFFF !important;
        border-radius: 10px !important; border: none !important;
        padding: 0.55rem 1.4rem !important; font-weight: 600 !important; width: auto !important;
    }
    .st-key-save_bins button:hover { background-color: #16422D !important; }
</style>
''', unsafe_allow_html=True)

run = data.ensure_ready()
months = data.periods()
period = months[0]
summary = data.capacity(period)
previous = data.capacity(months[1]) if len(months) > 1 else None

page_header("Home", "Where waste will rise next, and how many bins to add.")
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
    hover = np.column_stack([geo["predicted_tons_per_day"], geo["bins_to_add"], geo["zone"].fillna("-")])

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
        customdata=np.column_stack([geo["city"], hover]),
        hovertemplate="<b>%{customdata[0]}</b><br>Zone: %{customdata[3]}<br>"
                      "Forecast: %{customdata[1]:,.0f} t/day<br>Bins to add: %{customdata[2]:,.0f}<extra></extra>",
    ))
    fig.update_geos(
        scope="asia", lataxis_range=[6.5, 37.5], lonaxis_range=[67.5, 98.0],
        showland=True, landcolor="#9EB8AB", showcountries=True, countrycolor="#E6EFEA", countrywidth=1.2,
        showocean=True, oceancolor="#D7E5DE", showlakes=False, bgcolor="#D7E5DE",
    )
    # dragmode="pan": click-and-drag moves the map; scrollZoom: mouse wheel / pinch zooms it.
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=430, showlegend=False, paper_bgcolor="#D7E5DE", dragmode="pan",
                      hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#C8D6CF", font=dict(color="#16211D", family="Inter", size=12)))
    st.plotly_chart(
        fig, width="stretch",
        config={
            "scrollZoom": True,
            "displaylogo": False,
            "displayModeBar": True,
            "modeBarButtons": [["zoomInGeo", "zoomOutGeo", "resetGeo"]],
            "doubleClick": "reset",
        },
    )
    st.markdown("<div style='font-size:0.8rem; color:#2B3934; margin-top:-6px; padding-left:6px;'>Drag to pan, scroll to zoom, double-click to reset. Marker size shows predicted waste: top region in orange, the rest in green.</div>", unsafe_allow_html=True)

#  Region table (moved here from the Bin capacity page) 
st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)
st.markdown("<h3 style='margin-bottom:2px; font-weight:800; color:#16211D;'>Bins by region</h3>", unsafe_allow_html=True)
st.caption(
    "Bins needed is the ML script's weekly proxy, "
    "ceil(daily tons × 1000 × 7 / (bin kg × collections per week)). "
    "Deployed counts start as assumptions until edited here."
)

f1, f2, _ = st.columns([1, 1.4, 2.6], gap="medium")
zone = f1.selectbox("Zone", ["All zones"] + sorted(summary["zone"].dropna().unique()))
only_short = f2.toggle("Only regions that need bins", value=False)

view = summary if zone == "All zones" else summary[summary["zone"] == zone]
if only_short:
    view = view[view["bins_to_add"] > 0]

table = pd.DataFrame({
    "Region": view["city"],
    "Zone": view["zone"],
    "Bins needed": view["predicted_bins"].fillna(0).round().astype(int),
    "Likely range": [f"{lo:,.0f} - {hi:,.0f}" if pd.notna(lo) else "-" for lo, hi in zip(view["q10_bins"], view["q90_bins"])],
    "Bins deployed": view["bins_deployed"].fillna(0).astype(int),
    "Status": ["Enough" if add <= 0 else f"Add {int(add):,}" for add in view["bins_to_add"]],
    "Source": view["bins_source"],
}).reset_index(drop=True)

with st.container(border=True):
    edited = st.data_editor(
        table,
        hide_index=True,
        width="stretch",
        height=460,
        disabled=[c for c in table.columns if c != "Bins deployed"],
        column_config={"Bins deployed": st.column_config.NumberColumn("Bins deployed (editable)", min_value=0, step=10, format="%d")},
        key=f"bins_{zone}_{only_short}",
    )

st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
if st.button("Save changes", type="primary", key="save_bins"):
    changed = edited[edited["Bins deployed"].notna() & (edited["Bins deployed"] != table["Bins deployed"])]
    if changed.empty:
        st.toast("No changes to save.")
    else:
        saved = data.save_bins(dict(zip(changed["Region"], changed["Bins deployed"].astype(int))), st.session_state.username)
        st.toast(f"Saved bin counts for {saved} region{'s' if saved != 1 else ''}.")
        st.rerun()
