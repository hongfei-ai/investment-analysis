"""
pages/dashboard.py — Deal Evaluation Dashboard.

Two summary tiles (Total Deals Evaluated, Total Agents Run), two filter
toggles (My deals, Active), and a wide table with per-agent checkmarks.
"""

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import load_deal, atomic_save_deal, _safe_deal_name
from audit import append_audit
from auth import is_editor, User
from dashboard.queries import (
    AGENT_SEQUENCE,
    filter_deals,
    scan_deals,
    summary_tiles,
)
from ui import render_theme_toggle


# Human-readable labels for each agent, matching AGENT_SEQUENCE order.
_AGENT_COLUMNS: list[tuple[str, str, str]] = [
    ("agent1_precall",        "Pre-call",    "Pre-call research"),
    ("agent2_diligence_mgmt", "Dil. Mgmt",   "Diligence management"),
    ("agent3_founder",        "Founder",     "Founder diligence"),
    ("agent4_market",         "Market",      "Market diligence"),
    ("agent5_traction",       "Traction",    "Customer & traction intelligence"),
    ("agent6_thesis",         "Thesis",      "Thesis fit"),
    ("agent7_premortem",      "Pre-mortem",  "Pre-mortem"),
    ("agent8_ic_simulation",  "IC Sim",      "IC simulation"),
    ("agent9_ic_memo",        "IC Memo",     "IC memo"),
]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _open_deal(deal_name: str) -> None:
    st.session_state.current_deal = deal_name
    st.switch_page("pages/deal.py")


def _current_user() -> User:
    return User(email=st.session_state.get("current_user_email", ""))


def _claim_deal(deal_name: str) -> None:
    me = st.session_state.get("current_user_email", "")
    if not me:
        st.error("Not signed in.")
        return
    deal = load_deal(deal_name)
    if deal.get("owner_email") not in (None, "", "unassigned"):
        st.warning(f"Deal already owned by {deal['owner_email']}")
        return
    deal["owner_email"] = me
    deal.setdefault("created_by", me)
    atomic_save_deal(deal)
    append_audit(deal_name, actor=me, action="owner_claimed", details={"new_owner": me})
    st.rerun()


def _toggle_active(deal_name: str, new_value: bool) -> None:
    """Flip is_active on a deal. Owner/collab only; no-op for viewers."""
    user = _current_user()
    deal = load_deal(deal_name)
    if not is_editor(deal, user):
        st.warning(f"Only the owner of {deal_name} can change its active state.")
        return
    deal["is_active"] = bool(new_value)
    atomic_save_deal(deal)
    append_audit(
        deal_name, actor=user.email, action="metadata_changed",
        details={"field": "is_active", "from": not new_value, "to": new_value},
    )


def _fmt_date(iso_str: str) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        return "—"
    return dt.strftime("%Y-%m-%d")


# ─── Layout ──────────────────────────────────────────────────────────────────

def _header():
    left, mid, right = st.columns([0.55, 0.2, 0.25])
    with left:
        st.markdown("## Deal Evaluation Dashboard")
    with mid:
        render_theme_toggle("theme_toggle_dashboard")
    with right:
        st.markdown(
            f"<div style='text-align:right;padding-top:10px;color:var(--text-muted);"
            f"font-size:13px'>Signed in as "
            f"<b>{st.session_state.get('current_user_email', '')}</b></div>",
            unsafe_allow_html=True,
        )


def _render_tiles(summaries):
    tiles = summary_tiles(summaries)
    c1, c2 = st.columns(2)
    with c1:
        st.metric(label="Total Deals Evaluated", value=tiles["total_deals"])
    with c2:
        st.metric(label="Total Agents Run", value=tiles["total_agents_run"])


def _render_filter_bar():
    """Return the active filter dict."""
    my_email = st.session_state.get("current_user_email", "")

    c1, c2, c3 = st.columns([0.25, 0.2, 0.55])
    with c1:
        mine_only = st.toggle("My deals only", value=False, key="flt_mine")
    with c2:
        active_only = st.toggle("Active only", value=False, key="flt_active")
    with c3:
        sp1, sp2 = st.columns([0.55, 0.45])
        with sp2:
            if st.button("\u2795  New deal", use_container_width=True, type="primary"):
                _start_new_deal_dialog()

    return {
        "my_email":    my_email if mine_only else None,
        "active_only": active_only,
    }


