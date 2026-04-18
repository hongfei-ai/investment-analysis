"""
app.py — Streamlit UI for Investment Analysis Pipeline
Run: streamlit run app.py
"""

import sys
import os
import re
import html as _html
import streamlit as st
from pathlib import Path
from datetime import datetime
import markdown as _md

# Inject Streamlit secrets into env vars BEFORE importing shared.py
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))

from shared import (
    load_deal, save_deal, save_output, read_pdf, stream_claude,
    list_deals, read_output, parse_technical_diligence_required, extract_file_text,
    DEALS_DIR, OUTPUTS_DIR, MODEL_SONNET,
)

from ui import inject_theme, render_stepper
from ui.cards import (
    render_cards_with_placeholders,
    streaming_card_html,
    streaming_sectioned_card_html,
    filled_card_html,
)

from agents.prompts import (
    AGENT1_SYSTEM, agent1_user,
    AGENT2_SYSTEM, agent2_user,
    AGENT3_SYSTEM, agent3_user,
    AGENT4_SYSTEM, agent4_user,
    AGENT5_SYSTEM, agent5_user,
    AGENT6_SYSTEM, agent6_user,
    AGENT7_SYSTEM, agent7_user,
    AGENT8_SYSTEM, agent8_user,
    AGENT9_SYSTEM, agent9_user,
)
from agents.agent1_precall import AGENT1_TOOLS, AGENT1_MAX_TOKENS
from agents.agent4_market import AGENT4_TOOLS, AGENT4_MAX_TOKENS

# ─── Page Config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Investment Analysis",
    page_icon="\U0001f4ca",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_theme()

# ─── Authentication ──────────────────────────────────────────────────────────

def check_password() -> bool:
    try:
        correct_pw = st.secrets["app_password"]
    except (KeyError, FileNotFoundError):
        return True
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if st.session_state.authenticated:
        return True
    st.title("\U0001f4ca Investment Analysis")
    st.caption("January Capital \u2014 Internal Tool")
    pw = st.text_input("Password", type="password", placeholder="Enter password...")
    if pw:
        if pw == correct_pw:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not check_password():
    st.stop()

# ─── Session State Init ─────────────────────────────────────────────────────

if "current_deal" not in st.session_state:
    st.session_state.current_deal = None
if "active_stream" not in st.session_state:
    st.session_state.active_stream = None
if "batch_queue" not in st.session_state:
    st.session_state.batch_queue = []
if "batch_total" not in st.session_state:
    st.session_state.batch_total = 0

# ─── Top Bar: Deal Selector ─────────────────────────────────────────────────

top_col1, top_col2, top_col3 = st.columns([2, 6, 2])

with top_col1:
    st.markdown(
        f'<div style="font-size:17px;font-weight:700;padding-top:6px;">'
        f'<span style="color:#00d4aa">&#9632;</span> Investment Analysis</div>',
        unsafe_allow_html=True,
    )

with top_col2:
    existing_deals = list_deals()
    deal_options = ["-- New Deal --"] + existing_deals
    selected = st.selectbox(
        "Select Deal",
        deal_options,
        index=0 if not st.session_state.current_deal else
              (deal_options.index(st.session_state.current_deal)
               if st.session_state.current_deal in deal_options else 0),
        label_visibility="collapsed",
    )
    if selected != "-- New Deal --":
        st.session_state.current_deal = selected

with top_col3:
    if st.session_state.current_deal:
        deal_info = load_deal(st.session_state.current_deal)
        founder = deal_info["inputs"].get("founder_name", "")
        if founder:
            st.markdown(
                f'<div style="text-align:right;padding-top:8px;color:#8b949e;font-size:13px">'
                f'{founder}</div>',
                unsafe_allow_html=True,
            )

# ─── Phase Stepper ──────────────────────────────────────────────────────────

if st.session_state.current_deal:
    deal_info = load_deal(st.session_state.current_deal)
    render_stepper(deal_info.get("status", "pre-call"))
else:
    render_stepper(None)

# ─── Phase Tabs ──────────────────────────────────────────────────────────────

