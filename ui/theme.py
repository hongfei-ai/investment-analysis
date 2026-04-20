"""Light + dark theme: design tokens and injected CSS with a runtime toggle.

Default theme is "light" (editorial-VC palette inspired by january.capital).
Call `inject_theme()` once at the top of each page. Call `render_theme_toggle()`
wherever you want the switch to appear; it flips `st.session_state["theme"]`
and triggers a rerun.
"""

import streamlit as st


# ─── Palettes ────────────────────────────────────────────────────────────────

LIGHT = {
    "bg":          "#FAF8F3",   # warm paper
    "surface":     "#FFFFFF",
    "surface_alt": "#F2EFE8",
    "border":      "#C9C4B5",   # darker so inputs and panels stand out on white
    "border_soft": "#E3DFD4",
    "text":        "#1A1A1A",
    "text_muted":  "#5A5A5A",
    "text_dim":    "#9A9A9A",
    "accent":      "#003DA5",   # primary action (January blue)
    "accent_hover": "#002B7A",
    "on_accent":   "#FFFFFF",
    "btn_bg":      "#FFFFFF",
    "btn_border":  "#C9C4B5",
    "btn_fg":      "#1A1A1A",
    "hc":          "#1F6B4A",
    "mc":          "#A57A08",
    "lc":          "#A8321C",
    "gap":         "#5B4E7A",
    "src":         "#3B5A80",
    "exec_bg":     "rgba(0,61,165,0.06)",
    "exec_border": "rgba(0,61,165,0.20)",
    "body_text":   "#2A2A2A",
    "section_open_bg": "rgba(0,0,0,0.03)",
}

DARK = {
    "bg":          "#0d1117",
    "surface":     "#161b22",
    "surface_alt": "#1c2230",
    "border":      "#30363d",
    "border_soft": "#21262d",
    "text":        "#e6edf3",
    "text_muted":  "#8b949e",
    "text_dim":    "#484f58",
    "accent":      "#003DA5",   # stays consistent with light mode for brand
    "accent_hover": "#1A52B8",
    "on_accent":   "#FFFFFF",
    "btn_bg":      "#000000",   # high contrast secondary button
    "btn_border":  "#FFFFFF",
    "btn_fg":      "#FFFFFF",
    "hc":          "#3fb950",
    "mc":          "#d29922",
    "lc":          "#f85149",
    "gap":         "#a371f7",
    "src":         "#58a6ff",
    "exec_bg":     "rgba(0,61,165,0.10)",
    "exec_border": "rgba(0,61,165,0.30)",
    "body_text":   "#c9d1d9",
    "section_open_bg": "rgba(255,255,255,0.02)",
}


AGENT_ACCENTS = {
    "agent1_precall":            "#2C5F4E",
    "agent2_diligence_mgmt":     "#3B5A80",
    "agent3_founder_diligence":  "#2C5F4E",
    "agent4_market_diligence":   "#3B5A80",
    "agent5_reference_check":    "#5B4E7A",
    "agent6_thesis_check":       "#B8870B",
    "agent7_premortem":          "#A8321C",
    "agent8_ic_simulation":      "#5B4E7A",
    "agent9_ic_memo":            "#2C5F4E",
}


def _current_palette() -> dict:
    mode = st.session_state.get("theme", "light")
    return LIGHT if mode == "light" else DARK


# Backwards-compatible alias: other modules import `COLORS`.
# Evaluated lazily via a module-level property-style proxy.
class _ColorsProxy:
    def __getitem__(self, key):
        return _current_palette()[key]
    def __getattr__(self, key):
        return _current_palette()[key]

COLORS = _ColorsProxy()


