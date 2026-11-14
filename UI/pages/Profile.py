import streamlit as st

from utils import data
from utils.styles import load_css, page_header, render_navbar, require_login

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
</style>
''', unsafe_allow_html=True)

page_header("Edit profile", "Change your username or password.")

username = st.session_state.username
form_col, _ = st.columns([1, 1.6], gap="large")

with form_col:
    with st.container(border=True):
        st.markdown(f"<div style='padding:4px 4px 0 4px; color:#5B6B64; font-size:0.85rem;'>Role: <b style='text-transform:capitalize; color:#16211D;'>{st.session_state.role}</b></div>", unsafe_allow_html=True)
        with st.form("edit_profile", border=False):
            new_username = st.text_input("Username", value=username)
            new_password = st.text_input("New password", type="password", placeholder="Leave blank to keep your current password")
            confirm = st.text_input("Confirm new password", type="password")
            current = st.text_input("Current password", type="password", help="Required to save any change.")
            submitted = st.form_submit_button("Save changes", key="save_profile")

    if submitted:
        new_username = new_username.strip()
        if not current:
            st.error("Enter your current password to save changes.")
        elif new_password != confirm:
            st.error("The new passwords do not match.")
        elif new_username == username and not new_password:
            st.toast("No changes to save.")
        else:
            try:
                user = data.update_profile(username, current, new_username, new_password or None)
            except ValueError as err:
                st.error(str(err))
            else:
                st.session_state.username = user["username"]
                st.toast("Profile updated.")
                st.rerun()
