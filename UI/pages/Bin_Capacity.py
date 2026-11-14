import pandas as pd
import streamlit as st

from utils import data
from utils.styles import kpi_card, load_css, page_header, render_navbar, require_login

st.set_page_config(page_title="Waste Forecast - Bin capacity", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="collapsed")
load_css()
require_login()
render_navbar("Bin capacity")

st.markdown('''
<style>
    div.stButton > button[kind="primary"] {
        background-color: #1E563B !important; color: #FFFFFF !important;
        border-radius: 10px !important; border: none !important;
        padding: 0.55rem 1.4rem !important; font-weight: 600 !important; width: auto !important;
    }
</style>
''', unsafe_allow_html=True)

data.ensure_ready()
period = data.periods()[0]
summary = data.capacity(period)

page_header("Bin capacity", "Bins deployed now versus bins needed.")
st.caption(
    f"{data.month_label(period)} · bins needed is the ML script's weekly proxy, "
    "ceil(daily tons × 1000 × 7 / (bin kg × collections per week)). "
    "Deployed counts start as assumptions until edited here."
)

k1, k2, k3 = st.columns(3, gap="medium")
k1.markdown(kpi_card("Total deployed", f"{int(summary['bins_deployed'].sum()):,}"), unsafe_allow_html=True)
k2.markdown(kpi_card("Total needed", f"{int(summary['predicted_bins'].sum()):,}"), unsafe_allow_html=True)
k3.markdown(kpi_card("Bins to add", f"{int(summary['bins_to_add'].sum()):,}", f"{int((summary['bins_to_add'] > 0).sum())} regions", accent=True), unsafe_allow_html=True)

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
if st.button("Save changes", type="primary"):
    changed = edited[edited["Bins deployed"].notna() & (edited["Bins deployed"] != table["Bins deployed"])]
    if changed.empty:
        st.toast("No changes to save.")
    else:
        saved = data.save_bins(dict(zip(changed["Region"], changed["Bins deployed"].astype(int))), st.session_state.username)
        st.toast(f"Saved bin counts for {saved} region{'s' if saved != 1 else ''}.")
        st.rerun()