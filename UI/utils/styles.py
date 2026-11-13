import streamlit as st

def load_css():
    st.markdown('''
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        #MainMenu, footer, header, [data-testid="stSidebar"], [data-testid="stSidebarNav"], [data-testid="stToolbar"], [data-testid="stDecoration"] {
            display: none !important;
        }

        .stApp {
            background-color: #E6EFEA;
            color: #16211D;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        .block-container {
            padding-top: 0rem !important;
            padding-bottom: 2.5rem !important;
            max-width: 1320px;
        }

        .modebar, .modebar-container, [data-testid="StyledFullScreenButton"] {
            display: none !important;
        }

        div[data-testid="stHorizontalBlock"] .stButton > button {
            border-radius: 999px;
            border: 1px solid #8AA699;
            background-color: transparent;
            color: #16211D;
            font-weight: 500;
            font-size: 0.92rem;
            padding: 0.4rem 1.25rem;
            transition: all 0.18s ease;
            width: 100%;
            box-shadow: none;
        }
        div[data-testid="stHorizontalBlock"] .stButton > button:hover {
            border-color: #1E563B;
            background-color: #C7DBD1;
            color: #16211D;
        }
        div[data-testid="stHorizontalBlock"] .stButton > button[kind="primary"] {
            background-color: #1E563B;
            color: #FFFFFF;
            border: 1px solid #1E563B;
            font-weight: 600;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #FFFFFF !important;
            border-radius: 16px !important;
            border: none !important;
            box-shadow: 0 4px 14px rgba(22, 33, 29, 0.05) !important;
            padding: 8px 10px !important;
        }

        .kpi-card {
            background-color: #FFFFFF;
            border-radius: 16px;
            padding: 20px 24px;
            box-shadow: 0 4px 14px rgba(22, 33, 29, 0.05);
            margin-bottom: 16px;
        }
        .kpi-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.95rem;
            color: #2B3934;
            font-weight: 500;
            margin-bottom: 10px;
        }
        .kpi-value {
            font-size: 2.3rem;
            font-weight: 800;
            color: #16211D;
            line-height: 1.05;
        }
        .trend-icon {
            color: #1E563B;
            font-weight: 700;
            margin-right: 6px;
        }
        .badge-green {
            background-color: #D2E3DB;
            color: #1E563B;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
        }

        .kpi-card-orange {
            background: linear-gradient(135deg, #F59645 0%, #DF7626 100%);
            border-radius: 16px;
            padding: 20px 24px;
            box-shadow: 0 6px 16px rgba(223, 118, 38, 0.25);
            margin-bottom: 16px;
        }
        .badge-peach {
            background-color: #FAD5B6;
            color: #6B2D04;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
        }

        .peach-banner {
            background-color: #F7DEC8;
            border-radius: 16px;
            padding: 24px 26px;
            box-shadow: 0 4px 12px rgba(22, 33, 29, 0.04);
        }

        div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            border-radius: 10px !important;
            border: 1px solid #C8D6CF !important;
        }
    </style>
    ''', unsafe_allow_html=True)

def get_logo_svg(size=36):
    return f'<svg width="{size}" height="{size}" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="20" cy="20" r="20" fill="#1E563B"/><text x="16" y="26" fill="white" font-family="Inter, sans-serif" font-weight="800" font-size="18" text-anchor="middle">W</text><path d="M27 13C24 13 22 15.5 22 18.5C25 18.5 27.5 16.5 27 13Z" fill="#7AC79E"/></svg>'

def get_bin_svg(color="#1E563B"):
    return f'<svg width="18" height="18" viewBox="0 0 24 24" fill="{color}" style="vertical-align: middle; margin-left: 8px; flex-shrink: 0;"><path d="M9 3V4H4V6H5V19C5 20.1 5.9 21 7 21H17C18.1 21 19 20.1 19 19V6H20V4H15V3H9ZM7 6H17V19H7V6ZM9 8V17H11V8H9ZM13 8V17H15V8H13Z"/></svg>'

def render_navbar(active_page: str):
    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
    col_logo, col_nav1, col_nav2, col_nav3, col_nav4, col_user = st.columns([2.2, 1.05, 1.05, 1.25, 1.25, 2.3])

    with col_logo:
        st.markdown(f'<div style="display:flex; align-items:center; gap:10px; padding-top:2px;">{get_logo_svg(34)}<span style="font-size:1.25rem; font-weight:800; color:#16211D; letter-spacing:-0.02em;">Waste Forecast</span></div>', unsafe_allow_html=True)

    with col_nav1:
        if st.button("Overview", key="nav_Overview", type="primary" if active_page == "Overview" else "secondary"):
            st.switch_page("pages/Overview.py")

    with col_nav2:
        if st.button("Forecast", key="nav_Forecast", type="primary" if active_page == "Forecast" else "secondary"):
            st.switch_page("pages/Forecast.py")

    with col_nav3:
        if st.button("Region trend", key="nav_Region_trend", type="primary" if active_page == "Region trend" else "secondary"):
            st.switch_page("pages/Region_Trend.py")

    with col_nav4:
        if st.button("Bin capacity", key="nav_Bin_capacity", type="primary" if active_page == "Bin capacity" else "secondary"):
            st.switch_page("pages/Bin_Capacity.py")

    with col_user:
        u1, u2 = st.columns([1.45, 1])
        user = st.session_state.get("username", "officer")
        with u1:
            st.markdown(f"<div style='text-align:right; padding-top:8px; font-size:0.9rem; color:#2B3934;'>Signed in as <b>{user}</b></div>", unsafe_allow_html=True)
        with u2:
            if st.button("Log out", key="nav_logout"):
                st.session_state.logged_in = False
                st.switch_page("app.py")

    st.markdown("<hr style='margin: 12px 0 24px 0; border: none; border-top: 1px solid #C6D6CE;'>", unsafe_allow_html=True)
