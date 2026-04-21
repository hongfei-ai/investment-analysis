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
_INTEGRATION_SECRETS = (
    "ANTHROPIC_API_KEY",
    "NOTION_TOKEN",
    "NOTION_DEALS_DB_ID",
    "NOTION_OUTPUTS_DB_ID",
    "NOTION_BOT_USER_EMAIL",
    "NOTION_ENABLED",
    "SLACK_WEBHOOK_URL",
)
try:
    for _k in _INTEGRATION_SECRETS:
        if _k in st.secrets:
            os.environ[_k] = str(st.secrets[_k])
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
from auth import User, render_login_gate

inject_theme()

# Dev bypass: set DEV_USER_EMAIL in your environment (or dev_user_email in
# secrets.toml) to skip Google OAuth entirely. Unset both to enable real SSO.
_dev_email = os.environ.get("DEV_USER_EMAIL") or ""
if not _dev_email:
    try:
        _dev_email = st.secrets.get("dev_user_email") or ""
    except Exception:
        _dev_email = ""

if _dev_email:
    current_user = User(email=_dev_email, name=_dev_email.split("@")[0])
else:
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

# Start the Notion poller in a daemon thread. No-op unless NOTION_ENABLED=true.
# Dies when Streamlit Cloud sleeps the app; resumes on the next visit.
try:
    from integrations.poller import start_background_loop
    start_background_loop()
except Exception:
    import logging
    logging.getLogger(__name__).exception("Notion poller failed to start")

pg = st.navigation(
    [
        st.Page("pages/dashboard.py", title="Dashboard", icon="\U0001f4ca", default=True),
        st.Page("pages/deal.py", title="Deal Workspace", icon="\U0001f5c2\ufe0f"),
    ]
)
pg.run()