tab1, tab2, tab3 = st.tabs([
    "Phase 1: Pre-Call Research",
    "Phase 2: Post-Call Diligence",
    "Phase 3: IC Preparation",
])


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Registry & Streaming Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _a2_post(deal_name: str, output: str) -> None:
    deal = load_deal(deal_name)
    deal["diligence"]["technical_diligence_required"] = parse_technical_diligence_required(output)
    save_deal(deal)


def _a6_post(deal_name: str, output: str) -> None:
    deal = load_deal(deal_name)
    all_done = all(
        isinstance(deal["diligence"].get(f), str) and deal["diligence"][f].strip()
        for f in ("tracker", "founder_diligence", "market_diligence", "reference_check", "thesis_check")
    )
    if all_done:
        deal["status"] = "post-diligence"
        save_deal(deal)


def _a9_post(deal_name: str, output: str) -> None:
    deal = load_deal(deal_name)
    deal["status"] = "complete"
    save_deal(deal)


def _a1_post(deal_name: str, output: str) -> None:
    # Phase 1 doesn't change status here — the brief is the deliverable.
    pass


AGENT_REGISTRY: dict[str, dict] = {
    "agent1_precall": {
        "system": AGENT1_SYSTEM, "user_fn": agent1_user,
        "section": "pre_call", "field": "research_output",
        "label": "Agent 1: Pre-Call Research",
        "max_tokens": AGENT1_MAX_TOKENS, "tools": AGENT1_TOOLS,
        "post_save": _a1_post,
    },
    "agent2_diligence_mgmt": {
        "system": AGENT2_SYSTEM, "user_fn": agent2_user,
        "section": "diligence", "field": "tracker",
        "label": "Agent 2: Diligence Management",
        "max_tokens": 8000, "tools": None,
        "model": MODEL_SONNET,
        "post_save": _a2_post,
    },
    "agent3_founder_diligence": {
        "system": AGENT3_SYSTEM, "user_fn": agent3_user,
        "section": "diligence", "field": "founder_diligence",
        "label": "Agent 3: Founder Diligence",
        "max_tokens": 8000, "tools": None,
        "post_save": None,
        "sectioned_stream": True,
    },
    "agent4_market_diligence": {
        "system": AGENT4_SYSTEM, "user_fn": agent4_user,
        "section": "diligence", "field": "market_diligence",
        "label": "Agent 4: Market Diligence",
        "max_tokens": AGENT4_MAX_TOKENS, "tools": AGENT4_TOOLS,
        "post_save": None,
        "sectioned_stream": True,
    },
    "agent5_reference_check": {
        "system": AGENT5_SYSTEM, "user_fn": agent5_user,
        "section": "diligence", "field": "reference_check",
        "label": "Agent 5: Customer & Traction Intelligence",
        "max_tokens": 8000, "tools": None,
        "model": MODEL_SONNET,
        "post_save": None,
    },
    "agent6_thesis_check": {
        "system": AGENT6_SYSTEM, "user_fn": agent6_user,
        "section": "diligence", "field": "thesis_check",
        "label": "Agent 6: Thesis Check",
        "max_tokens": 8000, "tools": None,
        "model": MODEL_SONNET,
        "post_save": _a6_post,
    },
    "agent7_premortem": {
        "system": AGENT7_SYSTEM, "user_fn": agent7_user,
        "section": "ic_preparation", "field": "pre_mortem",
        "label": "Agent 7: Pre-Mortem",
        "max_tokens": 8000, "tools": None,
        "model": MODEL_SONNET,
        "post_save": None,
    },
    "agent8_ic_simulation": {
        "system": AGENT8_SYSTEM, "user_fn": agent8_user,
        "section": "ic_preparation", "field": "ic_simulation",
        "label": "Agent 8: IC Simulation",
        "max_tokens": 8000, "tools": None,
        "post_save": None,
    },
    "agent9_ic_memo": {
        "system": AGENT9_SYSTEM, "user_fn": agent9_user,
        "section": "ic_preparation", "field": "ic_memo",
        "label": "Agent 9: IC Memo",
        "max_tokens": 12000, "tools": None,
        "post_save": _a9_post,
    },
}


_H2_START_RE = re.compile(r"^##\s+", re.MULTILINE)


def _strip_cot_preamble(text: str) -> str:
    """Strip chain-of-thought text before the first ## H2 header.

    Web-search agents often emit planning text ("Let me begin by...")
    before the structured output. This preamble pollutes exec summary
    extraction and creates phantom sections.
    """
    m = _H2_START_RE.search(text)
    if m and m.start() > 0:
        return text[m.start():]
    return text


