"""
Agent 4: Market Diligence
Independent market opportunity validation — Mode A (existing market) and/or Mode B (category creation).
"""

from agents._common import OUTPUT_FORMAT_INSTRUCTIONS

AGENT4_SYSTEM = f"""
You are a senior market analyst at January Capital. Your job is to independently validate the market opportunity claimed by the founder, using the deal classification assigned by Agent 2.

MODE A — Existing Market Diligence:
- TAM/SAM/SOM sizing with methodology
- Competitive landscape mapping
- Customer validation signals
- Market timing assessment
- Why this market, why now, why APAC/SEA

MODE B — Technical Feasibility & Category Creation:
- Is the underlying technical thesis credible? What would need to be true?
- Is the market nascent or genuinely non-existent — and if so, what's the creation thesis?
- What analogues exist (prior category creations) and how does this compare?
- What are the gating technical risks?

Run the mode(s) assigned by the Diligence Management Agent.

{OUTPUT_FORMAT_INSTRUCTIONS}
"""

def agent4_user(deal: dict) -> str:
    mode = deal["diligence"].get("deal_mode", "A")
    tracker = deal["diligence"].get("tracker", {})
    return f"""
Company: {deal['company_name']}
Founder: {deal['inputs']['founder_name']}
Website: {deal['inputs'].get('company_website', 'N/A')}
Deal Mode assigned by Agent 2: {mode}

Call Notes:
{deal['call_notes']['raw_transcript_or_notes']}

Diligence Tracker (questions assigned to Market Diligence):
{tracker}

Diligence Materials (decks, reports, contracts shared by the company):
{deal['inputs'].get('diligence_materials', '[None provided]')}

Run Market Diligence in {mode} mode. Produce:

## MARKET DILIGENCE ({mode} MODE): {deal['company_name']}

### Executive Summary

{"### Mode A: Existing Market Analysis" if "A" in mode else ""}
{"#### 1. TAM/SAM/SOM (with methodology)" if "A" in mode else ""}
{"#### 2. Competitive Landscape" if "A" in mode else ""}
{"#### 3. Customer Validation" if "A" in mode else ""}
{"#### 4. Market Timing" if "A" in mode else ""}
{"#### 5. APAC/SEA Market Dynamics" if "A" in mode else ""}

{"### Mode B: Technical Feasibility & Category Creation" if "B" in mode else ""}
{"#### 1. Technical Thesis Credibility Assessment" if "B" in mode else ""}
{"#### 2. Category Creation Analysis" if "B" in mode else ""}
{"#### 3. Gating Technical Risks" if "B" in mode else ""}
{"#### 4. Comparable Category Creations" if "B" in mode else ""}

### Overall Market Assessment
"""
