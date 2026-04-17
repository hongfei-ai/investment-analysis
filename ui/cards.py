"""Stacked agent cards with collapsible sections."""

from __future__ import annotations

import html
import re
from typing import Iterable

import markdown as md
import streamlit as st

from .output_parser import Tally, parse_output
from .theme import AGENT_ACCENTS, COLORS


# ─── Confidence tag substitution (operates on rendered HTML) ──────────────

_TAG_PATTERNS = [
    (re.compile(r"\[HIGH CONFIDENCE\]", re.IGNORECASE),
     '<span class="conf-tag conf-hc">HC<span class="conf-tip">HIGH CONFIDENCE</span></span>'),
    (re.compile(r"\[MEDIUM CONFIDENCE\]", re.IGNORECASE),
     '<span class="conf-tag conf-mc">MC<span class="conf-tip">MEDIUM CONFIDENCE</span></span>'),
    (re.compile(r"\[LOW CONFIDENCE\s*/?\s*INFERRED\]", re.IGNORECASE),
     '<span class="conf-tag conf-lc">LC<span class="conf-tip">LOW CONFIDENCE / INFERRED</span></span>'),
    (re.compile(r"\[LOW CONFIDENCE\]", re.IGNORECASE),
     '<span class="conf-tag conf-lc">LC<span class="conf-tip">LOW CONFIDENCE</span></span>'),
    (re.compile(r"\[INSUFFICIENT DATA[^\]]*\]", re.IGNORECASE),
     '<span class="conf-tag conf-gap">GAP<span class="conf-tip">INSUFFICIENT DATA — requires manual input</span></span>'),
]
_SRC_PATTERN = re.compile(r"\[(?:Source|Cited?|Ref):\s*([^\]]+)\]", re.IGNORECASE)


def _apply_conf_tags(html_text: str) -> str:
    for pattern, replacement in _TAG_PATTERNS:
        html_text = pattern.sub(replacement, html_text)
    html_text = _SRC_PATTERN.sub(
        lambda m: (
            '<span class="conf-tag conf-src">src<span class="conf-tip">'
            f'Source: {html.escape(m.group(1).strip())}</span></span>'
        ),
        html_text,
    )
    return html_text


def _md_to_html(text: str, with_tags: bool = True) -> str:
    rendered = md.markdown(
        text or "",
        extensions=["tables", "fenced_code", "sane_lists"],
        output_format="html5",
    )
    return _apply_conf_tags(rendered) if with_tags else rendered


# ─── Tally rendering ──────────────────────────────────────────────────────

def _tally_badges(t: Tally) -> str:
    parts: list[str] = []
    if t.hc:  parts.append(f'<span class="tally tally-hc">{t.hc} HC</span>')
    if t.mc:  parts.append(f'<span class="tally tally-mc">{t.mc} MC</span>')
    if t.lc:  parts.append(f'<span class="tally tally-lc">{t.lc} LC</span>')
    if t.gap: parts.append(f'<span class="tally tally-gap">{t.gap} GAP</span>')
    return "".join(parts)


# ─── Card rendering ───────────────────────────────────────────────────────

def _empty_card(label: str, accent: str) -> str:
    return (
        f'<div class="agent-card empty" style="border-left-color:{accent}">'
        '<div class="agent-card-head">'
        f'<span class="agent-card-title" style="color:{COLORS["text_dim"]}">{html.escape(label)}</span>'
        '<span class="empty-pill">not run</span>'
        "</div></div>"
    )


def _filled_card(
    label: str,
    accent: str,
    output_text: str,
    skip_confidence: bool,
    initially_open: bool,
) -> str:
    parsed = parse_output(output_text)

    head_tally = "" if skip_confidence else _tally_badges(parsed.total)

    exec_html = ""
    if parsed.exec_summary:
        body_html = _md_to_html(parsed.exec_summary, with_tags=not skip_confidence)
        exec_html = (
            '<div class="exec-summary">'
            '<div class="exec-summary-label">EXECUTIVE SUMMARY</div>'
            f'<div class="exec-summary-body">{body_html}</div>'
            "</div>"
        )

    sections_html_parts: list[str] = []
    for i, section in enumerate(parsed.sections):
        body_html = _md_to_html(section.body, with_tags=not skip_confidence)
        open_attr = " open" if (initially_open and i == 0) else ""
        sections_html_parts.append(
            f'<details class="section"{open_attr}>'
            f'<summary>{html.escape(section.title)}</summary>'
            f'<div class="section-body">{body_html}</div>'
            "</details>"
        )

    sections_html = "".join(sections_html_parts)

    # Entire card is collapsible — header is the toggle, body folds away
    open_attr = " open" if initially_open else " open"  # default open after generation
    return (
        f'<details class="agent-card" style="border-left-color:{accent}"{open_attr}>'
        f'<summary class="agent-card-head">'
        f'<span class="agent-card-title">{html.escape(label)}</span>'
        f'<div class="agent-card-tally">{head_tally}</div>'
        f'</summary>'
        f'<div class="agent-card-body">{exec_html}{sections_html}</div>'
        "</details>"
    )


