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
    secrets_keys = list(st.secrets.keys()) if hasattr(st, 'secrets') else []
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    else:
        # Debug: show what secrets are available (remove after fixing)
        st.error(f"ANTHROPIC_API_KEY not found in Streamlit secrets. Available keys: {secrets_keys}")
except FileNotFoundError:
    # No secrets file — running locally with .env
    pass
except Exception as e:
    st.warning(f"Secrets loading note: {type(e).__name__}: {e}")

sys.path.insert(0, str(Path(__file__).parent))

from shared import (
    load_deal, save_deal, save_output, read_pdf, call_claude,
    list_deals, read_output, DEALS_DIR, OUTPUTS_DIR,
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
     '<span class="conf-tag conf-gap">GAP<span class="conf-tip">INSUFFICIENT DATA — requires manual input</span></span>'),

    # Source citations like [Source: URL] or [Source: document name]
    (_re.compile(r'\[(?:Source|Cited?|Ref):\s*([^\]]+)\]', _re.IGNORECASE),
     lambda m: f'<span class="conf-tag conf-src">src<span class="conf-tip">Source: {m.group(1).strip()}</span></span>'),
]


def render_md(text: str) -> None:
    """Render markdown with confidence tags converted to hover tooltips."""
    for pattern, replacement in _CONF_PATTERNS:
        text = pattern.sub(replacement, text)
    st.markdown(TOOLTIP_CSS + text, unsafe_allow_html=True)


# ─── Notion Fetcher ──────────────────────────────────────────────────────────

def _extract_notion_page_id(url: str) -> str | None:
    """Extract page ID from a Notion URL."""
    # Matches patterns like: notion.so/workspace/Title-<32hex> or notion.so/<32hex>
    match = _re.search(r'([a-f0-9]{32})', url.replace("-", ""))
    if match:
        raw = match.group(1)
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    return None


def _fetch_notion_blocks_text(notion_client, block_id: str, depth: int = 0) -> str:
    """Recursively fetch all block text content from a Notion page."""
    lines = []
    cursor = None
    while True:
        kwargs = {"block_id": block_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion_client.blocks.children.list(**kwargs)
        for block in resp["results"]:
            btype = block.get("type", "")
            bdata = block.get(btype, {})

            # Extract rich_text content
            text_parts = []
            for rt_field in ("rich_text", "text"):
                for rt in bdata.get(rt_field, []):
                    text_parts.append(rt.get("plain_text", ""))
            text = "".join(text_parts)

            # Format based on block type
            prefix = ""
            if btype.startswith("heading_1"):
                prefix = "# "
            elif btype.startswith("heading_2"):
                prefix = "## "
            elif btype.startswith("heading_3"):
                prefix = "### "
            elif btype == "bulleted_list_item":
                prefix = "- "
            elif btype == "numbered_list_item":
                prefix = "1. "
            elif btype == "to_do":
                checked = bdata.get("checked", False)
                prefix = "[x] " if checked else "[ ] "
            elif btype == "toggle":
                prefix = "> "
            elif btype == "callout":
                prefix = "> "
            elif btype == "quote":
                prefix = "> "
            elif btype == "divider":
                lines.append("---")
                continue
            elif btype == "child_page":
                title = bdata.get("title", "")
                lines.append(f"\n### {title}\n")
                continue

            if text:
                lines.append(f"{'  ' * depth}{prefix}{text}")

            # Recurse into children
            if block.get("has_children"):
                child_text = _fetch_notion_blocks_text(notion_client, block["id"], depth + 1)
                if child_text:
                    lines.append(child_text)

        cursor = resp.get("next_cursor")
        if not cursor:
            break

    return "\n".join(lines)


def fetch_notion_page(notion_token: str, page_url: str) -> str:
    """Fetch a Notion page's content as plain text."""
    from notion_client import Client

    page_id = _extract_notion_page_id(page_url)
    if not page_id:
        raise ValueError(f"Could not extract page ID from URL: {page_url}")

    client = Client(auth=notion_token)

    # Get page title
    page = client.pages.retrieve(page_id=page_id)
    title = ""
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            for rt in prop.get("title", []):
                title += rt.get("plain_text", "")

    # Get page content
    content = _fetch_notion_blocks_text(client, page_id)

    return f"# {title}\n\n{content}" if title else content
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

# ─── Page Config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Investment Analysis",
    page_icon="📊",
    layout="wide",
)

