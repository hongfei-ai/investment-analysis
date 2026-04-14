"""
shared.py — Shared utilities, knowledge store, and API caller for all agents.
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

# Support both .env (local) and Streamlit secrets (cloud)
def _get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return None

client = anthropic.Anthropic(api_key=_get_api_key())
MODEL = "claude-opus-4-6"

DEALS_DIR = Path("deals")
OUTPUTS_DIR = Path("outputs")
DEALS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)


# ─── Knowledge Store ──────────────────────────────────────────────────────────

def load_deal(deal_name: str) -> dict:
    """Load deal context from JSON, or create a new one."""
    path = DEALS_DIR / f"{deal_name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {
        "deal_id": deal_name,
        "company_name": deal_name,
        "date_created": datetime.now().isoformat(),
        "status": "pre-call",
        "inputs": {
            "founder_name": "",
            "founder_linkedin": "",
            "founder_email": "",
            "company_website": "",
            "pitch_deck_path": "",
            "intro_source": "",
            "intro_context": "",
            "initial_notes": ""
        },
        "pre_call": {
            "research_output": {},
            "suggested_questions": [],
            "human_notes": ""
        },
        "call_notes": {
            "raw_transcript_or_notes": "",
            "date_of_call": "",
            "attendees": [],
            "human_annotations": ""
        },
        "diligence": {
            "tracker": {},
            "deal_mode": "",
            "founder_diligence": {},
            "market_diligence": {},
            "reference_check": {},
            "thesis_check": {},
            "human_review_notes": ""
        },
        "ic_preparation": {
            "pre_mortem": {},
            "ic_simulation": {},
            "ic_memo": {},
            "human_edits": ""
        }
    }


def save_deal(deal: dict):
    """Persist deal context to JSON."""
    path = DEALS_DIR / f"{deal['deal_id']}.json"
    path.write_text(json.dumps(deal, indent=2))


def save_output(deal_name: str, agent_key: str, content: str):
    """Save agent output as markdown and return the path."""
    out_dir = OUTPUTS_DIR / deal_name
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{agent_key}.md"
    path.write_text(content, encoding="utf-8")
    print(f"  ✓ Saved: {path}")
    return path


# ─── PDF Reader ───────────────────────────────────────────────────────────────

def read_pdf(path: str) -> str:
    """Extract text from a PDF file."""
    try:
        import PyPDF2
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            return "\n\n".join(
                page.extract_text() for page in reader.pages if page.extract_text()
            )
    except Exception as e:
        return f"[Could not read PDF: {e}]"


# ─── API Caller ───────────────────────────────────────────────────────────────

def call_claude(system_prompt: str, user_message: str, max_tokens: int = 8000) -> str:
    """Call Claude and return the text response."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )
    return response.content[0].text


# ─── Output Standards ─────────────────────────────────────────────────────────

# ─── UI Helpers ──────────────────────────────────────────────────────────────

def list_deals() -> list[str]:
    """Return sorted list of deal names from deals/ folder."""
    return sorted(
        p.stem for p in DEALS_DIR.glob("*.json")
    )



def read_output(deal_name: str, agent_key: str) -> str | None:
    """Load a saved agent markdown output, or None if not found."""
    path = OUTPUTS_DIR / deal_name / f"{agent_key}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


# ─── Output Standards ─────────────────────────────────────────────────────────

OUTPUT_FORMAT_INSTRUCTIONS = """
Output format standards (apply to every section):
- Structured markdown with clear headers
- All claims must cite source URL or document
- Use [HIGH CONFIDENCE], [MEDIUM CONFIDENCE], [LOW CONFIDENCE / INFERRED] where inference is involved
- Separate factual findings from analytical judgments
- Begin with a 3-5 sentence executive summary
- Use [INSUFFICIENT DATA — requires manual input] rather than fabricating content
"""
