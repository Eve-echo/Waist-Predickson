import streamlit as st

from utils import data
from utils.styles import kpi_card, load_css, page_header, render_navbar, require_login

st.set_page_config(page_title="Waste Forecast - Bin capacity", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="collapsed")
load_css()
require_login()
render_navbar("Bin capacity")

data.ensure_ready()
period = data.periods()[0]
summary = data.capacity(period)

page_header("Bin capacity", "Bins deployed now versus bins needed.")
st.caption(
    f"{data.month_label(period)} · bins needed is the ML script's weekly proxy, "
    "ceil(daily tons × 1000 × 7 / (bin kg × collections per week))."
)

k1, k2, k3 = st.columns(3, gap="medium")
k1.markdown(kpi_card("Total deployed", f"{int(summary['bins_deployed'].sum()):,}"), unsafe_allow_html=True)
k2.markdown(kpi_card("Total needed", f"{int(summary['predicted_bins'].sum()):,}"), unsafe_allow_html=True)
k3.markdown(kpi_card("Bins to add", f"{int(summary['bins_to_add'].sum()):,}", f"{int((summary['bins_to_add'] > 0).sum())} regions", accent=True), unsafe_allow_html=True)

st.page_link("pages/Home.py", label="View and edit bins by region on Home", icon=":material/table_view:")