# ─── Authentication ──────────────────────────────────────────────────────────

def check_password() -> bool:
    """Gate access with a password. Reads from st.secrets or skips if not set."""
    # Skip auth if no password configured (local dev)
    try:
        correct_pw = st.secrets["app_password"]
    except (KeyError, FileNotFoundError):
        return True

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("📊 Investment Analysis")
    st.caption("January Capital — Internal Tool")
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
if "running" not in st.session_state:
    st.session_state.running = False
if "notion_token" not in st.session_state:
    st.session_state.notion_token = ""

# ─── Sidebar: Deal Selector ─────────────────────────────────────────────────

with st.sidebar:
    st.title("📊 Investment Analysis")
    st.divider()

    existing_deals = list_deals()

    st.subheader("Select Deal")
    deal_options = ["-- New Deal --"] + existing_deals
    selected = st.selectbox(
        "Deal",
        deal_options,
        index=0 if not st.session_state.current_deal else
              (deal_options.index(st.session_state.current_deal)
               if st.session_state.current_deal in deal_options else 0),
        label_visibility="collapsed",
    )

    if selected != "-- New Deal --":
        st.session_state.current_deal = selected
        deal = load_deal(selected)
        st.divider()
        st.subheader("Deal Status")
        status = deal.get("status", "pre-call")
        status_map = {
            "pre-call": ("1/4", "Pre-Call"),
            "diligence": ("2/4", "Diligence"),
            "post-diligence": ("3/4", "Post-Diligence"),
            "complete": ("4/4", "Complete"),
        }
        frac, label = status_map.get(status, ("?", status))
        st.progress(int(frac.split("/")[0]) / int(frac.split("/")[1]))
        st.caption(f"Status: **{label}**")

        # Show deal metadata
        st.divider()
        st.caption(f"Created: {deal.get('date_created', 'N/A')[:10]}")
        if deal["inputs"].get("founder_name"):
            st.caption(f"Founder: {deal['inputs']['founder_name']}")

    st.divider()
    st.subheader("Settings")
    notion_token = st.text_input(
        "Notion API Token",
        type="password",
        placeholder="ntn_...",
        help="Required for fetching notes from Notion. Get one at https://www.notion.so/my-integrations",
    )
    if notion_token:
        st.session_state.notion_token = notion_token

# ─── Main Content ────────────────────────────────────────────────────────────

tab1, tab2, tab3 = st.tabs([
    "Phase 1: Pre-Call Research",
    "Phase 2: Post-Call Diligence",
    "Phase 3: IC Preparation",
])

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1
# ═══════════════════════════════════════════════════════════════════════════════

