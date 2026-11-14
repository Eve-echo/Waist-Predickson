import pandas as pd
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
            border-radius: 4px;
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

        .st-key-nav_profile { display: flex; justify-content: flex-end; }
        .st-key-nav_profile button {
            border-radius: 4px !important;
            border: 1px solid #8AA699 !important;
            background-color: transparent !important;
            padding: 0.3rem 0.45rem !important;
            min-height: 0 !important;
            color: #1E563B !important;
        }
        .st-key-nav_profile button:hover { background-color: #C7DBD1 !important; border-color: #1E563B !important; }
        .st-key-nav_profile button svg { width: 1.7rem; height: 1.7rem; }
        .st-key-nav_profile button [data-testid="stIconMaterial"] { font-size: 1.7rem !important; }
        .st-key-nav_profile button p { display: none; }

        div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            border-radius: 10px !important;
            border: 1px solid #C8D6CF !important;
        }
    </style>
    ''', unsafe_allow_html=True)

def get_logo_svg(size=36):
    return f'<svg width="{size}" height="{size}" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="20" cy="20" r="20" fill="#1E563B"/><text x="16" y="26" fill="white" font-family="Inter, sans-serif" font-weight="800" font-size="18" text-anchor="middle">W</text><path d="M27 13C24 13 22 15.5 22 18.5C25 18.5 27.5 16.5 27 13Z" fill="#7AC79E"/></svg>'

def render_navbar(active_page: str):
    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
    col_logo, col_nav1, col_nav2, col_nav3, col_nav4, col_user = st.columns([2.2, 1.05, 1.05, 1.25, 1.25, 2.3])

    with col_logo:
        st.markdown(f'<div style="display:flex; align-items:center; gap:10px; padding-top:2px;">{get_logo_svg(34)}<span style="font-size:1.25rem; font-weight:800; color:#16211D; letter-spacing:-0.02em;">Waste Forecast</span></div>', unsafe_allow_html=True)

    with col_nav1:
        if st.button("Home", key="nav_Home", type="primary" if active_page == "Home" else "secondary"):
            st.switch_page("pages/Home.py")

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
        _, col_profile = st.columns([4, 1])
        user = st.session_state.get("username", "")
        role = st.session_state.get("role", "")
        with col_profile:
            with st.popover("", icon=":material/account_circle:", key="nav_profile", help="Profile"):
                st.markdown(
                    f"<div style='padding:2px 4px 8px 4px; min-width:150px;'>"
                    f"<div style='font-weight:700; color:#16211D;'>{user}</div>"
                    f"<div style='font-size:0.8rem; color:#5B6B64; text-transform:capitalize;'>{role}</div></div>",
                    unsafe_allow_html=True,
                )
                if st.button("Edit profile", key="nav_edit_profile", icon=":material/edit:", width="stretch"):
                    st.switch_page("pages/Profile.py")
                if st.button("Log out", key="nav_logout", icon=":material/logout:", width="stretch"):
                    st.session_state.logged_in = False
                    st.session_state.username = ""
                    st.session_state.role = ""
                    st.switch_page("app.py")

    st.markdown("<hr style='margin: 12px 0 24px 0; border: none; border-top: 4px solid #9DB8AB; border-radius: 4px;'>", unsafe_allow_html=True)


def require_login():
    """Send visitors who are not signed in back to the login page."""
    if not st.session_state.get("logged_in"):
        st.switch_page("app.py")


def kpi_card(label: str, value: str, badge: str | None = None, accent: bool = False) -> str:
    """HTML for one KPI tile; accent=True renders the orange call-to-action variant."""
    cls = "kpi-card-orange" if accent else "kpi-card"
    badge_cls = "badge-peach" if accent else "badge-green"
    badge_html = f'<span class="{badge_cls}">{badge}</span>' if badge else ""
    value_style = ' style="color:#6E2E04;"' if accent else ""
    return (f'<div class="{cls}"><div class="kpi-header"><span>{label}</span>{badge_html}</div>'
            f'<div class="kpi-value"{value_style}>{value}</div></div>')


def page_header(title: str, subtitle: str):
    st.markdown(f"<h1 style='margin-bottom:2px; font-size:2.2rem; font-weight:800; color:#16211D;'>{title}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#2B3934; font-size:1rem; margin-bottom:20px;'>{subtitle}</p>", unsafe_allow_html=True)


def fmt_change(new: float, old: float) -> str | None:
    """Signed percentage change, or None when it cannot be computed."""
    if old is None or not old or pd.isna(old) or pd.isna(new):
        return None
    return f"{(new - old) / old * 100:+.1f}%"