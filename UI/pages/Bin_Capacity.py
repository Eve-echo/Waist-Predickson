import streamlit as st
import pandas as pd
from utils.styles import load_css, render_navbar, get_bin_svg

st.set_page_config(page_title="Waste Forecast - Bin capacity", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="collapsed")
load_css()
render_navbar("Bin capacity")

if "bin_data" not in st.session_state:
    st.session_state.bin_data = pd.DataFrame({
        "Region": ["Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata"],
        "Deployed": [2973, 2612, 2579, 2331, 1982],
        "Trend": ["+0.5%", "+1.2%", "+1.2%", "+0.5%", "+0.0%"],
        "Needed": [2923, 2750, 2632, 2274, 2022]
    })

st.markdown('''
<style>
    div[data-testid="stNumberInput"] input {
        background-color: #FFFFFF !important;
        border: 1px solid #C6D6CE !important;
        border-radius: 8px !important;
        padding: 4px 10px !important;
        font-weight: 500 !important;
        color: #16211D !important;
    }
    div[data-testid="stNumberInput"] button {
        display: none !important;
    }
    .save-btn-wrap .stButton > button {
        background-color: #1E563B !important;
        color: #FFFFFF !important;
        border-radius: 10px !important;
        border: none !important;
        padding: 0.55rem 1.4rem !important;
        font-weight: 600 !important;
        width: auto !important;
    }
</style>
''', unsafe_allow_html=True)

st.markdown("<h1 style='margin-bottom:2px; font-size:2.2rem; font-weight:800; color:#16211D;'>Bin capacity</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#2B3934; font-size:1rem; margin-bottom:20px;'>Bins deployed now versus bins needed.</p>", unsafe_allow_html=True)

df = st.session_state.bin_data
total_deployed = int(df["Deployed"].sum())
total_needed = int(df["Needed"].sum())
total_to_add = max(0, int((df["Needed"] - df["Deployed"]).clip(lower=0).sum()))

k1, k2, k3 = st.columns(3, gap="medium")
with k1:
    st.markdown(f'<div class="kpi-card"><div class="kpi-header"><span>Total deployed</span><span class="badge-green">+0.5%</span></div><div class="kpi-value">{total_deployed:,}</div></div>', unsafe_allow_html=True)
with k2:
    st.markdown(f'<div class="kpi-card"><div class="kpi-header"><span>Total needed</span><span class="badge-green">+1.2%</span></div><div class="kpi-value">{total_needed:,}</div></div>', unsafe_allow_html=True)
with k3:
    st.markdown(f'<div class="kpi-card-orange"><div class="kpi-header"><span>Bins to add</span><span class="badge-peach">+5%</span></div><div class="kpi-value" style="color:#6E2E04;">{total_to_add:,}</div></div>', unsafe_allow_html=True)

with st.container(border=True):
    hdr = st.columns([1.4, 2.2, 1.3, 1.6])
    hdr[0].markdown("<div style='font-weight:600; color:#16211D; padding:6px 8px;'>Region</div>", unsafe_allow_html=True)
    hdr[1].markdown("<div style='font-weight:600; color:#16211D; padding:6px 8px;'>Bins deployed (editable)</div>", unsafe_allow_html=True)
    hdr[2].markdown("<div style='font-weight:600; color:#16211D; padding:6px 8px;'>Bins needed</div>", unsafe_allow_html=True)
    hdr[3].markdown("<div style='font-weight:600; color:#16211D; padding:6px 8px;'>Status</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:4px 0 10px 0; border:none; border-top:1px solid #E5EFEA;'>", unsafe_allow_html=True)

    updated_deployed = []
    for idx, row in df.iterrows():
        c1, c2, c3, c4 = st.columns([1.4, 2.2, 1.3, 1.6])
        c1.markdown(f"<div style='padding:8px; font-weight:500; color:#16211D;'>{row['Region']}</div>", unsafe_allow_html=True)

        with c2:
            in_col, badge_col = st.columns([1, 1.2])
            val = in_col.number_input(
                label=f"dep_{row['Region']}",
                value=int(row["Deployed"]),
                step=10,
                label_visibility="collapsed",
                key=f"input_{row['Region']}"
            )
            updated_deployed.append(val)

            is_enough = val >= row["Needed"]
            icon_color = "#1E563B" if is_enough else "#A32015"
            pill_bg = "#D2E3DB" if is_enough else "#F4C7C3"
            pill_fg = "#1E563B" if is_enough else "#7A1810"
            badge_col.markdown(
                f"<div style='padding-top:6px; display:flex; align-items:center;'><span style='background:{pill_bg}; color:{pill_fg}; padding:3px 10px; border-radius:999px; font-size:0.78rem; font-weight:600;'>{row['Trend']}</span>{get_bin_svg(icon_color)}</div>",
                unsafe_allow_html=True
            )

        c3.markdown(f"<div style='padding:8px; color:#16211D;'>{row['Needed']:,}</div>", unsafe_allow_html=True)

        diff = row["Needed"] - val
        if diff <= 0:
            status_html = f"<span style='background:#D2E3DB; color:#1E563B; padding:4px 12px; border-radius:999px; font-size:0.8rem; font-weight:600;'>Enough</span>{get_bin_svg('#1E563B')}"
        else:
            status_html = f"<span style='background:#F4C7C3; color:#7A1810; padding:4px 12px; border-radius:999px; font-size:0.8rem; font-weight:600;'>Add {diff}</span>{get_bin_svg('#A32015')}"

        c4.markdown(f"<div style='padding:6px 8px; display:flex; justify-content:space-between; align-items:center;'>{status_html}</div>", unsafe_allow_html=True)

st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
st.markdown("<div class='save-btn-wrap'>", unsafe_allow_html=True)
if st.button("Save changes"):
    st.session_state.bin_data["Deployed"] = updated_deployed
    st.toast("Bin capacity changes saved!")
    st.rerun()
st.markdown("</div>", unsafe_allow_html=True)