def render_output_panel(
    deal_name: str,
    agents: Iterable[tuple[str, str]],
    *,
    read_output_fn,
    initially_open_first: bool = False,
    skip_confidence_keys: Iterable[str] = (),
    empty_message: str = "No outputs yet.",
) -> None:
    """Render a stacked panel of agent output cards.

    agents: iterable of (output_key, label).
    read_output_fn: callable(deal, key) -> str | None.
    skip_confidence_keys: output_keys (e.g. agent9_ic_memo) that bypass conf tags + tally.
    """
    skip_set = set(skip_confidence_keys)
    has_any = False
    parts: list[str] = []

    for key, label in agents:
        accent = AGENT_ACCENTS.get(key, COLORS["accent"])
        text = read_output_fn(deal_name, key)
        if text:
            has_any = True
            parts.append(
                _filled_card(
                    label,
                    accent,
                    text,
                    skip_confidence=key in skip_set,
                    initially_open=initially_open_first and not parts,
                )
            )
        else:
            parts.append(_empty_card(label, accent))

    if not has_any:
        st.info(empty_message)
        return

    st.markdown("".join(parts), unsafe_allow_html=True)


# ─── Placeholder-based renderer (for in-place streaming) ──────────────────

def filled_card_html(
    label: str,
    accent: str,
    output_text: str,
    *,
    skip_confidence: bool = False,
    initially_open: bool = False,
) -> str:
    """Public wrapper: return the fully styled card HTML for a completed agent output."""
    return _filled_card(label, accent, output_text, skip_confidence, initially_open)


def empty_card_html(label: str, accent: str) -> str:
    """Public wrapper: return the empty-state card HTML for an agent that has not run."""
    return _empty_card(label, accent)


def streaming_card_html(label: str, accent: str, partial_text: str) -> str:
    """Card chrome with partial markdown body — used while an agent is actively streaming."""
    body = md.markdown(
        partial_text or "",
        extensions=["tables", "fenced_code", "sane_lists"],
        output_format="html5",
    )
    return (
        f'<div class="agent-card" style="border-left-color:{accent}">'
        '<div class="agent-card-head">'
        f'<span class="agent-card-title">{html.escape(label)}</span>'
        '<span class="empty-pill">streaming…</span>'
        "</div>"
        f'<div class="section-body">{body}</div>'
        "</div>"
    )


# ─── H3-split regex (shared with app.py's _split_by_h3) ─────────────────
_H3_SPLIT_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown by ### headers into (title, body) pairs."""
    matches = list(_H3_SPLIT_RE.finditer(text))
    if not matches:
        return [("Output", text)]

    sections: list[tuple[str, str]] = []
    # Discard preamble before the first ### (H2 title line, whitespace, etc.)
    # — the H2 title is already shown in the card header, no need to duplicate.

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((m.group(1).strip(), text[m.end() : end].strip()))

    return sections


def streaming_sectioned_card_html(label: str, accent: str, partial_text: str) -> str:
    """Card with per-section rendering during streaming.

    Completed sections (all but the last) render as collapsed <details>.
    The active (last) section renders open with a streaming indicator.
    """
    text = (partial_text or "").strip()
    sections = _split_sections(text)

    head = (
        f'<div class="agent-card-head">'
        f'<span class="agent-card-title">{html.escape(label)}</span>'
        f'<span class="empty-pill">streaming…</span>'
        f'</div>'
    )

    parts: list[str] = []
    for i, (title, body) in enumerate(sections):
        is_last = (i == len(sections) - 1)
        body_html = md.markdown(
            body or "",
            extensions=["tables", "fenced_code", "sane_lists"],
            output_format="html5",
        )
        body_html = _apply_conf_tags(body_html)

        if is_last:
            # Active section — open, with streaming indicator
            status = (
                ' <span style="color:var(--accent,#00d4aa);font-size:0.8em;'
                'font-weight:400;margin-left:auto">streaming…</span>'
            )
            parts.append(
                f'<details class="section" open>'
                f'<summary>{html.escape(title)}{status}</summary>'
                f'<div class="section-body">{body_html}</div>'
                f'</details>'
            )
        else:
            # Completed section — collapsed
            parts.append(
                f'<details class="section">'
                f'<summary>{html.escape(title)}</summary>'
                f'<div class="section-body">{body_html}</div>'
                f'</details>'
            )

    return (
        f'<div class="agent-card" style="border-left-color:{accent}">'
        f'{head}{"".join(parts)}'
        f'</div>'
    )


def render_cards_with_placeholders(
    deal_name: str,
    agents: Iterable[tuple[str, str]],
    *,
    read_output_fn,
    initially_open_first: bool = False,
    skip_confidence_keys: Iterable[str] = (),
) -> dict[str, dict]:
    """Render one st.empty() per agent and return a handle-dict for in-place streaming.

    Returns: {agent_key: {"placeholder": st.empty, "label": str, "accent": str, "skip_conf": bool}}
    """
    skip_set = set(skip_confidence_keys)
    handles: dict[str, dict] = {}
    first_filled_rendered = False

    for key, label in agents:
        accent = AGENT_ACCENTS.get(key, COLORS["accent"])
        text = read_output_fn(deal_name, key)
        placeholder = st.empty()
        skip_conf = key in skip_set

        if text:
            open_this = initially_open_first and not first_filled_rendered
            first_filled_rendered = True
            placeholder.markdown(
                _filled_card(label, accent, text, skip_conf, open_this),
                unsafe_allow_html=True,
            )
        else:
            placeholder.markdown(_empty_card(label, accent), unsafe_allow_html=True)

        handles[key] = {
            "placeholder": placeholder,
            "label": label,
            "accent": accent,
            "skip_conf": skip_conf,
        }

    return handles
