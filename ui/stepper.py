"""Phase pipeline stepper — decorative status display above st.tabs()."""

from __future__ import annotations

import streamlit as st


_PHASES = [
    ("pre-call",       "Pre-Call"),
    ("diligence",      "Diligence"),
    ("post-diligence", "IC Prep"),
    ("complete",       "Complete"),
]


def _state_for(idx: int, current_idx: int) -> str:
    if current_idx > idx:
        return "done"
    if current_idx == idx:
        return "active"
    return "upcoming"


def _resolve_current(status: str | None) -> int:
    if not status:
        return 0
    keys = [k for k, _ in _PHASES]
    if status == "ic-prep":
        return keys.index("post-diligence")
    if status in keys:
        return keys.index(status)
    return 0


def render_stepper(status: str | None, sub_label: str | None = None) -> None:
    """Render the horizontal phase pipeline.

    status: one of pre-call / diligence / post-diligence / ic-prep / complete
    sub_label: optional small text under the active node (e.g. '3/5 agents')
    """
    current_idx = _resolve_current(status)
    nodes_html: list[str] = []

    for i, (_, label) in enumerate(_PHASES):
        state = _state_for(i, current_idx)
        if state == "done":
            circle = '<div class="stepper-circle done">&#10003;</div>'
            label_cls = "stepper-label on"
        elif state == "active":
            circle = f'<div class="stepper-circle active">{i + 1}</div>'
            label_cls = "stepper-label on"
        else:
            circle = f'<div class="stepper-circle">{i + 1}</div>'
            label_cls = "stepper-label"

        sub = (
            f'<div class="stepper-sub">{sub_label}</div>'
            if state == "active" and sub_label else ""
        )
        nodes_html.append(
            f'<div class="stepper-node">{circle}'
            f'<div class="{label_cls}">{label}</div>{sub}</div>'
        )

        if i < len(_PHASES) - 1:
            bar_cls = "stepper-bar done" if current_idx > i else "stepper-bar"
            nodes_html.append(f'<div class="{bar_cls}"></div>')

    st.markdown(
        f'<div class="stepper">{"".join(nodes_html)}</div>',
        unsafe_allow_html=True,
    )
