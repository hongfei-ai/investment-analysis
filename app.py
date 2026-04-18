"""
app.py — Entrypoint for the Investment Analysis platform.

Responsibilities (thin):
  1. Page config + theme injection (must happen exactly once).
  2. Secrets → env bootstrap so shared.py can pick up the API key.
  3. Auth gate (Google Workspace SSO via Streamlit native OIDC).
  4. Session-state defaults shared across pages.
  5. Navigation dispatch to pages/dashboard.py (default) or pages/deal.py.

Run: streamlit run app.py
"""

import os
import sys
from pathlib import Path

import streamlit as st

# Secrets → env must run BEFORE importing shared.py so the Anthropic key is
# visible at module load. Silently tolerate a missing secrets file in dev.
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

st.set_page_config(
    page_title="Investment Analysis",
    page_icon="\U0001f4ca",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from ui import inject_theme
from auth import render_login_gate

inject_theme()

current_user = render_login_gate()
if current_user is None:
    st.stop()
st.session_state["current_user_email"] = current_user.email
st.session_state["current_user_name"] = current_user.name
st.session_state["current_user_picture"] = current_user.picture

# Shared defaults — every page assumes these exist.
for _key, _default in (
    ("current_deal", None),
    ("active_stream", None),
    ("batch_queue", []),
    ("batch_total", 0),
):
    st.session_state.setdefault(_key, _default)

pg = st.navigation(
    [
        st.Page("pages/dashboard.py", title="Dashboard", icon="\U0001f4ca", default=True),
        st.Page("pages/deal.py", title="Deal Workspace", icon="\U0001f5c2\ufe0f"),
    ]
)
pg.run()