def _build_css(c: dict) -> str:
    return f"""
<style>
:root {{
  --bg: {c['bg']};
  --surface: {c['surface']};
  --surface-alt: {c['surface_alt']};
  --border: {c['border']};
  --border-soft: {c['border_soft']};
  --text: {c['text']};
  --text-muted: {c['text_muted']};
  --text-dim: {c['text_dim']};
  --accent: {c['accent']};
  --accent-hover: {c['accent_hover']};
  --on-accent: {c['on_accent']};
  --btn-bg: {c['btn_bg']};
  --btn-border: {c['btn_border']};
  --btn-fg: {c['btn_fg']};
  --hc: {c['hc']};
  --mc: {c['mc']};
  --lc: {c['lc']};
  --gap: {c['gap']};
  --src: {c['src']};
  --body-text: {c['body_text']};
}}

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{
  background: var(--bg) !important;
  color: var(--text) !important;
}}

.block-container {{
  padding-top: 1.6rem;
  max-width: 1400px;
}}

h1, h2, h3, h4, h5 {{
  color: var(--text) !important;
  letter-spacing: -0.01em;
}}

p, li, span, label, div {{ color: var(--text); }}

.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
  border-radius: 6px;
  border: 1px solid var(--btn-border) !important;
  background: var(--btn-bg) !important;
  color: var(--btn-fg) !important;
  font-weight: 600;
  transition: background 0.12s, border-color 0.12s, transform 0.05s;
}}
/* Force all descendants of secondary buttons to inherit the button foreground
   (Streamlit wraps labels in divs that would otherwise pick up `--text`). */
.stButton > button *, .stDownloadButton > button *, .stFormSubmitButton > button * {{
  color: var(--btn-fg) !important;
}}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {{
  border-color: var(--accent) !important;
  background: var(--surface-alt) !important;
  color: var(--btn-fg) !important;
}}
.stButton > button:active {{ transform: translateY(1px); }}

/* Primary: January blue in both themes, always white text. */
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
  background: var(--accent) !important;
  color: var(--on-accent) !important;
  border-color: var(--accent) !important;
}}
.stButton > button[kind="primary"] *, .stFormSubmitButton > button[kind="primary"] * {{
  color: var(--on-accent) !important;
}}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {{
  background: var(--accent-hover) !important;
  border-color: var(--accent-hover) !important;
  color: var(--on-accent) !important;
}}
.stButton > button:disabled {{
  opacity: 0.45;
  background: var(--border-soft) !important;
  color: var(--text-dim) !important;
  border-color: var(--border-soft) !important;
}}

.stTextInput input, .stTextArea textarea, .stNumberInput input, .stDateInput input {{
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 6px !important;
  color: var(--text) !important;
}}
.stTextInput input::placeholder, .stTextArea textarea::placeholder {{
  color: var(--text-dim) !important;
  opacity: 1;
}}
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {{
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 1px var(--accent) !important;
  outline: none !important;
}}
.stTextInput label, .stTextArea label, .stNumberInput label,
.stSelectbox label, .stRadio label, .stFileUploader label {{
  color: var(--text) !important;
  font-size: 12px !important;
  font-weight: 600 !important;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}}

/* Dialog / modal: force theme colors regardless of Streamlit's base config */
[data-testid="stDialog"], [data-testid="stModal"], div[role="dialog"] {{
  background: var(--surface) !important;
  color: var(--text) !important;
}}
[data-testid="stDialog"] *, [data-testid="stModal"] *, div[role="dialog"] * {{
  color: var(--text);
}}
[data-testid="stDialog"] h1, [data-testid="stDialog"] h2, [data-testid="stDialog"] h3,
[data-testid="stModal"] h1, [data-testid="stModal"] h2, [data-testid="stModal"] h3,
div[role="dialog"] h1, div[role="dialog"] h2, div[role="dialog"] h3 {{
  color: var(--text) !important;
}}

/* Dialog: tint inputs so they stand out against the white modal surface */
[data-testid="stModal"] .stTextInput input,
[data-testid="stModal"] .stTextArea textarea,
[data-testid="stDialog"] .stTextInput input,
[data-testid="stDialog"] .stTextArea textarea,
div[role="dialog"] .stTextInput input,
div[role="dialog"] .stTextArea textarea {{
  background: var(--bg) !important;
  color: var(--text) !important;
  border: 1.5px solid var(--border) !important;
}}
[data-testid="stModal"] .stTextInput label,
[data-testid="stDialog"] .stTextInput label,
div[role="dialog"] .stTextInput label {{
  color: var(--text) !important;
}}

.stSelectbox div[data-baseweb="select"] > div {{
  background: var(--surface) !important;
  border-color: var(--border) !important;
  border-radius: 6px !important;
  color: var(--text) !important;
}}
.stSelectbox div[data-baseweb="select"] * {{
  color: var(--text) !important;
}}

/* Selectbox dropdown popup (rendered in a separate portal at <body> level). */
div[data-baseweb="popover"], div[data-baseweb="menu"] {{
  background: var(--surface) !important;
  color: var(--text) !important;
  border: 1px solid var(--border) !important;
}}
div[data-baseweb="popover"] ul, div[data-baseweb="menu"] ul {{
  background: var(--surface) !important;
}}
div[data-baseweb="popover"] li, div[data-baseweb="menu"] li {{
  background: var(--surface) !important;
  color: var(--text) !important;
}}
div[data-baseweb="popover"] li *, div[data-baseweb="menu"] li * {{
  color: var(--text) !important;
}}
div[data-baseweb="popover"] li[aria-selected="true"],
div[data-baseweb="menu"] li[aria-selected="true"],
div[data-baseweb="popover"] li:hover,
div[data-baseweb="menu"] li:hover {{
  background: var(--surface-alt) !important;
}}

[data-testid="stFileUploader"] section {{
  background: var(--surface) !important;
  border: 1.5px dashed var(--border) !important;
  border-radius: 8px !important;
  padding: 14px !important;
}}
[data-testid="stFileUploader"] section:hover {{
  border-color: var(--accent) !important;
}}

.stRadio > div {{ background: transparent; }}

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

hr, [data-testid="stDivider"] {{
  border-color: var(--border-soft) !important;
}}

[data-testid="stExpander"] {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
}}

.stProgress > div > div > div > div {{
  background: var(--accent) !important;
}}

[data-testid="stCaptionContainer"], .stCaption, small {{
  color: var(--text-muted) !important;
}}

[data-testid="stAlert"] {{
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
}}

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
.conf-hc  {{ color: var(--hc);  background: rgba(44,95,78,0.12); }}
.conf-mc  {{ color: var(--mc);  background: rgba(184,135,11,0.12); }}
.conf-lc  {{ color: var(--lc);  background: rgba(168,50,28,0.12); }}
.conf-gap {{ color: var(--gap); background: rgba(91,78,122,0.12); }}
.conf-src {{ color: var(--src); background: rgba(59,90,128,0.12); }}
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

.stepper {{
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 12px 0 18px;
}}
.stepper-node {{ display: flex; flex-direction: column; align-items: center; gap: 4px; }}
.stepper-circle {{
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700;
  border: 2px solid var(--border);
  background: transparent;
  color: var(--text-dim);
}}
.stepper-circle.done {{ background: var(--accent); color: var(--on-accent); border-color: var(--accent); }}
.stepper-circle.active {{
  border-color: var(--accent); color: var(--accent);
  box-shadow: 0 0 10px rgba(44,95,78,0.25);
}}
.stepper-label {{ font-size: 11px; font-weight: 600; color: var(--text-dim); }}
.stepper-label.on {{ color: var(--accent); }}
.stepper-sub {{ font-size: 10px; color: var(--text-muted); }}
.stepper-bar {{ width: 80px; height: 2px; background: var(--border); margin: 0 6px 18px; }}
.stepper-bar.done {{ background: var(--accent); }}

.agent-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--border);
  border-radius: 8px;
  margin-bottom: 10px;
  overflow: hidden;
}}
.agent-card.empty {{ opacity: 0.5; }}
details.agent-card > summary.agent-card-head {{ cursor: pointer; list-style: none; }}
details.agent-card > summary.agent-card-head::-webkit-details-marker {{ display: none; }}
details.agent-card > summary.agent-card-head::after {{
  content: "\u25BC";
  font-size: 9px;
  color: var(--text-muted);
  transition: transform 0.15s;
}}
details.agent-card:not([open]) > summary.agent-card-head::after {{
  transform: rotate(-90deg);
}}
details.agent-card:not([open]) {{ border-bottom: 1px solid var(--border); }}
.agent-card-head {{
  padding: 14px 16px;
  display: flex; justify-content: space-between; align-items: center;
}}
.agent-card-title {{ font-weight: 600; font-size: 14px; color: var(--text); }}
.agent-card-tally {{ display: flex; align-items: center; gap: 6px; }}
.tally {{
  font-size: 10px; font-weight: 700;
  padding: 2px 7px; border-radius: 3px;
  letter-spacing: 0.03em;
}}
.tally-hc  {{ color: var(--hc);  background: rgba(44,95,78,0.12); }}
.tally-mc  {{ color: var(--mc);  background: rgba(184,135,11,0.12); }}
.tally-lc  {{ color: var(--lc);  background: rgba(168,50,28,0.12); }}
.tally-gap {{ color: var(--gap); background: rgba(91,78,122,0.12); }}
.empty-pill {{
  font-size: 11px; color: var(--text-dim);
  background: var(--border-soft);
  padding: 2px 8px; border-radius: 3px;
}}
.exec-summary {{
  margin: 0 16px 14px;
  background: {c['exec_bg']};
  border: 1px solid {c['exec_border']};
  border-radius: 6px;
  padding: 12px 14px;
}}
.exec-summary-label {{
  font-size: 10px; color: var(--accent); font-weight: 700;
  letter-spacing: 0.06em; margin-bottom: 5px;
}}
.exec-summary-body {{ font-size: 13px; color: var(--body-text); line-height: 1.6; }}
details.section {{
  margin: 0 16px 8px;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  overflow: hidden;
}}
details.section[open] > summary {{
  background: {c['section_open_bg']};
  border-bottom: 1px solid var(--border-soft);
}}
details.section > summary {{
  padding: 10px 14px; cursor: pointer;
  font-weight: 600; font-size: 13px; color: var(--text);
  list-style: none; display: flex; align-items: center; gap: 8px;
}}
details.section > summary::-webkit-details-marker {{ display: none; }}
details.section > summary::before {{
  content: "\u25B6"; font-size: 9px; color: var(--text-muted);
  transition: transform 0.15s;
}}
details.section[open] > summary::before {{ transform: rotate(90deg); }}
.section-body {{
  padding: 12px 14px; font-size: 13px; color: var(--body-text); line-height: 1.65;
}}
.section-body h3 {{
  font-size: 13px !important; font-weight: 700;
  color: var(--text) !important; margin: 14px 0 6px !important;
}}
.section-body h4 {{
  font-size: 12px !important; font-weight: 600;
  color: var(--text-muted) !important; margin: 10px 0 4px !important;
  text-transform: uppercase; letter-spacing: 0.04em;
}}
.section-body p {{ margin: 0 0 8px; }}
.section-body ul, .section-body ol {{ margin: 4px 0 8px; padding-left: 22px; }}
.section-body li {{ margin-bottom: 3px; }}
.section-body table {{
  width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 12px;
}}
.section-body th, .section-body td {{
  padding: 6px 10px; border: 1px solid var(--border-soft); text-align: left;
}}
.section-body th {{
  background: var(--surface-alt); font-weight: 600; color: var(--text);
}}
.section-body code {{
  background: var(--surface-alt);
  padding: 1px 5px; border-radius: 3px; font-size: 0.92em;
}}
.section-body blockquote {{
  border-left: 3px solid var(--accent);
  margin: 8px 0; padding: 4px 12px; color: var(--text-muted);
}}
</style>
"""


def inject_theme() -> None:
    """Inject the active theme's CSS. Call once near the top of each page."""
    st.session_state.setdefault("theme", "light")
    st.markdown(_build_css(_current_palette()), unsafe_allow_html=True)


def render_theme_toggle(key: str = "theme_toggle") -> None:
    """Render a small button that flips light ↔ dark for this session."""
    mode = st.session_state.get("theme", "light")
    label = "Dark mode" if mode == "light" else "Light mode"
    if st.button(label, key=key, help="Toggle theme", use_container_width=True):
        st.session_state["theme"] = "dark" if mode == "light" else "light"
        st.rerun()
