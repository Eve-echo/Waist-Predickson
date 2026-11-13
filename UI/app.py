
import streamlit as st
import re
from utils.styles import load_css, get_logo_svg

st.set_page_config(
    page_title="Waste Forecast - Login",
    page_icon="assets/favicon.png",
    layout="wide",
    initial_sidebar_state="collapsed"
)

load_css()

# Session state initialization
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = "officer"

if "login_error" not in st.session_state:
    st.session_state.login_error = False

if "validation_errors" not in st.session_state:
    st.session_state.validation_errors = {}


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

    .field-error {
        color: #A32015;
        font-size: 0.82rem;
        margin-top: -12px;
        margin-bottom: 10px;
    }
</style>
''', unsafe_allow_html=True)


# Login form
with st.container(border=True):

    st.markdown(
        f'''
        <div style="padding: 16px 14px 4px 14px;">
            <div style="display:flex; align-items:center;
                justify-content:center; gap:10px; margin-bottom:6px;">
                {get_logo_svg(38)}
                <span style="font-size:1.75rem; font-weight:800;
                    color:#16211D; letter-spacing:-0.02em;">
                    Waste Forecast
                </span>
            </div>
            <p style="text-align:center; color:#2B3934;
                font-size:1.05rem; margin-bottom:20px;">
                Municipal staff login
            </p>
        </div>
        ''',
        unsafe_allow_html=True
    )

    username = st.text_input(
        "Username",
        placeholder="officer_name"
    )

    if "username" in st.session_state.validation_errors:
        st.markdown(
            f'<p class="field-error">{st.session_state.validation_errors["username"]}</p>',
            unsafe_allow_html=True
        )

    password = st.text_input(
        "Password",
        type="password",
        placeholder="Enter your password"
    )

    if "password" in st.session_state.validation_errors:
        st.markdown(
            f'<p class="field-error">{st.session_state.validation_errors["password"]}</p>',
            unsafe_allow_html=True
        )

    # Login button
    if st.button("Log in", type="primary", width="stretch"):

        errors = {}

        # Username validation
        if not username.strip():
            errors["username"] = "Username is required."

        elif len(username.strip()) < 3:
            errors["username"] = "Username must contain at least 3 characters."

        # Password validation
        if not password:
            errors["password"] = "Password is required."

        elif len(password) < 8:
            errors["password"] = "Password must contain at least 8 characters."

        elif not re.search(r"[A-Z]", password):
            errors["password"] = "Include at least one uppercase letter."

        elif not re.search(r"[a-z]", password):
            errors["password"] = "Include at least one lowercase letter."

        elif not re.search(r"[0-9]", password):
            errors["password"] = "Include at least one number."

        elif not re.search(r"[^A-Za-z0-9\s]", password):
            errors["password"] = "Include at least one special character."
        # Update validation state
        st.session_state.validation_errors = errors

        if not errors:

            # Clear previous login errors
            st.session_state.login_error = False

            # Login success (demo authentication)
            st.session_state.logged_in = True
            st.session_state.username = username.strip()

            st.switch_page("pages/Overview.py")

        else:
            st.session_state.login_error = False
            st.rerun()


    # Invalid credentials message
    if st.session_state.login_error:
        st.markdown(
            '''
            <div style="display:flex; align-items:center;
                justify-content:center; gap:8px; color:#A32015;
                font-size:0.9rem; margin-top:14px;
                margin-bottom:8px; font-weight:500;">
                <span style="background:#A32015; color:white;
                    width:18px; height:18px; border-radius:50%;
                    display:inline-flex; align-items:center;
                    justify-content:center; font-size:12px;
                    font-weight:800;">!</span>
                <span>Invalid username or password.</span>
            </div>
            ''',
            unsafe_allow_html=True
        )

    else:
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)


# Footer
st.markdown(
    '''
    <p style='text-align:center; color:#6B7A74;
        font-size:0.82rem; margin-top:32px;'>
        © 2026 Waste Forecast Municipal Division
    </p>
    ''',
    unsafe_allow_html=True
)
