"""
app.py — Streamlit UI for Investment Analysis Pipeline
Run: streamlit run app.py
"""

import sys
import os
import streamlit as st
import concurrent.futures
from pathlib import Path
from datetime import datetime

# Inject Streamlit secrets into env vars BEFORE importing shared.py
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))

from shared import (
    load_deal, save_deal, save_output, read_pdf, call_claude, stream_claude,
    list_deals, read_output, parse_deal_mode, DEALS_DIR, OUTPUTS_DIR,
)
import re as _re


# ─── Confidence Tag Tooltips ─────────────────────────────────────────────────

TOOLTIP_CSS = """
<style>
.conf-tag {
    position: relative;
    display: inline-block;
    cursor: help;
    border-bottom: 1.5px dotted;
    font-size: 0.7em;
    font-weight: 600;
    letter-spacing: 0.02em;
    padding: 1px 5px;
    border-radius: 3px;
    vertical-align: middle;
    margin-left: 2px;
}
.conf-tag .conf-tip {
    visibility: hidden;
    opacity: 0;
    position: absolute;
    bottom: 125%;
    left: 50%;
    transform: translateX(-50%);
    background: #1a1a2e;
    color: #f0f0f0;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 400;
    letter-spacing: 0;
    white-space: nowrap;
    z-index: 999;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    transition: opacity 0.15s;
    pointer-events: none;
}
.conf-tag .conf-tip::after {
    content: "";
    position: absolute;
    top: 100%;
    left: 50%;
    margin-left: -5px;
    border-width: 5px;
    border-style: solid;
    border-color: #1a1a2e transparent transparent transparent;
}
.conf-tag:hover .conf-tip {
    visibility: visible;
    opacity: 1;
}
.conf-high { color: #0e8a16; border-color: #0e8a16; background: #e6f9e8; }
.conf-med  { color: #b08800; border-color: #b08800; background: #fff8e1; }
.conf-low  { color: #cf222e; border-color: #cf222e; background: #ffeef0; }
.conf-gap  { color: #6e40c9; border-color: #6e40c9; background: #f0e8ff; }
.conf-src  { color: #0969da; border-color: #0969da; background: #e8f0fe; }
</style>
"""

_CONF_PATTERNS = [
    (_re.compile(r'\[HIGH CONFIDENCE\]', _re.IGNORECASE),
     '<span class="conf-tag conf-high">HC<span class="conf-tip">HIGH CONFIDENCE</span></span>'),
    (_re.compile(r'\[MEDIUM CONFIDENCE\]', _re.IGNORECASE),
     '<span class="conf-tag conf-med">MC<span class="conf-tip">MEDIUM CONFIDENCE</span></span>'),
    (_re.compile(r'\[LOW CONFIDENCE\s*/?\s*INFERRED\]', _re.IGNORECASE),
     '<span class="conf-tag conf-low">LC<span class="conf-tip">LOW CONFIDENCE / INFERRED</span></span>'),
    (_re.compile(r'\[LOW CONFIDENCE\]', _re.IGNORECASE),
     '<span class="conf-tag conf-low">LC<span class="conf-tip">LOW CONFIDENCE</span></span>'),
    (_re.compile(r'\[INSUFFICIENT DATA[^]]*\]', _re.IGNORECASE),
     '<span class="conf-tag conf-gap">GAP<span class="conf-tip">INSUFFICIENT DATA \u2014 requires manual input</span></span>'),
    (_re.compile(r'\[(?:Source|Cited?|Ref):\s*([^\]]+)\]', _re.IGNORECASE),
     lambda m: f'<span class="conf-tag conf-src">src<span class="conf-tip">Source: {m.group(1).strip()}</span></span>'),
]


def render_md(text: str) -> None:
    """Render markdown with confidence tags converted to hover tooltips."""
    for pattern, replacement in _CONF_PATTERNS:
        text = pattern.sub(replacement, text)
    st.markdown(TOOLTIP_CSS + text, unsafe_allow_html=True)


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

# ─── Page Config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Investment Analysis",
    page_icon="\U0001f4ca",
    layout="wide",
    initial_sidebar_state="collapsed",
)

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

# ─── Top Bar: Deal Selector + Status ────────────────────────────────────────

top_col1, top_col2, top_col3 = st.columns([2, 6, 2])

