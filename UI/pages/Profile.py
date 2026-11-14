import streamlit as st

from utils import data
from utils.styles import load_css, render_navbar, require_login

st.set_page_config(page_title="Waste Forecast - Profile", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="collapsed")
load_css()
require_login()
render_navbar("")

st.markdown('''
<style>
    .st-key-save_profile button {
        background-color: #1E563B !important; color: #FFFFFF !important;
        border-radius: 10px !important; border: none !important;
        padding: 0.55rem 1.4rem !important; font-weight: 600 !important;
    }
    .st-key-save_profile button:hover { background-color: #16422D !important; }
    [data-testid="stHeaderActionElements"] { display: none !important; }
</style>
''', unsafe_allow_html=True)

st.markdown(
    "<div style='text-align:center; margin-bottom:20px;'>"
    "<h1 style='margin-bottom:2px; font-size:2.2rem; font-weight:800; color:#16211D;'>Edit profile</h1>"
    "<p style='color:#2B3934; font-size:1rem; margin:0;'>Change your username or password.</p></div>",
    unsafe_allow_html=True,
)

username = st.session_state.username
_, form_col, _ = st.columns([1, 1.2, 1], gap="large")

with form_col:
    # Shown on the run right after a successful save (the page reruns so the navbar picks up a new username).
    if st.session_state.pop("profile_saved", False):
        st.success("Your profile has been saved.", icon=":material/check_circle:")

    with st.container(border=True):
        st.markdown(f"<div style='text-align:center; padding:4px 4px 0 4px; color:#5B6B64; font-size:0.85rem;'>Role: <b style='text-transform:capitalize; color:#16211D;'>{st.session_state.role}</b></div>", unsafe_allow_html=True)
        # The counter changes after a successful save, which gives the form fresh (empty) fields.
        n = st.session_state.get("profile_form_n", 0)
        with st.form(f"edit_profile_{n}", border=False):
            new_username = st.text_input("Username", value=username, key=f"pf_user_{n}")
            new_password = st.text_input("New password", type="password", placeholder="Leave blank to keep your current password", key=f"pf_new_{n}")
            confirm = st.text_input("Confirm new password", type="password", key=f"pf_confirm_{n}")
            current = st.text_input("Current password", type="password", help="Required to save any change.", key=f"pf_current_{n}")
            submitted = st.form_submit_button("Save changes", key="save_profile", width="stretch")

    if submitted:
        new_username = new_username.strip()
        if not current:
            st.error("Enter your current password to save changes.")
        elif new_password != confirm:
            st.error("The new passwords do not match.")
        elif new_username == username and not new_password:
            st.info("There are no changes to save.")
        else:
            try:
                user = data.update_profile(username, current, new_username, new_password or None)
            except ValueError as err:
                st.error(str(err))
            else:
                st.session_state.username = user["username"]
                st.session_state.profile_saved = True
                st.session_state.profile_form_n = n + 1
                st.rerun()
