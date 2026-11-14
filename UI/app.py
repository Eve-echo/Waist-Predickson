import streamlit as st

from utils.data import authenticate
from utils.styles import get_logo_svg, load_css

st.set_page_config(
    page_title="Waste Forecast - Login",
    page_icon="assets/favicon.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)
load_css()

st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("username", "")
st.session_state.setdefault("role", "")

if st.session_state.logged_in:
    st.switch_page("pages/Overview.py")

st.markdown('''
<style>
    .block-container { max-width: 460px !important; padding-top: 4.5rem !important; }
    div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
        background-color: #1E563B !important; color: #FFFFFF !important;
        border-radius: 10px !important; padding: 0.65rem 1rem !important;
        font-weight: 600 !important; font-size: 1rem !important; border: none !important;
        width: 100% !important; margin-top: 8px !important;
    }
    div[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover { background-color: #16422D !important; }
    div[data-baseweb="input"] { border-radius: 8px !important; border-color: #C9D3CE !important; }
    .login-error {
        display: flex; align-items: center; justify-content: center; gap: 8px;
        color: #A32015; font-size: 0.9rem; margin: 14px 0 8px 0; font-weight: 500;
    }
</style>
''', unsafe_allow_html=True)

with st.container(border=True):
    st.markdown(
        f'''
        <div style="padding: 16px 14px 4px 14px;">
            <div style="display:flex; align-items:center; justify-content:center; gap:10px; margin-bottom:6px;">
                {get_logo_svg(38)}
                <span style="font-size:1.75rem; font-weight:800; color:#16211D; letter-spacing:-0.02em;">Waste Forecast</span>
            </div>
            <p style="text-align:center; color:#2B3934; font-size:1.05rem; margin-bottom:20px;">Municipal staff login</p>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    with st.form("login", border=False):
        username = st.text_input("Username", placeholder="officer_name")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Log in", type="primary", width="stretch")

    if submitted:
        user = authenticate(username.strip(), password) if username.strip() and password else None
        if user:
            st.session_state.logged_in = True
            st.session_state.username = user["username"]
            st.session_state.role = user["role"]
            st.switch_page("pages/Overview.py")
        else:
            st.markdown('<div class="login-error">Invalid username or password.</div>', unsafe_allow_html=True)

st.markdown(
    "<p style='text-align:center; color:#6B7A74; font-size:0.82rem; margin-top:32px;'>"
    "© 2026 Waste Forecast Municipal Division</p>",
    unsafe_allow_html=True,
)