with top_col1:
    st.markdown("#### \U0001f4ca Investment Analysis")

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
        status = deal_info.get("status", "pre-call")
        status_labels = {
            "pre-call": "\U0001f535 Pre-Call",
            "diligence": "\U0001f7e1 Diligence",
            "post-diligence": "\U0001f7e0 Post-Diligence",
            "complete": "\U0001f7e2 Complete",
        }
        st.markdown(f"**{status_labels.get(status, status)}**")
        if deal_info["inputs"].get("founder_name"):
            st.caption(deal_info["inputs"]["founder_name"])

st.divider()

# ─── Phase Tabs ──────────────────────────────────────────────────────────────

tab1, tab2, tab3 = st.tabs([
    "Phase 1: Pre-Call Research",
    "Phase 2: Post-Call Diligence",
    "Phase 3: IC Preparation",
])


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


def run_single_agent(
    current_deal: str,
    system_prompt: str,
    user_msg_fn,
    deal_section: str,
    deal_field: str,
    output_key: str,
    spinner_label: str = "Running agent...",
    success_label: str = "Done.",
    max_tokens: int = 8000,
    post_save_fn=None,
):
    """Run a single agent with streaming: load deal, stream response, save, rerun.

    post_save_fn: optional callable(deal, output) for custom logic after saving
                  (e.g. mode parsing, status updates). Should return success label
                  override or None.
    """
    deal = load_deal(current_deal)
    try:
        generator = stream_claude(system_prompt, user_msg_fn(deal), max_tokens=max_tokens)
        output = st.write_stream(generator)
        deal[deal_section][deal_field] = output
        save_deal(deal)
        save_output(current_deal, output_key, output)
        if post_save_fn:
            override = post_save_fn(deal, output)
            if override:
                success_label = override
        st.success(success_label)
        st.rerun()
    except Exception as e:
        st.error(f"Failed: {e}")


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
            intro_source = st.text_input("Intro Source", placeholder="Who introduced the deal?")
            intro_context = st.text_area("Intro Context", placeholder="How did this deal come about?", height=68)
            initial_notes = st.text_area("Initial Notes", placeholder="Any preliminary notes...", height=68)
            deck_file = st.file_uploader("Pitch Deck (PDF)", type=["pdf"])

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
                deal["inputs"]["intro_source"] = intro_source or ""
                deal["inputs"]["intro_context"] = intro_context or ""
                deal["inputs"]["initial_notes"] = initial_notes or ""
                if deck_file:
                    deck_path = Path("inputs") / deck_file.name
                    deck_path.parent.mkdir(exist_ok=True)
                    deck_path.write_bytes(deck_file.getvalue())
                    deal["inputs"]["pitch_deck_path"] = str(deck_path)
                save_deal(deal)
                st.session_state.current_deal = deal_name

                try:
                    generator = stream_claude(
                        AGENT1_SYSTEM, agent1_user(deal),
                        max_tokens=AGENT1_MAX_TOKENS, tools=AGENT1_TOOLS,
                    )
                    output = st.write_stream(generator)
                    deal["pre_call"]["research_output"] = output
                    save_deal(deal)
                    save_output(deal_name, "agent1_precall", output)
                    st.success("Phase 1 complete!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    with right:
        st.subheader("Pre-Call Research Brief")
        current = st.session_state.current_deal
        if current:
            output_text = read_output(current, "agent1_precall")
            if output_text:
                render_md(output_text)
            else:
                st.info("No output yet. Fill in the inputs and run Phase 1.")
        else:
            st.info("Select an existing deal or create a new one.")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2
# ═══════════════════════════════════════════════════════════════════════════════

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

            with st.form("phase2_notes_form"):
                notes_method = st.radio(
                    "Input method",
                    ["Paste notes", "Upload file"],
                    horizontal=True,
                )
                call_notes = ""
                notes_file = None
                if notes_method == "Paste notes":
                    call_notes = st.text_area(
                        "Call Notes",
                        height=200,
                        placeholder="Paste your call notes or transcript here...",
                        value=deal.get("call_notes", {}).get("raw_transcript_or_notes", ""),
                    )
                else:
                    notes_file = st.file_uploader("Upload Notes File", type=["txt", "md"])

                annotations = st.text_area(
                    "Deal Champion Annotations (optional)",
                    placeholder="Your post-call observations...",
                    height=68,
                    value=deal.get("call_notes", {}).get("human_annotations", ""),
                )
                save_notes = st.form_submit_button("Save Notes", use_container_width=True)

            if save_notes:
                notes_content = call_notes
                if notes_file:
                    notes_content = notes_file.getvalue().decode("utf-8")
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

                # Extract text from PDFs and store in deal
                materials_text = []
                for f in uploaded_files:
                    if f.name.lower().endswith(".pdf"):
                        fpath = materials_dir / f.name
                        text = read_pdf(str(fpath))
                        materials_text.append(f"--- {f.name} ---\n{text}")
                    elif f.name.lower().endswith((".txt", ".md", ".csv")):
                        materials_text.append(f"--- {f.name} ---\n{f.getvalue().decode('utf-8', errors='replace')}")

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
                           "Diligence tracker + deal mode. Run first.",
                           "run_a2", "agent2_diligence_mgmt", disabled=not has_notes):
                def _a2_post(deal, output):
                    mode = parse_deal_mode(output)
                    deal["diligence"]["deal_mode"] = mode
                    save_deal(deal)
                    return f"Done. Mode: {mode}"
                run_single_agent(current, AGENT2_SYSTEM, agent2_user,
                                 "diligence", "tracker", "agent2_diligence_mgmt",
                                 spinner_label="Running Agent 2...", post_save_fn=_a2_post)

            st.divider()
            if agent_button("Agent 3: Founder Diligence",
                           "Company building, domain depth, leadership.",
                           "run_a3", "agent3_founder_diligence", disabled=not has_notes):
                run_single_agent(current, AGENT3_SYSTEM, agent3_user,
                                 "diligence", "founder_diligence", "agent3_founder_diligence",
                                 spinner_label="Running Agent 3...")

            st.divider()
            if agent_button("Agent 4: Market Diligence",
                           "TAM/SAM/SOM, competitive landscape.",
                           "run_a4", "agent4_market_diligence", disabled=not has_notes):
                run_single_agent(current, AGENT4_SYSTEM, agent4_user,
                                 "diligence", "market_diligence", "agent4_market_diligence",
                                 spinner_label="Running Agent 4...")

            st.divider()
            if agent_button("Agent 5: Reference Check",
                           "Reference intelligence, negative signals.",
                           "run_a5", "agent5_reference_check", disabled=not has_notes):
                run_single_agent(current, AGENT5_SYSTEM, agent5_user,
                                 "diligence", "reference_check", "agent5_reference_check",
                                 spinner_label="Running Agent 5...")

            st.divider()
            if agent_button("Agent 6: Thesis Check",
                           "JanCap thesis alignment, bias detection.",
                           "run_a6", "agent6_thesis_check", disabled=not has_notes):
                def _a6_post(deal, output):
                    deal = load_deal(st.session_state.current_deal)
                    all_done = all(
                        isinstance(deal["diligence"].get(f), str) and deal["diligence"][f].strip()
                        for f in ("tracker", "founder_diligence", "market_diligence", "reference_check", "thesis_check")
                    )
                    if all_done:
                        deal["status"] = "post-diligence"
                        save_deal(deal)
                run_single_agent(current, AGENT6_SYSTEM, agent6_user,
                                 "diligence", "thesis_check", "agent6_thesis_check",
                                 spinner_label="Running Agent 6...", post_save_fn=_a6_post)

            st.divider()
            if st.button("\u25b6 Run All Phase 2 Agents", use_container_width=True, disabled=not has_notes):
                deal = load_deal(current)
                progress = st.progress(0, text="Agent 2: Diligence Management...")
                try:
                    output2 = call_claude(AGENT2_SYSTEM, agent2_user(deal))
                    mode = parse_deal_mode(output2)
                    deal["diligence"]["tracker"] = output2
                    deal["diligence"]["deal_mode"] = mode
                    save_deal(deal)
                    save_output(current, "agent2_diligence_mgmt", output2)
                    progress.progress(20, text=f"Agent 2 done (Mode: {mode}). Running 3-6...")

                    parallel_tasks = {
                        "agent3": (AGENT3_SYSTEM, agent3_user(deal), "founder_diligence", "agent3_founder_diligence"),
                        "agent4": (AGENT4_SYSTEM, agent4_user(deal), "market_diligence", "agent4_market_diligence"),
                        "agent5": (AGENT5_SYSTEM, agent5_user(deal), "reference_check", "agent5_reference_check"),
                        "agent6": (AGENT6_SYSTEM, agent6_user(deal), "thesis_check", "agent6_thesis_check"),
                    }

                    def _run(key):
                        system, user_msg, field, filename = parallel_tasks[key]
                        return key, field, filename, call_claude(system, user_msg)

                    results = {}
                    done = 0
                    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                        futures = {executor.submit(_run, k): k for k in parallel_tasks}
                        for future in concurrent.futures.as_completed(futures):
                            key = futures[future]
                            try:
                                _, field, filename, output = future.result()
                                results[key] = (field, filename, output)
                                done += 1
                                progress.progress(20 + done * 20, text=f"Agent {key[-1]} done ({done}/4)")
                            except Exception as e:
                                st.warning(f"Agent {key} failed: {e}")

                    # Write all results after threads complete — single save
                    for key, (field, filename, output) in results.items():
                        deal["diligence"][field] = output
                        save_output(current, filename, output)

                    deal["status"] = "post-diligence"
                    save_deal(deal)
                    progress.progress(100, text="All Phase 2 agents complete!")
                    st.success("Phase 2 complete!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

        # ── Right Panel: Outputs ─────────────────────────────────────────────
        with right:
            st.subheader("Diligence Outputs")
            agent_outputs = [
                ("agent2_diligence_mgmt", "Agent 2: Diligence Management"),
                ("agent3_founder_diligence", "Agent 3: Founder Diligence"),
                ("agent4_market_diligence", "Agent 4: Market Diligence"),
                ("agent5_reference_check", "Agent 5: Reference Check"),
                ("agent6_thesis_check", "Agent 6: Thesis Check"),
            ]
            has_any = any(read_output(current, key) for key, _ in agent_outputs)

            if has_any:
                for key, label in agent_outputs:
                    text = read_output(current, key)
                    if text:
                        with st.expander(label, expanded=False):
                            render_md(text)
            else:
                st.info("No outputs yet. Save notes and run agents from the left panel.")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3
# ═══════════════════════════════════════════════════════════════════════════════

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
                run_single_agent(current, AGENT7_SYSTEM, agent7_user,
                                 "ic_preparation", "pre_mortem", "agent7_premortem",
                                 spinner_label="Running Agent 7...")

            st.divider()
            if agent_button("Agent 8: IC Simulation",
                           "4 IC personas evaluate the deal.",
                           "run_a8", "agent8_ic_simulation"):
                run_single_agent(current, AGENT8_SYSTEM, agent8_user,
                                 "ic_preparation", "ic_simulation", "agent8_ic_simulation",
                                 spinner_label="Running Agent 8...")

            st.divider()
            if agent_button("Agent 9: IC Memo",
                           "Final IC memo in January Capital format.",
                           "run_a9", "agent9_ic_memo"):
                def _a9_post(deal, output):
                    deal["status"] = "complete"
                    save_deal(deal)
                run_single_agent(current, AGENT9_SYSTEM, agent9_user,
                                 "ic_preparation", "ic_memo", "agent9_ic_memo",
                                 spinner_label="Running Agent 9...",
                                 success_label="IC Memo ready!",
                                 max_tokens=12000, post_save_fn=_a9_post)

            st.divider()
            if st.button("\u25b6 Run All Phase 3 Agents", use_container_width=True):
                deal = load_deal(current)
                progress = st.progress(0, text="Agent 7: Pre-Mortem...")
                try:
                    a7_out = call_claude(AGENT7_SYSTEM, agent7_user(deal))
                    deal["ic_preparation"]["pre_mortem"] = a7_out
                    save_deal(deal)
                    save_output(current, "agent7_premortem", a7_out)
                    progress.progress(33, text="Agent 7 done. Running Agent 8...")

                    a8_out = call_claude(AGENT8_SYSTEM, agent8_user(deal))
                    deal["ic_preparation"]["ic_simulation"] = a8_out
                    save_deal(deal)
                    save_output(current, "agent8_ic_simulation", a8_out)
                    progress.progress(66, text="Agent 8 done. Running Agent 9...")

                    a9_out = call_claude(AGENT9_SYSTEM, agent9_user(deal), max_tokens=12000)
                    deal["ic_preparation"]["ic_memo"] = a9_out
                    deal["status"] = "complete"
                    save_deal(deal)
                    save_output(current, "agent9_ic_memo", a9_out)
                    progress.progress(100, text="Phase 3 complete!")
                    st.success("IC Memo ready!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

        # ── Right Panel: Outputs ─────────────────────────────────────────────
        with right:
            st.subheader("IC Preparation Outputs")
            agent_outputs = [
                ("agent9_ic_memo", "Agent 9: IC Memo", True),
                ("agent8_ic_simulation", "Agent 8: IC Simulation", False),
                ("agent7_premortem", "Agent 7: Pre-Mortem", False),
            ]
            has_any = any(read_output(current, key) for key, _, _ in agent_outputs)

            if has_any:
                for key, label, expanded in agent_outputs:
                    text = read_output(current, key)
                    if text:
                        with st.expander(label, expanded=expanded):
                            render_md(text)
            else:
                st.info("No outputs yet. Run agents from the left panel.")