@st.dialog("Start a new deal")
def _start_new_deal_dialog():
    company = st.text_input("Company name", placeholder="e.g. Acme Robotics")
    founder = st.text_input("Founder name", placeholder="e.g. Ada Lovelace")
    submitted = st.button("Create", type="primary", disabled=not company.strip())
    if submitted:
        try:
            safe = _safe_deal_name(company.strip())
        except ValueError as e:
            st.error(str(e))
            return
        deal = load_deal(safe)
        is_new = deal.get("_version", 0) == 0
        me = st.session_state.get("current_user_email") or "unassigned"

        deal["company_name"] = company.strip()
        if founder.strip():
            deal.setdefault("inputs", {})["founder_name"] = founder.strip()
        if is_new:
            deal["owner_email"] = me
            deal["created_by"] = me

        atomic_save_deal(deal)
        if is_new:
            append_audit(safe, actor=me, action="deal_created",
                         details={"founder": founder.strip() or None})
        _open_deal(safe)


def _col_widths() -> list[float]:
    # Company | Owner | Active | [9 agent columns] | Added | Modified
    return [0.12, 0.12, 0.07] + [0.05] * len(_AGENT_COLUMNS) + [0.08, 0.08]


def _render_table_header():
    widths = _col_widths()
    cols = st.columns(widths)
    labels = ["Company", "Owner", "Active"] + \
             [label for _, label, _ in _AGENT_COLUMNS] + \
             ["Added", "Modified"]
    tooltips = ["", "", "Toggle to archive inactive deals"] + \
               [tip for _, _, tip in _AGENT_COLUMNS] + \
               ["Date added", "Last modified"]
    for c, label, tip in zip(cols, labels, tooltips):
        c.markdown(
            f"<div title='{tip}' style='color:var(--text-muted);font-size:11px;"
            f"font-weight:600;text-transform:uppercase;letter-spacing:0.04em'>"
            f"{label}</div>",
            unsafe_allow_html=True,
        )


def _render_row(s, editable: bool):
    widths = _col_widths()
    cols = st.columns(widths)

    with cols[0]:
        if st.button(s.company_name, key=f"open_{s.deal_id}",
                     use_container_width=True):
            _open_deal(s.deal_id)

    with cols[1]:
        owner = s.owner_email or "unassigned"
        if owner == "unassigned":
            if st.button("Claim", key=f"claim_{s.deal_id}",
                         help="Assign this deal to you", type="secondary"):
                _claim_deal(s.deal_id)
        else:
            st.markdown(
                f"<span style='font-size:12px;color:var(--text)'>{owner}</span>",
                unsafe_allow_html=True,
            )

    with cols[2]:
        new_val = st.toggle(
            "active",
            value=s.is_active,
            key=f"active_{s.deal_id}",
            label_visibility="collapsed",
            disabled=not editable,
        )
        if editable and new_val != s.is_active:
            _toggle_active(s.deal_id, new_val)
            st.rerun()

    done_set = set(s.agents_done_keys)
    for i, (agent_key, _, _) in enumerate(_AGENT_COLUMNS):
        with cols[3 + i]:
            mark = "\u2713" if agent_key in done_set else "\u2014"
            color = "var(--accent)" if agent_key in done_set else "var(--text-dim)"
            st.markdown(
                f"<div style='text-align:center;font-size:14px;color:{color};"
                f"padding-top:6px'>{mark}</div>",
                unsafe_allow_html=True,
            )

    with cols[3 + len(_AGENT_COLUMNS)]:
        st.markdown(
            f"<span style='font-size:12px;color:var(--text-muted)'>"
            f"{_fmt_date(s.date_created)}</span>",
            unsafe_allow_html=True,
        )
    with cols[3 + len(_AGENT_COLUMNS) + 1]:
        st.markdown(
            f"<span style='font-size:12px;color:var(--text-muted)'>"
            f"{_fmt_date(s.updated_at)}</span>",
            unsafe_allow_html=True,
        )


def _render_table(summaries):
    if not summaries:
        st.info("No deals match the current filters. Start one with **+ New deal**.")
        return

    _render_table_header()
    user = _current_user()
    for s in summaries:
        deal = load_deal(s.deal_id)
        editable = is_editor(deal, user)
        _render_row(s, editable=editable)


def main():
    _header()
    summaries = scan_deals()

    _render_tiles(summaries)
    st.divider()

    filters = _render_filter_bar()
    st.divider()

    filtered = filter_deals(
        summaries,
        my_email=filters["my_email"],
        active_only=filters["active_only"],
    )
    filtered.sort(key=lambda s: s.updated_at, reverse=True)

    _render_table(filtered)


main()
