"""
pages/dashboard.py — Team deal dashboard.

Lands every authenticated user on a scannable view of the pipeline:
  - Top-row summary tiles (active / in diligence / at IC / added this
    week / stalled)
  - Filter bar (my deals, stage, priority, owner, sector)
  - Deal table with owner, stage, agent progress, thesis verdict,
    last-activity delta, and stalled warnings

Clicking a row stashes the deal name in session_state.current_deal and
switches to pages/deal.py. The "+ Start new deal" button does the same
with the deal's owner pre-set to the current user's email.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import load_deal, atomic_save_deal, _safe_deal_name
from audit import append_audit
from dashboard.queries import (
    DealSummary,
    filter_deals,
    scan_deals,
    stalled_deals,
    summary_tiles,
    days_since_activity,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

_STAGE_LABELS = {
    "sourced":     "Sourced",
    "contacted":   "Contacted",
    "met":         "Met",
    "diligence":   "Diligence",
    "ic":          "IC",
    "term_sheet":  "Term Sheet",
    "invested":    "Invested",
    "passed":      "Passed",
    "tracking":    "Tracking",
}

_STAGE_COLORS = {
    "sourced":    "#8b949e",
    "contacted":  "#3b82f6",
    "met":        "#14b8a6",
    "diligence":  "#f59e0b",
    "ic":         "#a855f7",
    "term_sheet": "#ec4899",
    "invested":   "#10b981",
    "passed":     "#64748b",
    "tracking":   "#64748b",
}

_PRIORITY_COLORS = {"H": "#ef4444", "M": "#f59e0b", "L": "#64748b"}


def _chip(text: str, color: str) -> str:
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
        f'background:{color}22;color:{color};font-size:12px;font-weight:500;'
        f'border:1px solid {color}55">{text}</span>'
    )


def _relative_time(iso_str: str, now: datetime) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return "just now"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 48:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    if months < 12:
        return f"{months}mo ago"
    return f"{months // 12}y ago"


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


# ─── Page ────────────────────────────────────────────────────────────────────

def _header():
    left, right = st.columns([0.7, 0.3])
    with left:
        st.markdown("## Deal pipeline")
    with right:
        st.markdown(
            f"<div style='text-align:right;padding-top:10px;color:#8b949e;"
            f"font-size:13px'>Signed in as "
            f"<b>{st.session_state.get('current_user_email', '')}</b></div>",
            unsafe_allow_html=True,
        )


def _render_tiles(summaries):
    tiles = summary_tiles(summaries)
    cols = st.columns(5)
    for col, (label, key) in zip(
        cols,
        [
            ("Active pipeline", "total_active"),
            ("In diligence",    "in_diligence"),
            ("At IC",           "at_ic"),
            ("Added this week", "added_this_week"),
            ("Stalled (>14d)",  "stalled"),
        ],
    ):
        with col:
            st.metric(label=label, value=tiles[key])


def _render_filter_bar(summaries):
    """Return (my_email_filter, stage_filter, priority_filter, sector_filter)."""
    my_email = st.session_state.get("current_user_email", "")
    all_stages = sorted({s.deal_stage for s in summaries if s.deal_stage})
    all_priorities = ["H", "M", "L"]
    all_sectors = sorted({s.sector for s in summaries if s.sector})

    c1, c2, c3, c4, c5 = st.columns([0.18, 0.25, 0.2, 0.2, 0.17])
    with c1:
        mine_only = st.toggle("My deals only", value=False, key="flt_mine")
    with c2:
        stages = st.multiselect(
            "Stage", options=all_stages,
            format_func=lambda s: _STAGE_LABELS.get(s, s.title()),
            key="flt_stages",
        )
    with c3:
        priorities = st.multiselect("Priority", options=all_priorities, key="flt_prio")
    with c4:
        sector = st.selectbox(
            "Sector", options=[""] + all_sectors,
            format_func=lambda x: "All" if x == "" else x,
            key="flt_sector",
        )
    with c5:
        if st.button("\u2795  New deal", use_container_width=True, type="primary"):
            _start_new_deal_dialog()

    return {
        "my_email": my_email if mine_only else None,
        "stages":   stages or None,
        "priorities": priorities or None,
        "sector":   sector or None,
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
            # Brand-new deal: stamp owner + founder on first save
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

    now = datetime.now(timezone.utc)
    stalled_ids = {s.deal_id for s in stalled_deals(summaries, threshold_days=14, now=now)}

    # Header row
    cols = st.columns([0.22, 0.12, 0.15, 0.08, 0.10, 0.10, 0.10, 0.13])
    for c, label in zip(
        cols,
        ["Company", "Stage", "Owner", "Priority", "Agents",
         "Verdict", "Last activity", "Next step"],
    ):
        c.markdown(f"<div style='color:#8b949e;font-size:12px;font-weight:600'>"
                   f"{label}</div>", unsafe_allow_html=True)

    for s in summaries:
        cols = st.columns([0.22, 0.12, 0.15, 0.08, 0.10, 0.10, 0.10, 0.13])
        stalled_mark = " \u26a0\ufe0f" if s.deal_id in stalled_ids else ""

        with cols[0]:
            if st.button(
                f"{s.company_name}{stalled_mark}",
                key=f"open_{s.deal_id}",
                use_container_width=True,
            ):
                _open_deal(s.deal_id)

        with cols[1]:
            st.markdown(
                _chip(
                    _STAGE_LABELS.get(s.deal_stage, s.deal_stage.title()),
                    _STAGE_COLORS.get(s.deal_stage, "#64748b"),
                ),
                unsafe_allow_html=True,
            )

        with cols[2]:
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

        with cols[3]:
            if s.priority:
                st.markdown(
                    _chip(s.priority, _PRIORITY_COLORS.get(s.priority, "#64748b")),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown("<span style='color:#484f58'>—</span>", unsafe_allow_html=True)

        with cols[4]:
            ratio = f"{s.agents_done}/{s.agents_total}"
            tip = ", ".join(s.agents_done_keys) if s.agents_done_keys else "none"
            st.markdown(
                f"<span title='{tip}' style='font-size:13px;color:#c9d1d9'>"
                f"{ratio}</span>",
                unsafe_allow_html=True,
            )

        with cols[5]:
            if s.thesis_verdict:
                color = {
                    "Strong":   "#10b981",
                    "Moderate": "#f59e0b",
                    "Weak":     "#ef4444",
                    "No Fit":   "#64748b",
                }.get(s.thesis_verdict, "#64748b")
                st.markdown(_chip(s.thesis_verdict, color), unsafe_allow_html=True)
            else:
                st.markdown("<span style='color:#484f58'>—</span>", unsafe_allow_html=True)

        with cols[6]:
            st.markdown(
                f"<span style='font-size:13px;color:#8b949e'>"
                f"{_relative_time(s.updated_at, now)}</span>",
                unsafe_allow_html=True,
            )

        with cols[7]:
            nxt = (s.next_step or "").strip()
            if nxt:
                shown = nxt if len(nxt) <= 40 else nxt[:37] + "…"
                st.markdown(
                    f"<span style='font-size:13px;color:#c9d1d9'>{shown}</span>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown("<span style='color:#484f58'>—</span>", unsafe_allow_html=True)


def main():
    _header()
    summaries = scan_deals()

    _render_tiles(summaries)
    st.divider()

    filters = _render_filter_bar(summaries)
    st.divider()

    filtered = filter_deals(
        summaries,
        my_email=filters["my_email"],
        stages=filters["stages"],
        priorities=filters["priorities"],
        sector=filters["sector"],
        exclude_terminal=False,
    )
    filtered.sort(key=lambda s: s.updated_at, reverse=True)

    _render_table(filtered)


main()