with tab1:
    st.header("Phase 1: Pre-Call Research")
    st.caption("Generate a research brief before your founder call.")

    with st.form("phase1_form"):
        col1, col2 = st.columns(2)
        with col1:
            deal_name = st.text_input("Company Name *", placeholder="e.g. AGI7")
            founder_name = st.text_input("Founder Name *", placeholder="e.g. Song Cao")
            linkedin_url = st.text_input("LinkedIn URL *", placeholder="https://linkedin.com/in/...")
            website = st.text_input("Company Website", placeholder="https://...")
        with col2:
            intro_source = st.text_input("Intro Source", placeholder="Who introduced the deal?")
            intro_context = st.text_area("Intro Context", placeholder="How did this deal come about?", height=68)
            initial_notes = st.text_area("Initial Notes", placeholder="Any preliminary notes...", height=68)

        deck_file = st.file_uploader("Pitch Deck (PDF)", type=["pdf"])

        submitted_p1 = st.form_submit_button(
            "Run Phase 1",
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

            # Handle PDF upload
            if deck_file:
                deck_path = Path("inputs") / deck_file.name
                deck_path.parent.mkdir(exist_ok=True)
                deck_path.write_bytes(deck_file.getvalue())
                deal["inputs"]["pitch_deck_path"] = str(deck_path)

            save_deal(deal)
            st.session_state.current_deal = deal_name

            with st.spinner("Running Agent 1: Pre-Call Research... (this may take a minute)"):
                try:
                    output = call_claude(AGENT1_SYSTEM, agent1_user(deal))
                    deal["pre_call"]["research_output"] = output
                    save_deal(deal)
                    save_output(deal_name, "agent1_precall", output)
                    st.success("Phase 1 complete!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # Show existing output
    current = st.session_state.current_deal
    if current:
        output_text = read_output(current, "agent1_precall")
        if output_text:
            st.divider()
            st.subheader("Pre-Call Research Brief")
            render_md(output_text)

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2
# ═══════════════════════════════════════════════════════════════════════════════

with tab2:
    st.header("Phase 2: Post-Call Diligence")
    st.caption("Run diligence agents after your founder call. Save notes first, then run agents individually.")

    current = st.session_state.current_deal
    if not current:
        st.info("Select or create a deal first (run Phase 1).")
    else:
        deal = load_deal(current)
        has_notes = bool(deal.get("call_notes", {}).get("raw_transcript_or_notes", "").strip())

        # ── Step 1: Save Call Notes ──────────────────────────────────────────
        st.subheader("Step 1: Call Notes")

        with st.form("phase2_notes_form"):
            notes_method = st.radio(
                "Call Notes Input",
                ["Paste notes", "Upload file"],
                horizontal=True,
            )
            call_notes = ""
            notes_file = None
            if notes_method == "Paste notes":
                call_notes = st.text_area(
                    "Call Notes",
                    height=250,
                    placeholder="Paste your call notes or transcript here...",
                    value=deal.get("call_notes", {}).get("raw_transcript_or_notes", ""),
                )
            else:
                notes_file = st.file_uploader("Upload Notes File", type=["txt", "md"])

            annotations = st.text_area(
                "Deal Champion Annotations (optional)",
                placeholder="Your post-call observations, gut feelings, key signals...",
                height=80,
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
            st.caption("Notes saved. You can now run the agents below.")
        else:
            st.info("Save call notes above before running agents.")

        st.divider()

        # ── Step 2: Individual Agent Buttons ─────────────────────────────────
        st.subheader("Step 2: Run Agents")

        # Agent 2: Diligence Management
        a2_col1, a2_col2 = st.columns([3, 1])
        with a2_col1:
            st.markdown("**Agent 2: Diligence Management**")
            st.caption("Produces diligence tracker and deal mode classification. Run this first.")
        with a2_col2:
            a2_exists = read_output(current, "agent2_diligence_mgmt") is not None
            a2_label = "Re-run" if a2_exists else "Run"
            run_a2 = st.button(
                a2_label, key="run_a2", type="primary",
                use_container_width=True, disabled=not has_notes,
            )
        if run_a2:
            deal = load_deal(current)
            with st.spinner("Running Agent 2: Diligence Management..."):
                try:
                    output = call_claude(AGENT2_SYSTEM, agent2_user(deal))
                    mode = "A"
                    lower = output.lower()
                    if "mode b" in lower and "mode a" in lower:
                        mode = "A+B"
                    elif "mode b" in lower:
                        mode = "B"
                    deal["diligence"]["tracker"] = output
                    deal["diligence"]["deal_mode"] = mode
                    save_deal(deal)
                    save_output(current, "agent2_diligence_mgmt", output)
                    st.success(f"Agent 2 complete. Deal Mode: {mode}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Agent 2 failed: {e}")

        # Agent 3: Founder Diligence
        st.divider()
        a3_col1, a3_col2 = st.columns([3, 1])
        with a3_col1:
            st.markdown("**Agent 3: Founder Diligence**")
            st.caption("Deep dive on founder's company building ability, domain depth, leadership.")
        with a3_col2:
            a3_exists = read_output(current, "agent3_founder_diligence") is not None
            a3_label = "Re-run" if a3_exists else "Run"
            run_a3 = st.button(
                a3_label, key="run_a3", type="primary",
                use_container_width=True, disabled=not has_notes,
            )
        if run_a3:
            deal = load_deal(current)
            with st.spinner("Running Agent 3: Founder Diligence..."):
                try:
                    output = call_claude(AGENT3_SYSTEM, agent3_user(deal))
                    deal["diligence"]["founder_diligence"] = output
                    save_deal(deal)
                    save_output(current, "agent3_founder_diligence", output)
                    st.success("Agent 3 complete.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Agent 3 failed: {e}")

        # Agent 4: Market Diligence
        st.divider()
        a4_col1, a4_col2 = st.columns([3, 1])
        with a4_col1:
            st.markdown("**Agent 4: Market Diligence**")
            st.caption("TAM/SAM/SOM analysis, competitive landscape, market timing.")
        with a4_col2:
            a4_exists = read_output(current, "agent4_market_diligence") is not None
            a4_label = "Re-run" if a4_exists else "Run"
            run_a4 = st.button(
                a4_label, key="run_a4", type="primary",
                use_container_width=True, disabled=not has_notes,
            )
        if run_a4:
            deal = load_deal(current)
            with st.spinner("Running Agent 4: Market Diligence..."):
                try:
                    output = call_claude(AGENT4_SYSTEM, agent4_user(deal))
                    deal["diligence"]["market_diligence"] = output
                    save_deal(deal)
                    save_output(current, "agent4_market_diligence", output)
                    st.success("Agent 4 complete.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Agent 4 failed: {e}")

        # Agent 5: Reference Check
        st.divider()
        a5_col1, a5_col2 = st.columns([3, 1])
        with a5_col1:
            st.markdown("**Agent 5: Reference Check**")
            st.caption("Reference intelligence, employee retention signals, negative signal detection.")
        with a5_col2:
            a5_exists = read_output(current, "agent5_reference_check") is not None
            a5_label = "Re-run" if a5_exists else "Run"
            run_a5 = st.button(
                a5_label, key="run_a5", type="primary",
                use_container_width=True, disabled=not has_notes,
            )
        if run_a5:
            deal = load_deal(current)
            with st.spinner("Running Agent 5: Reference Check..."):
                try:
                    output = call_claude(AGENT5_SYSTEM, agent5_user(deal))
                    deal["diligence"]["reference_check"] = output
                    save_deal(deal)
                    save_output(current, "agent5_reference_check", output)
                    st.success("Agent 5 complete.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Agent 5 failed: {e}")

        # Agent 6: Thesis Check
        st.divider()
        a6_col1, a6_col2 = st.columns([3, 1])
        with a6_col1:
            st.markdown("**Agent 6: Thesis Check**")
            st.caption("Alignment with January Capital thesis, bias detection.")
        with a6_col2:
            a6_exists = read_output(current, "agent6_thesis_check") is not None
            a6_label = "Re-run" if a6_exists else "Run"
            run_a6 = st.button(
                a6_label, key="run_a6", type="primary",
                use_container_width=True, disabled=not has_notes,
            )
        if run_a6:
            deal = load_deal(current)
            with st.spinner("Running Agent 6: Thesis Check..."):
                try:
                    output = call_claude(AGENT6_SYSTEM, agent6_user(deal))
                    deal["diligence"]["thesis_check"] = output
                    save_deal(deal)
                    save_output(current, "agent6_thesis_check", output)
                    st.success("Agent 6 complete.")
                    # Update status if all agents done
                    deal = load_deal(current)
                    all_done = all(
                        isinstance(deal["diligence"].get(f), str) and deal["diligence"][f].strip()
                        for f in ("tracker", "founder_diligence", "market_diligence", "reference_check", "thesis_check")
                    )
                    if all_done:
                        deal["status"] = "post-diligence"
                        save_deal(deal)
                    st.rerun()
                except Exception as e:
                    st.error(f"Agent 6 failed: {e}")

        # ── Run All Button ───────────────────────────────────────────────────
        st.divider()
        if st.button("Run All Phase 2 Agents", use_container_width=True, disabled=not has_notes):
            deal = load_deal(current)
            progress = st.progress(0, text="Running Agent 2: Diligence Management...")
            try:
                # Agent 2 first
                output2 = call_claude(AGENT2_SYSTEM, agent2_user(deal))
                mode = "A"
                lower = output2.lower()
                if "mode b" in lower and "mode a" in lower:
                    mode = "A+B"
                elif "mode b" in lower:
                    mode = "B"
                deal["diligence"]["tracker"] = output2
                deal["diligence"]["deal_mode"] = mode
                save_deal(deal)
                save_output(current, "agent2_diligence_mgmt", output2)
                progress.progress(20, text=f"Agent 2 complete (Mode: {mode}). Running Agents 3-6...")

                # Agents 3-6 in parallel
                parallel_tasks = {
                    "agent3": (AGENT3_SYSTEM, agent3_user(deal), "founder_diligence", "agent3_founder_diligence"),
                    "agent4": (AGENT4_SYSTEM, agent4_user(deal), "market_diligence", "agent4_market_diligence"),
                    "agent5": (AGENT5_SYSTEM, agent5_user(deal), "reference_check", "agent5_reference_check"),
                    "agent6": (AGENT6_SYSTEM, agent6_user(deal), "thesis_check", "agent6_thesis_check"),
                }

                def _run(key):
                    system, user_msg, field, filename = parallel_tasks[key]
                    return key, field, filename, call_claude(system, user_msg)

                done = 0
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {executor.submit(_run, k): k for k in parallel_tasks}
                    for future in concurrent.futures.as_completed(futures):
                        key = futures[future]
                        try:
                            _, field, filename, output = future.result()
                            deal["diligence"][field] = output
                            save_output(current, filename, output)
                            done += 1
                            progress.progress(20 + done * 20, text=f"Agent {key[-1]} complete ({done}/4)")
                        except Exception as e:
                            st.warning(f"Agent {key} failed: {e}")

                deal["status"] = "post-diligence"
                save_deal(deal)
                progress.progress(100, text="All Phase 2 agents complete!")
                st.success("Phase 2 complete!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

        # ── Show Existing Outputs ────────────────────────────────────────────
        if current:
            agent_outputs = [
                ("agent2_diligence_mgmt", "Agent 2: Diligence Management"),
                ("agent3_founder_diligence", "Agent 3: Founder Diligence"),
                ("agent4_market_diligence", "Agent 4: Market Diligence"),
                ("agent5_reference_check", "Agent 5: Reference Check"),
                ("agent6_thesis_check", "Agent 6: Thesis Check"),
            ]
            has_any = any(read_output(current, key) for key, _ in agent_outputs)

            if has_any:
                st.divider()
                st.subheader("Diligence Outputs")
                for key, label in agent_outputs:
                    text = read_output(current, key)
                    if text:
                        with st.expander(label, expanded=False):
                            render_md(text)

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3
# ═══════════════════════════════════════════════════════════════════════════════

with tab3:
    st.header("Phase 3: IC Preparation")
    st.caption("Generate Pre-Mortem, IC Simulation, and final IC Memo. Run agents sequentially or individually.")

    current = st.session_state.current_deal
    if not current:
        st.info("Select or create a deal first (run Phase 1).")
    else:
        deal = load_deal(current)

        if deal.get("status") not in ("post-diligence", "ic-prep", "complete"):
            st.warning("Phase 2 may not be complete. Some inputs may be missing.")

        # Agent 7: Pre-Mortem
        a7_col1, a7_col2 = st.columns([3, 1])
        with a7_col1:
            st.markdown("**Agent 7: Pre-Mortem / Devil's Advocate**")
            st.caption("Articulates failure scenarios with probability and evidence.")
        with a7_col2:
            a7_exists = read_output(current, "agent7_premortem") is not None
            a7_label = "Re-run" if a7_exists else "Run"
            run_a7 = st.button(a7_label, key="run_a7", type="primary", use_container_width=True)
        if run_a7:
            deal = load_deal(current)
            with st.spinner("Running Agent 7: Pre-Mortem..."):
                try:
                    output = call_claude(AGENT7_SYSTEM, agent7_user(deal))
                    deal["ic_preparation"]["pre_mortem"] = output
                    save_deal(deal)
                    save_output(current, "agent7_premortem", output)
                    st.success("Agent 7 complete.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Agent 7 failed: {e}")

        # Agent 8: IC Simulation
        st.divider()
        a8_col1, a8_col2 = st.columns([3, 1])
        with a8_col1:
            st.markdown("**Agent 8: IC Simulation**")
            st.caption("Simulates 4 IC personas scoring the deal across 10 dimensions.")
        with a8_col2:
            a8_exists = read_output(current, "agent8_ic_simulation") is not None
            a8_label = "Re-run" if a8_exists else "Run"
            run_a8 = st.button(a8_label, key="run_a8", type="primary", use_container_width=True)
        if run_a8:
            deal = load_deal(current)
            with st.spinner("Running Agent 8: IC Simulation..."):
                try:
                    output = call_claude(AGENT8_SYSTEM, agent8_user(deal))
                    deal["ic_preparation"]["ic_simulation"] = output
                    save_deal(deal)
                    save_output(current, "agent8_ic_simulation", output)
                    st.success("Agent 8 complete.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Agent 8 failed: {e}")

        # Agent 9: IC Memo
        st.divider()
        a9_col1, a9_col2 = st.columns([3, 1])
        with a9_col1:
            st.markdown("**Agent 9: IC Memo**")
            st.caption("Final 8-12 page Investment Committee memo synthesizing all prior outputs.")
        with a9_col2:
            a9_exists = read_output(current, "agent9_ic_memo") is not None
            a9_label = "Re-run" if a9_exists else "Run"
            run_a9 = st.button(a9_label, key="run_a9", type="primary", use_container_width=True)
        if run_a9:
            deal = load_deal(current)
            with st.spinner("Running Agent 9: IC Memo..."):
                try:
                    output = call_claude(AGENT9_SYSTEM, agent9_user(deal), max_tokens=12000)
                    deal["ic_preparation"]["ic_memo"] = output
                    deal["status"] = "complete"
                    save_deal(deal)
                    save_output(current, "agent9_ic_memo", output)
                    st.success("Agent 9 complete. IC Memo is ready!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Agent 9 failed: {e}")

        # ── Run All Button ───────────────────────────────────────────────────
        st.divider()
        if st.button("Run All Phase 3 Agents", use_container_width=True):
            deal = load_deal(current)
            progress = st.progress(0, text="Running Agent 7: Pre-Mortem...")
            try:
                a7_out = call_claude(AGENT7_SYSTEM, agent7_user(deal))
                deal["ic_preparation"]["pre_mortem"] = a7_out
                save_deal(deal)
                save_output(current, "agent7_premortem", a7_out)
                progress.progress(33, text="Agent 7 complete. Running Agent 8...")

                a8_out = call_claude(AGENT8_SYSTEM, agent8_user(deal))
                deal["ic_preparation"]["ic_simulation"] = a8_out
                save_deal(deal)
                save_output(current, "agent8_ic_simulation", a8_out)
                progress.progress(66, text="Agent 8 complete. Running Agent 9...")

                a9_out = call_claude(AGENT9_SYSTEM, agent9_user(deal), max_tokens=12000)
                deal["ic_preparation"]["ic_memo"] = a9_out
                deal["status"] = "complete"
                save_deal(deal)
                save_output(current, "agent9_ic_memo", a9_out)
                progress.progress(100, text="Phase 3 complete!")

                st.success("All Phase 3 agents complete! IC Memo is ready.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

        # ── Show Existing Outputs ────────────────────────────────────────────
        if current:
            agent_outputs = [
                ("agent9_ic_memo", "Agent 9: IC Memo", True),
                ("agent8_ic_simulation", "Agent 8: IC Simulation", False),
                ("agent7_premortem", "Agent 7: Pre-Mortem / Devil's Advocate", False),
            ]
            has_any = any(read_output(current, key) for key, _, _ in agent_outputs)

            if has_any:
                st.divider()
                st.subheader("IC Preparation Outputs")
                for key, label, expanded in agent_outputs:
                    text = read_output(current, key)
                    if text:
                        with st.expander(label, expanded=expanded):
                            render_md(text)
