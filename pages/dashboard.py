"""
pages/dashboard.py — Deal Evaluation Dashboard.

Two summary tiles (Total Deals Evaluated, Total Agents Run), a minimal
filter bar (My deals toggle, Priority, + New deal), and a three-column
deal table (Company, Owner, Total Agents Run). Clicking a company name
stashes the deal in session_state and switches to pages/deal.py.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import load_deal, atomic_save_deal, _safe_deal_name
from audit import append_audit
from dashboard.queries import (
    filter_deals,
    scan_deals,
    summary_tiles,
)


def _open_deal(deal_name: str) -> None:
    st.session_state.current_deal = deal_name
    st.switch_page("pages/deal.py")


def _claim_deal(deal_name: str) -> None:
    """Assign an unassigned deal to the current user. No-op if already owned."""
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


def _header():
    left, right = st.columns([0.7, 0.3])
    with left:
        st.markdown("## Deal Evaluation Dashboard")
    with right:
        st.markdown(
            f"<div style='text-align:right;padding-top:10px;color:#8b949e;"
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
    all_priorities = ["H", "M", "L"]

    c1, c2, c3 = st.columns([0.25, 0.35, 0.4])
    with c1:
        mine_only = st.toggle("My deals only", value=False, key="flt_mine")
    with c2:
        priorities = st.multiselect("Priority", options=all_priorities, key="flt_prio")
    with c3:
        if st.button("\u2795  New deal", use_container_width=True, type="primary"):
            _start_new_deal_dialog()

    return {
        "my_email":   my_email if mine_only else None,
        "priorities": priorities or None,
    }


@st.dialog("Start a new deal")
def _start_new_deal_dialog():
    """Minimal create-deal form; fills a skeleton and opens the workspace."""
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
        if is_new:
            deal["owner_email"] = me
            deal["created_by"] = me
            if founder.strip():
                deal["inputs"]["founder_name"] = founder.strip()
        atomic_save_deal(deal)
        if is_new:
            append_audit(safe, actor=me, action="deal_created",
                         details={"founder": founder.strip() or None})
        _open_deal(safe)


def _render_table(summaries):
    if not summaries:
        st.info("No deals match the current filters. Start one with **+ New deal**.")
        return

    cols = st.columns([0.45, 0.35, 0.20])
    for c, label in zip(cols, ["Company", "Owner", "Total Agents Run"]):
        c.markdown(
            f"<div style='color:#8b949e;font-size:12px;font-weight:600'>{label}</div>",
            unsafe_allow_html=True,
        )

    for s in summaries:
        cols = st.columns([0.45, 0.35, 0.20])

        with cols[0]:
            if st.button(
                s.company_name,
                key=f"open_{s.deal_id}",
                use_container_width=True,
            ):
                _open_deal(s.deal_id)

        with cols[1]:
            owner = s.owner_email or "unassigned"
            if owner == "unassigned":
                if st.button("Claim", key=f"claim_{s.deal_id}",
                             help="Assign this deal to you", type="secondary"):
                    _claim_deal(s.deal_id)
            else:
                st.markdown(
                    f"<span style='font-size:13px;color:#c9d1d9'>{owner}</span>",
                    unsafe_allow_html=True,
                )

        with cols[2]:
            st.markdown(
                f"<span style='font-size:13px;color:#c9d1d9'>"
                f"{s.agents_done}</span>",
                unsafe_allow_html=True,
            )


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
        priorities=filters["priorities"],
    )
    filtered.sort(key=lambda s: s.updated_at, reverse=True)

    _render_table(filtered)


main()
