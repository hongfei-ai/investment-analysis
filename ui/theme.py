"""Dark professional theme: design tokens + injected CSS."""

import streamlit as st


COLORS = {
    "bg":          "#0d1117",
    "surface":     "#161b22",
    "surface_alt": "#1c2230",
    "border":      "#30363d",
    "border_soft": "#21262d",
    "text":        "#e6edf3",
    "text_muted":  "#8b949e",
    "text_dim":    "#484f58",
    "accent":      "#00d4aa",
    "hc":          "#3fb950",
    "mc":          "#d29922",
    "lc":          "#f85149",
    "gap":         "#a371f7",
    "src":         "#58a6ff",
}


AGENT_ACCENTS = {
    "agent1_precall":            "#00d4aa",
    "agent2_diligence_mgmt":     "#58a6ff",
    "agent3_founder_diligence":  "#00d4aa",
    "agent4_market_diligence":   "#3b82f6",
    "agent5_reference_check":    "#a371f7",
    "agent6_thesis_check":       "#d29922",
    "agent7_premortem":          "#f85149",
    "agent8_ic_simulation":      "#a371f7",
    "agent9_ic_memo":            "#00d4aa",
}


_CSS = f"""
<style>
:root {{
  --bg: {COLORS['bg']};
  --surface: {COLORS['surface']};
  --surface-alt: {COLORS['surface_alt']};
  --border: {COLORS['border']};
  --border-soft: {COLORS['border_soft']};
  --text: {COLORS['text']};
  --text-muted: {COLORS['text_muted']};
  --text-dim: {COLORS['text_dim']};
  --accent: {COLORS['accent']};
  --hc: {COLORS['hc']};
  --mc: {COLORS['mc']};
  --lc: {COLORS['lc']};
  --gap: {COLORS['gap']};
  --src: {COLORS['src']};
}}

/* Tighten top padding */
.block-container {{
  padding-top: 1.6rem;
  max-width: 1400px;
}}

/* Headings */
h1, h2, h3, h4, h5 {{
  color: var(--text) !important;
  letter-spacing: -0.01em;
}}

/* ─── Native widget polish ──────────────────────────────────────────── */

/* Buttons */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font-weight: 600;
  transition: background 0.12s, border-color 0.12s, transform 0.05s;
}}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {{
  border-color: var(--accent);
  background: var(--surface-alt);
  color: var(--text);
}}
.stButton > button:active {{ transform: translateY(1px); }}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
  background: var(--accent);
  color: var(--bg);
  border-color: var(--accent);
}}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {{
  background: #00b894;
  border-color: #00b894;
  color: var(--bg);
}}
.stButton > button:disabled {{
  opacity: 0.45;
  background: var(--border-soft);
  color: var(--text-dim);
  border-color: var(--border-soft);
}}

/* Inputs / textareas */
.stTextInput input, .stTextArea textarea, .stNumberInput input, .stDateInput input {{
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 6px !important;
  color: var(--text) !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {{
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 1px var(--accent) !important;
  outline: none !important;
}}
.stTextInput label, .stTextArea label, .stNumberInput label,
.stSelectbox label, .stRadio label, .stFileUploader label {{
  color: var(--text-muted) !important;
  font-size: 12px !important;
  font-weight: 500 !important;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}}

/* Selectbox */
.stSelectbox div[data-baseweb="select"] > div {{
  background: var(--surface) !important;
  border-color: var(--border) !important;
  border-radius: 6px !important;
}}

/* File uploader */
[data-testid="stFileUploader"] section {{
  background: var(--surface) !important;
  border: 1.5px dashed var(--border) !important;
  border-radius: 8px !important;
  padding: 14px !important;
}}
[data-testid="stFileUploader"] section:hover {{
  border-color: var(--accent) !important;
}}

/* Radio */
.stRadio > div {{
  background: transparent;
}}

/* Tabs */
button[data-baseweb="tab"] {{
  color: var(--text-muted) !important;
  font-weight: 500 !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
  color: var(--text) !important;
  font-weight: 700 !important;
}}
div[data-baseweb="tab-highlight"] {{
  background: var(--accent) !important;
  height: 2px !important;
}}
div[data-baseweb="tab-list"] {{
  border-bottom: 1px solid var(--border-soft) !important;
}}

/* Dividers */
hr, [data-testid="stDivider"] {{
  border-color: var(--border-soft) !important;
}}

/* Expander (legacy fallback) */
[data-testid="stExpander"] {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
}}

/* Progress bar */
.stProgress > div > div > div > div {{
  background: var(--accent) !important;
}}

/* Captions */
[data-testid="stCaptionContainer"], .stCaption, small {{
  color: var(--text-muted) !important;
}}

/* Alerts: keep dark-friendly */
[data-testid="stAlert"] {{
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
}}

/* ─── Confidence tags (carried from old render_md, restyled) ───────── */
.conf-tag {{
  display: inline-block;
  font-size: 0.68em;
  font-weight: 700;
  letter-spacing: 0.03em;
  padding: 1px 6px;
  border-radius: 4px;
  vertical-align: middle;
  margin: 0 1px;
  cursor: help;
  position: relative;
}}
.conf-hc  {{ color: var(--hc);  background: rgba(63,185,80,0.15); }}
.conf-mc  {{ color: var(--mc);  background: rgba(210,153,34,0.15); }}
.conf-lc  {{ color: var(--lc);  background: rgba(248,81,73,0.15); }}
.conf-gap {{ color: var(--gap); background: rgba(163,113,247,0.15); }}
.conf-src {{ color: var(--src); background: rgba(88,166,255,0.15); }}
.conf-tag .conf-tip {{
  visibility: hidden;
  opacity: 0;
  position: absolute;
  bottom: 130%;
  left: 50%;
  transform: translateX(-50%);
  background: var(--surface-alt);
  color: var(--text);
  padding: 5px 9px;
  border-radius: 5px;
  border: 1px solid var(--border);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0;
  white-space: nowrap;
  z-index: 1000;
  transition: opacity 0.12s;
  pointer-events: none;
}}
.conf-tag:hover .conf-tip {{ visibility: visible; opacity: 1; }}

/* ─── Stepper ──────────────────────────────────────────────────────── */
.stepper {{
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 12px 0 18px;
}}
.stepper-node {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}}
.stepper-circle {{
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  border: 2px solid var(--border);
  background: transparent;
  color: var(--text-dim);
}}
.stepper-circle.done {{
  background: var(--accent);
  color: var(--bg);
  border-color: var(--accent);
}}
.stepper-circle.active {{
  border-color: var(--accent);
  color: var(--accent);
  box-shadow: 0 0 10px rgba(0,212,170,0.35);
}}
.stepper-label {{
  font-size: 11px;
  font-weight: 600;
  color: var(--text-dim);
}}
.stepper-label.on {{ color: var(--accent); }}
.stepper-sub {{ font-size: 10px; color: var(--text-muted); }}
.stepper-bar {{
  width: 80px;
  height: 2px;
  background: var(--border);
  margin: 0 6px 18px;
}}
.stepper-bar.done {{ background: var(--accent); }}

/* ─── Stacked agent cards ──────────────────────────────────────────── */
.agent-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--border);
  border-radius: 8px;
  margin-bottom: 10px;
  overflow: hidden;
}}
.agent-card.empty {{ opacity: 0.5; }}
.agent-card-head {{
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}}
.agent-card-title {{
  font-weight: 600;
  font-size: 14px;
  color: var(--text);
}}
.agent-card-tally {{
  display: flex;
  align-items: center;
  gap: 6px;
}}
.tally {{
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 3px;
  letter-spacing: 0.03em;
}}
.tally-hc  {{ color: var(--hc);  background: rgba(63,185,80,0.15); }}
.tally-mc  {{ color: var(--mc);  background: rgba(210,153,34,0.15); }}
.tally-lc  {{ color: var(--lc);  background: rgba(248,81,73,0.15); }}
.tally-gap {{ color: var(--gap); background: rgba(163,113,247,0.15); }}
.empty-pill {{
  font-size: 11px;
  color: var(--text-dim);
  background: var(--border-soft);
  padding: 2px 8px;
  border-radius: 3px;
}}
.exec-summary {{
  margin: 0 16px 14px;
  background: rgba(0,212,170,0.06);
  border: 1px solid rgba(0,212,170,0.20);
  border-radius: 6px;
  padding: 12px 14px;
}}
.exec-summary-label {{
  font-size: 10px;
  color: var(--accent);
  font-weight: 700;
  letter-spacing: 0.06em;
  margin-bottom: 5px;
}}
.exec-summary-body {{
  font-size: 13px;
  color: #c9d1d9;
  line-height: 1.6;
}}
details.section {{
  margin: 0 16px 8px;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  overflow: hidden;
}}
details.section[open] > summary {{
  background: rgba(255,255,255,0.02);
  border-bottom: 1px solid var(--border-soft);
}}
details.section > summary {{
  padding: 10px 14px;
  cursor: pointer;
  font-weight: 600;
  font-size: 13px;
  color: var(--text);
  list-style: none;
  display: flex;
  align-items: center;
  gap: 8px;
}}
details.section > summary::-webkit-details-marker {{ display: none; }}
details.section > summary::before {{
  content: "▶";
  font-size: 9px;
  color: var(--text-muted);
  transition: transform 0.15s;
}}
details.section[open] > summary::before {{ transform: rotate(90deg); }}
.section-body {{
  padding: 12px 14px;
  font-size: 13px;
  color: #c9d1d9;
  line-height: 1.65;
}}
.section-body h3 {{
  font-size: 13px !important;
  font-weight: 700;
  color: var(--text) !important;
  margin: 14px 0 6px !important;
}}
.section-body h4 {{
  font-size: 12px !important;
  font-weight: 600;
  color: var(--text-muted) !important;
  margin: 10px 0 4px !important;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}}
.section-body p {{ margin: 0 0 8px; }}
.section-body ul, .section-body ol {{ margin: 4px 0 8px; padding-left: 22px; }}
.section-body li {{ margin-bottom: 3px; }}
.section-body table {{
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
  font-size: 12px;
}}
.section-body th, .section-body td {{
  padding: 6px 10px;
  border: 1px solid var(--border-soft);
  text-align: left;
}}
.section-body th {{
  background: var(--surface-alt);
  font-weight: 600;
  color: var(--text);
}}
.section-body code {{
  background: var(--surface-alt);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 0.92em;
}}
.section-body blockquote {{
  border-left: 3px solid var(--accent);
  margin: 8px 0;
  padding: 4px 12px;
  color: var(--text-muted);
}}
</style>
"""


def inject_theme() -> None:
    """Inject the dark theme CSS. Call once near the top of the app."""
    st.markdown(_CSS, unsafe_allow_html=True)
