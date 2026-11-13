import streamlit as st
from utils.styles import load_css, get_logo_svg

st.set_page_config(
    page_title="Waste Forecast - Login",
    page_icon="W",
    layout="wide",
    initial_sidebar_state="collapsed"
)

load_css()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = "officer"
if "login_error" not in st.session_state:
    st.session_state.login_error = False

st.markdown('''
<style>
    .block-container {
        max-width: 460px !important;
        padding-top: 4.5rem !important;
    }
    div.stButton > button[kind="primary"] {
        background-color: #1E563B !important;
        color: #FFFFFF !important;
        border-radius: 10px !important;
        padding: 0.65rem 1rem !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        border: none !important;
        width: 100% !important;
        margin-top: 8px !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #16422D !important;
    }
    div[data-baseweb="input"] {
        border-radius: 8px !important;
        border-color: #C9D3CE !important;
    }
</style>
''', unsafe_allow_html=True)

with st.container(border=True):
    st.markdown(f'<div style="padding: 16px 14px 4px 14px;"><div style="display:flex; align-items:center; justify-content:center; gap:10px; margin-bottom:6px;">{get_logo_svg(38)}<span style="font-size:1.75rem; font-weight:800; color:#16211D; letter-spacing:-0.02em;">Waste Forecast</span></div><p style="text-align:center; color:#2B3934; font-size:1.05rem; margin-bottom:20px;">Municipal staff login</p></div>', unsafe_allow_html=True)

    username = st.text_input("Username", placeholder="officer_name")
    password = st.text_input("Password", type="password", placeholder="Enter your password")

    if st.button("Log in", type="primary", use_container_width=True):
        if username.strip() and password.strip():
            st.session_state.logged_in = True
            st.session_state.username = username.strip()
            st.session_state.login_error = False
            st.switch_page("pages/Overview.py")
        else:
            st.session_state.login_error = True

    if st.session_state.login_error:
        st.markdown('<div style="display:flex; align-items:center; justify-content:center; gap:8px; color:#A32015; font-size:0.9rem; margin-top:14px; margin-bottom:8px; font-weight:500;"><span style="background:#A32015; color:white; width:18px; height:18px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-size:12px; font-weight:800;">!</span><span>Error: Invalid username or password.</span></div>', unsafe_allow_html=True)
    else:
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

st.markdown("<p style='text-align:center; color:#6B7A74; font-size:0.82rem; margin-top:32px;'>© 2024 Waste Forecast Municipal Division</p>", unsafe_allow_html=True)
