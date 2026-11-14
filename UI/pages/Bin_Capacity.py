import plotly.graph_objects as go
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

chart_df = summary.sort_values("predicted_bins", ascending=False)
needed = chart_df["predicted_bins"].fillna(0).round().astype(int)
deployed = chart_df["bins_deployed"].fillna(0).astype(int)
gap = (needed - deployed).clip(lower=0)

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
with st.container(border=True):
    st.markdown("<div style='padding:6px 8px 0 8px; font-size:1.05rem; font-weight:700; color:#16211D;'>Bins needed vs deployed, by region</div>", unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Bins needed", x=chart_df["city"], y=needed, marker_color="#F47B20",
        customdata=gap, hovertemplate="<b>%{x}</b><br>Needed: %{y:,}<br>Short by: %{customdata:,}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Bins deployed", x=chart_df["city"], y=deployed, marker_color="#1E563B",
        hovertemplate="<b>%{x}</b><br>Deployed: %{y:,}<extra></extra>",
    ))
    fig.update_layout(
        barmode="group", bargap=0.25, bargroupgap=0.08, height=420,
        margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#16211D", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#C8D6CF", font=dict(color="#16211D", family="Inter", size=12)),
        xaxis=dict(tickangle=-35, showgrid=False, fixedrange=True),
        yaxis=dict(title="Bins", gridcolor="#E3EBE7", zeroline=False, fixedrange=True),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

st.page_link("pages/Home.py", label="View and edit bins by region on Home", icon=":material/table_view:")