def stream_into_card(handles: dict, key: str, deal_name: str) -> str | None:
    """Stream agent output into a right-panel card placeholder, then swap to styled card.

    On success: saves output, runs post_save, replaces placeholder with styled HTML, returns text.
    On failure: replaces placeholder with an in-card error message, returns None.
    Caller is responsible for clearing st.session_state flags.
    """
    handle = handles[key]
    placeholder = handle["placeholder"]
    label = handle["label"]
    accent = handle["accent"]
    skip_conf = handle["skip_conf"]
    cfg = AGENT_REGISTRY[key]

    deal = load_deal(deal_name)
    accumulated = ""
    use_sectioned = cfg.get("sectioned_stream", False)
    try:
        generator = stream_claude(
            cfg["system"], cfg["user_fn"](deal),
            max_tokens=cfg["max_tokens"], tools=cfg.get("tools"),
            model=cfg.get("model"),
        )
        for chunk in generator:
            accumulated += chunk
            if use_sectioned:
                placeholder.markdown(
                    streaming_sectioned_card_html(label, accent, accumulated),
                    unsafe_allow_html=True,
                )
            else:
                placeholder.markdown(
                    streaming_card_html(label, accent, accumulated),
                    unsafe_allow_html=True,
                )
        # Strip chain-of-thought preamble before first ## header
        # (web_search agents often emit planning text before structured output)
        accumulated = _strip_cot_preamble(accumulated)
        deal[cfg["section"]][cfg["field"]] = accumulated
        save_deal(deal)
        save_output(deal_name, key, accumulated)
        if cfg.get("post_save"):
            cfg["post_save"](deal_name, accumulated)
        placeholder.markdown(
            filled_card_html(label, accent, accumulated, skip_confidence=skip_conf),
            unsafe_allow_html=True,
        )
        return accumulated
    except Exception as e:
        placeholder.error(f"{label} failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Agent button row (used in Phase 2 & 3 left panels)
# ═══════════════════════════════════════════════════════════════════════════════

def agent_button(label, caption, key, output_key, disabled=False):
    """Render an agent description + run button. Returns True if clicked."""
    st.markdown(f"**{label}**")
    st.caption(caption)
    exists = read_output(st.session_state.current_deal, output_key) is not None
    btn_label = "\u21bb Re-run" if exists else "\u25b6 Run"
    return st.button(btn_label, key=key, type="primary", use_container_width=True, disabled=disabled)


def render_left_status() -> None:
    """If a stream is active in this run, show a spinner-style status message in the left panel."""
    active = st.session_state.get("active_stream")
    queue = st.session_state.get("batch_queue") or []
    total = st.session_state.get("batch_total", 0)
    if active and active in AGENT_REGISTRY:
        st.info(f"\u23f3 Running {AGENT_REGISTRY[active]['label']}\u2026")
    elif queue:
        running = queue[0]
        if running in AGENT_REGISTRY:
            done = total - len(queue)
            st.info(
                f"\u23f3 Running {AGENT_REGISTRY[running]['label']}\u2026 "
                f"({done + 1}/{total})"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Section-based brief renderer (splits by ### headers)
# ═══════════════════════════════════════════════════════════════════════════════

_H3_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)

MAX_BRIEF_SECTIONS = 15  # pre-allocate this many slots


def _split_by_h3(text: str) -> list[tuple[str, str]]:
    """Split markdown text by ### headers. Returns [(title, body), ...]."""
    matches = list(_H3_RE.finditer(text))
    sections: list[tuple[str, str]] = []

    if not matches:
        return [("Output", text)]

    # Preamble before the first ### header (H2 title + any intro text)
    preamble = text[: matches[0].start()].strip()
    # Strip any leading H2 line from the preamble
    preamble_body = re.sub(r"^##\s+.+?\n*", "", preamble).strip()
    if preamble_body:
        sections.append(("Research Process", preamble_body))

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        title = m.group(1).strip()
        body = text[m.end() : end].strip()
        sections.append((title, body))

    return sections


def _section_html(title: str, body: str, *, open: bool = False,
                  streaming: bool = False) -> str:
    """Render one section as a styled <details> card matching the theme."""
    body_html = _md.markdown(
        body or "", extensions=["tables", "fenced_code", "sane_lists"],
        output_format="html5",
    )
    open_attr = " open" if open else ""
    status = ""
    if streaming:
        status = (
            ' <span style="color:var(--accent,#00d4aa);font-size:0.8em;'
            'font-weight:400;margin-left:auto">streaming…</span>'
        )
    return (
        f'<details class="section"{open_attr}>'
        f'<summary>{_html.escape(title)}{status}</summary>'
        f'<div class="section-body">{body_html}</div>'
        f'</details>'
    )


def _rebuild_output(sections: list[tuple[str, str]]) -> str:
    """Reassemble section list back into markdown text."""
    parts = []
    for title, body in sections:
        if title == "Research Process":
            # Preamble — no header prefix
            parts.append(body)
        else:
            parts.append(f"### {title}\n\n{body}")
    return "\n\n".join(parts)


_SECTION_RERUN_SYSTEM = """You are a senior venture capital analyst at January Capital. You are re-running ONE specific section of a pre-call research brief. You have access to a web search tool — use it to find fresh, specific information for this section.

You will be given:
1. The deal context (founder, company, inputs)
2. The existing full brief for context
3. The specific section to regenerate

Output ONLY the content for that section — no section header, no preamble, no other sections. Write the content as if it's the body under that section heading."""


def _rerun_section_prompt(deal: dict, full_brief: str, section_title: str) -> str:
    inputs = deal["inputs"]
    deck_text = deal.get("_deck_text", "")
    return f"""
Founder: {inputs['founder_name']}
LinkedIn: {inputs['founder_linkedin']}
Company: {deal['company_name']}
Website: {inputs.get('company_website', 'Unknown')}

{"Pitch Deck Content:\\n" + deck_text if deck_text else "No pitch deck provided."}

Here is the existing full research brief for context:
---
{full_brief}
---

Please regenerate ONLY this section: **{section_title}**

Do deeper research on this specific topic. Use web search to find new or better information. Output only the body content for this section — no ### header, no other sections.
"""


def render_sectioned_brief(output_text: str) -> None:
    """Render a completed brief with per-section re-run buttons."""
    sections = _split_by_h3(output_text)
    for i, (title, body) in enumerate(sections):
        col_title, col_btn = st.columns([6, 1])
        with col_btn:
            if st.button("↻", key=f"rerun_sec_{i}", help=f"Re-run: {title}"):
                st.session_state.p1_rerun_idx = i
                st.rerun()
        with col_title:
            st.markdown(
                _section_html(title, body, open=(i == 0)),
                unsafe_allow_html=True,
            )


def stream_sectioned_brief(deal_name: str) -> None:
    """Stream Agent 1 output into per-section cards that fill up in real-time.

    Completed sections render once and stay; the active section updates live.
    """
    cfg = AGENT_REGISTRY["agent1_precall"]
    deal = load_deal(deal_name)

    # Pre-allocate empty placeholder slots
    slots = [st.empty() for _ in range(MAX_BRIEF_SECTIONS)]
    finalized = [False] * MAX_BRIEF_SECTIONS  # track which slots are done

    accumulated = ""
    try:
        generator = stream_claude(
            cfg["system"], cfg["user_fn"](deal),
            max_tokens=cfg["max_tokens"], tools=cfg.get("tools"),
            model=cfg.get("model"),
        )
        for chunk in generator:
            accumulated += chunk
            sections = _split_by_h3(accumulated)

            for i, (title, body) in enumerate(sections):
                if i >= MAX_BRIEF_SECTIONS:
                    break
                is_last = (i == len(sections) - 1)

                if is_last:
                    # Active section — update on every chunk
                    slots[i].markdown(
                        _section_html(title, body, open=True, streaming=True),
                        unsafe_allow_html=True,
                    )
                elif not finalized[i]:
                    # Just completed — render once, mark done
                    slots[i].markdown(
                        _section_html(title, body, open=(i == 0)),
                        unsafe_allow_html=True,
                    )
                    finalized[i] = True

        # Streaming done — finalize the last section
        sections = _split_by_h3(accumulated)
        for i, (title, body) in enumerate(sections):
            if i >= MAX_BRIEF_SECTIONS:
                break
            if not finalized[i]:
                slots[i].markdown(
                    _section_html(title, body, open=(i == 0)),
                    unsafe_allow_html=True,
                )

        # Save
        deal[cfg["section"]][cfg["field"]] = accumulated
        save_deal(deal)
        save_output(deal_name, "agent1_precall", accumulated)
        if cfg.get("post_save"):
            cfg["post_save"](deal_name, accumulated)

    except Exception as e:
        slots[0].error(f"Agent 1 failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1
# ═══════════════════════════════════════════════════════════════════════════════

with tab1:
    left, right = st.columns([1, 2])

    with left:
        st.subheader("Inputs")

        with st.form("phase1_form"):
            deal_name = st.text_input("Company Name *", placeholder="e.g. AGI7")
            founder_name = st.text_input("Founder Name *", placeholder="e.g. Song Cao")
            linkedin_url = st.text_input("LinkedIn URL *", placeholder="https://linkedin.com/in/...")
            website = st.text_input("Company Website", placeholder="https://...")
            deal_champion = st.text_input("Deal Champion", placeholder="e.g. Hongfei Xia")
            intro_source = st.text_input("Intro Source", placeholder="Who introduced the deal?")
            intro_context = st.text_area("Intro Context", placeholder="How did this deal come about?", height=68)
            initial_notes = st.text_area("Initial Notes", placeholder="Any preliminary notes...", height=68)
            input_files = st.file_uploader(
                "Supporting Documents (pitch deck, one-pager, etc.)",
                type=["pdf", "doc", "docx", "txt", "md"],
                accept_multiple_files=True,
            )

            submitted_p1 = st.form_submit_button(
                "\u25b6 Run Phase 1",
                type="primary",
                use_container_width=True,
            )

        if submitted_p1:
            if not deal_name or not founder_name or not linkedin_url:
                st.error("Company Name, Founder Name, and LinkedIn URL are required.")
            else:
                deal = load_deal(deal_name)
                deal["inputs"]["founder_name"] = founder_name
                deal["inputs"]["founder_linkedin"] = linkedin_url
                deal["inputs"]["company_website"] = website or ""
                deal["inputs"]["deal_champion"] = deal_champion or ""
                deal["inputs"]["intro_source"] = intro_source or ""
                deal["inputs"]["intro_context"] = intro_context or ""
                deal["inputs"]["initial_notes"] = initial_notes or ""

                # Extract text from all uploaded files
                if input_files:
                    input_dir = Path("inputs") / deal_name
                    input_dir.mkdir(parents=True, exist_ok=True)
                    deck_parts = []
                    file_names = []
                    for f in input_files:
                        fpath = input_dir / f.name
                        fpath.write_bytes(f.getvalue())
                        file_names.append(f.name)
                        text = extract_file_text(f.getvalue(), f.name)
                        if not text.startswith("[Unsupported"):
                            deck_parts.append(f"--- {f.name} ---\n{text}")
                    deal["_deck_text"] = "\n\n".join(deck_parts)
                    deal["inputs"]["pitch_deck_path"] = ", ".join(file_names)

                save_deal(deal)
                st.session_state.current_deal = deal_name
                st.session_state.active_stream = "agent1_precall"

        # Status indicator while Agent 1 streams in the right panel
        if st.session_state.current_deal:
            render_left_status()

    with right:
        st.subheader("Pre-Call Research Brief")
        current = st.session_state.current_deal
        if not current:
            st.info("Select an existing deal or create a new one.")
        elif st.session_state.get("active_stream") == "agent1_precall":
            # Stream full brief into per-section cards in real-time
            stream_sectioned_brief(current)
            st.session_state.active_stream = None
            st.rerun()
        elif "p1_rerun_idx" in st.session_state:
            # Re-run a single section
            rerun_idx = st.session_state.pop("p1_rerun_idx")
            output_text = read_output(current, "agent1_precall")
            if output_text:
                sections = _split_by_h3(output_text)
                if 0 <= rerun_idx < len(sections):
                    target_title = sections[rerun_idx][0]
                    deal = load_deal(current)

                    # Render all sections: static except the re-running one
                    slots = []
                    for i, (title, body) in enumerate(sections):
                        slot = st.empty()
                        slots.append(slot)
                        if i == rerun_idx:
                            slot.markdown(
                                _section_html(title, "", open=True, streaming=True),
                                unsafe_allow_html=True,
                            )
                        else:
                            slot.markdown(
                                _section_html(title, body, open=False),
                                unsafe_allow_html=True,
                            )

                    # Stream the new section content
                    try:
                        accumulated = ""
                        generator = stream_claude(
                            _SECTION_RERUN_SYSTEM,
                            _rerun_section_prompt(deal, output_text, target_title),
                            max_tokens=4000,
                            tools=AGENT1_TOOLS,
                        )
                        for chunk in generator:
                            accumulated += chunk
                            slots[rerun_idx].markdown(
                                _section_html(target_title, accumulated, open=True, streaming=True),
                                unsafe_allow_html=True,
                            )

                        # Finalize
                        slots[rerun_idx].markdown(
                            _section_html(target_title, accumulated, open=True),
                            unsafe_allow_html=True,
                        )

                        # Splice back and save
                        sections[rerun_idx] = (target_title, accumulated)
                        new_output = _rebuild_output(sections)
                        deal["pre_call"]["research_output"] = new_output
                        save_deal(deal)
                        save_output(current, "agent1_precall", new_output)
                        st.rerun()
                    except Exception as e:
                        slots[rerun_idx].error(f"Re-run failed: {e}")
        else:
            # Show completed output as sectioned cards with re-run buttons
            output_text = read_output(current, "agent1_precall")
            if output_text:
                render_sectioned_brief(output_text)
            else:
                st.info("No output yet. Fill in the inputs and run Phase 1.")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2
# ═══════════════════════════════════════════════════════════════════════════════

PHASE2_AGENTS = [
    ("agent2_diligence_mgmt", "Agent 2: Diligence Management"),
    ("agent3_founder_diligence", "Agent 3: Founder Diligence"),
    ("agent4_market_diligence", "Agent 4: Market Diligence"),
    ("agent5_reference_check", "Agent 5: Customer & Traction Intelligence"),
    ("agent6_thesis_check", "Agent 6: Thesis Check"),
]
PHASE2_KEYS = {k for k, _ in PHASE2_AGENTS}


with tab2:
    current = st.session_state.current_deal

    if not current:
        st.info("Select or create a deal first (run Phase 1).")
    else:
        left, right = st.columns([1, 2])
        deal = load_deal(current)
        has_notes = bool(deal.get("call_notes", {}).get("raw_transcript_or_notes", "").strip())

        with left:
            # ── Call Notes ───────────────────────────────────────────────────
            st.subheader("Call Notes")

            notes_method = st.radio(
                "Input method",
                ["Paste notes", "Upload file"],
                horizontal=True,
                key="notes_input_method",
            )

            with st.form("phase2_notes_form"):
                call_notes = ""
                notes_files = None
                if notes_method == "Paste notes":
                    call_notes = st.text_area(
                        "Call Notes",
                        height=200,
                        placeholder="Paste your call notes or transcript here...",
                        value=deal.get("call_notes", {}).get("raw_transcript_or_notes", ""),
                    )
                else:
                    notes_files = st.file_uploader(
                        "Upload Notes Files",
                        type=["txt", "md", "pdf", "doc", "docx"],
                        accept_multiple_files=True,
                    )

                annotations = st.text_area(
                    "Deal Champion Annotations (optional)",
                    placeholder="Your post-call observations...",
                    height=68,
                    value=deal.get("call_notes", {}).get("human_annotations", ""),
                )
                save_notes = st.form_submit_button("Save Notes", use_container_width=True)

            if save_notes:
                notes_content = call_notes
                if notes_files:
                    parts = []
                    for nf in notes_files:
                        text = extract_file_text(nf.getvalue(), nf.name)
                        if not text.startswith("[Unsupported"):
                            parts.append(f"--- {nf.name} ---\n{text}")
                    notes_content = "\n\n".join(parts)
                if notes_content.strip():
                    deal["call_notes"]["raw_transcript_or_notes"] = notes_content
                    if annotations:
                        deal["call_notes"]["human_annotations"] = annotations
                    deal["status"] = "diligence"
                    save_deal(deal)
                    st.success("Notes saved!")
                    st.rerun()
                else:
                    st.error("Notes cannot be empty.")

            if has_notes:
                st.caption("\u2705 Notes saved")
            else:
                st.caption("\u26a0\ufe0f Save notes before running agents")

            # ── Diligence Materials ──────────────────────────────────────────
            st.divider()
            st.subheader("Diligence Materials")
            st.caption("Upload decks, reports, contracts, or other materials shared by the company.")

            uploaded_files = st.file_uploader(
                "Upload files",
                type=["pdf", "txt", "md", "docx", "xlsx", "csv", "pptx"],
                accept_multiple_files=True,
                key="diligence_materials",
                label_visibility="collapsed",
            )

            if uploaded_files:
                materials_dir = Path("inputs") / current / "materials"
                materials_dir.mkdir(parents=True, exist_ok=True)
                saved_files = []
                for f in uploaded_files:
                    fpath = materials_dir / f.name
                    fpath.write_bytes(f.getvalue())
                    saved_files.append(f.name)

                # Extract text from uploaded files and store in deal
                materials_text = []
                for f in uploaded_files:
                    text = extract_file_text(f.getvalue(), f.name)
                    if not text.startswith("[Unsupported"):
                        materials_text.append(f"--- {f.name} ---\n{text}")

                if materials_text:
                    deal = load_deal(current)
                    deal["inputs"]["diligence_materials"] = "\n\n".join(materials_text)
                    save_deal(deal)

                st.success(f"Saved {len(saved_files)} file(s): {', '.join(saved_files)}")

            # Show existing materials
            materials_dir = Path("inputs") / current / "materials"
            if materials_dir.exists():
                existing = list(materials_dir.iterdir())
                if existing:
                    st.caption(f"{len(existing)} file(s) uploaded:")
                    for f in existing:
                        st.caption(f"  \u2022 {f.name}")

            # ── Run Agents ───────────────────────────────────────────────────
            st.divider()
            st.subheader("Run Agents")

            if agent_button("Agent 2: Diligence Management",
                           "IC update + diligence tracker. Run first.",
                           "run_a2", "agent2_diligence_mgmt", disabled=not has_notes):
                st.session_state.active_stream = "agent2_diligence_mgmt"

            st.divider()
            if agent_button("Agent 3: Founder Diligence",
                           "Company building, domain depth, leadership.",
                           "run_a3", "agent3_founder_diligence", disabled=not has_notes):
                st.session_state.active_stream = "agent3_founder_diligence"

            st.divider()
            if agent_button("Agent 4: Market Diligence",
                           "TAM/SAM/SOM, competitive landscape.",
                           "run_a4", "agent4_market_diligence", disabled=not has_notes):
                st.session_state.active_stream = "agent4_market_diligence"

            st.divider()
            if agent_button("Agent 5: Customer & Traction Intelligence",
                           "Traction analysis from materials + profiles to source.",
                           "run_a5", "agent5_reference_check", disabled=not has_notes):
                st.session_state.active_stream = "agent5_reference_check"

            st.divider()
            if agent_button("Agent 6: Thesis Check",
                           "JanCap thesis alignment, bias detection.",
                           "run_a6", "agent6_thesis_check", disabled=not has_notes):
                st.session_state.active_stream = "agent6_thesis_check"

            st.divider()
            if st.button("\u25b6 Run All Phase 2 Agents", use_container_width=True, disabled=not has_notes):
                queue = [k for k, _ in PHASE2_AGENTS]
                st.session_state.batch_queue = queue
                st.session_state.batch_total = len(queue)

            render_left_status()

        # ── Right Panel: Outputs ─────────────────────────────────────────────
        with right:
            st.subheader("Diligence Outputs")

            # Progress bar above cards (only during batch runs)
            progress_slot = st.empty()
            queue = st.session_state.get("batch_queue") or []
            phase2_batch = bool(queue) and queue[0] in PHASE2_KEYS
            if phase2_batch:
                total = st.session_state.batch_total or len(queue)
                done = total - len(queue)
                progress_slot.progress(
                    done / total if total else 0.0,
                    text=f"Running agents… {done}/{total}",
                )

            handles = render_cards_with_placeholders(
                current,
                PHASE2_AGENTS,
                read_output_fn=read_output,
            )

            # Single-agent stream (a button was just clicked)
            active = st.session_state.get("active_stream")
            if active in PHASE2_KEYS and active in handles:
                stream_into_card(handles, active, current)
                st.session_state.active_stream = None

            # Batch stream (Run All was just clicked)
            if phase2_batch:
                while st.session_state.batch_queue and st.session_state.batch_queue[0] in PHASE2_KEYS:
                    key = st.session_state.batch_queue[0]
                    if key in handles:
                        stream_into_card(handles, key, current)
                    st.session_state.batch_queue.pop(0)
                    total = st.session_state.batch_total
                    done = total - len(st.session_state.batch_queue)
                    if st.session_state.batch_queue:
                        progress_slot.progress(
                            done / total if total else 0.0,
                            text=f"Running agents… {done}/{total}",
                        )
                    else:
                        progress_slot.progress(1.0, text="Phase 2 complete")
                st.session_state.batch_total = 0


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3
# ═══════════════════════════════════════════════════════════════════════════════

PHASE3_DISPLAY = [
    ("agent9_ic_memo", "Agent 9: IC Memo"),
    ("agent8_ic_simulation", "Agent 8: IC Simulation"),
    ("agent7_premortem", "Agent 7: Pre-Mortem"),
]
PHASE3_RUN_ORDER = ["agent7_premortem", "agent8_ic_simulation", "agent9_ic_memo"]
PHASE3_KEYS = {k for k, _ in PHASE3_DISPLAY}


with tab3:
    current = st.session_state.current_deal

    if not current:
        st.info("Select or create a deal first (run Phase 1).")
    else:
        left, right = st.columns([1, 2])
        deal = load_deal(current)

        with left:
            st.subheader("Run Agents")

            if deal.get("status") not in ("post-diligence", "ic-prep", "complete"):
                st.warning("Phase 2 may not be complete.")

            if agent_button("Agent 7: Pre-Mortem",
                           "Failure scenarios with probability and evidence.",
                           "run_a7", "agent7_premortem"):
                st.session_state.active_stream = "agent7_premortem"

            st.divider()
            if agent_button("Agent 8: IC Simulation",
                           "4 IC personas evaluate the deal.",
                           "run_a8", "agent8_ic_simulation"):
                st.session_state.active_stream = "agent8_ic_simulation"

            st.divider()
            if agent_button("Agent 9: IC Memo",
                           "Final IC memo in January Capital format.",
                           "run_a9", "agent9_ic_memo"):
                st.session_state.active_stream = "agent9_ic_memo"

            st.divider()
            if st.button("\u25b6 Run All Phase 3 Agents", use_container_width=True):
                st.session_state.batch_queue = list(PHASE3_RUN_ORDER)
                st.session_state.batch_total = len(PHASE3_RUN_ORDER)

            render_left_status()

        # ── Right Panel: Outputs ─────────────────────────────────────────────
        with right:
            st.subheader("IC Preparation Outputs")

            progress_slot = st.empty()
            queue = st.session_state.get("batch_queue") or []
            phase3_batch = bool(queue) and queue[0] in PHASE3_KEYS
            if phase3_batch:
                total = st.session_state.batch_total or len(queue)
                done = total - len(queue)
                progress_slot.progress(
                    done / total if total else 0.0,
                    text=f"Running agents… {done}/{total}",
                )

            handles = render_cards_with_placeholders(
                current,
                PHASE3_DISPLAY,
                read_output_fn=read_output,
                initially_open_first=True,
                skip_confidence_keys=["agent9_ic_memo"],
            )

            active = st.session_state.get("active_stream")
            if active in PHASE3_KEYS and active in handles:
                stream_into_card(handles, active, current)
                st.session_state.active_stream = None

            if phase3_batch:
                while st.session_state.batch_queue and st.session_state.batch_queue[0] in PHASE3_KEYS:
                    key = st.session_state.batch_queue[0]
                    if key in handles:
                        stream_into_card(handles, key, current)
                    st.session_state.batch_queue.pop(0)
                    total = st.session_state.batch_total
                    done = total - len(st.session_state.batch_queue)
                    if st.session_state.batch_queue:
                        progress_slot.progress(
                            done / total if total else 0.0,
                            text=f"Running agents… {done}/{total}",
                        )
                    else:
                        progress_slot.progress(1.0, text="Phase 3 complete")
                st.session_state.batch_total = 0
