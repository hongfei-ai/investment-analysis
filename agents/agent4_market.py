"""
Agent 4: Market Diligence
Independent market opportunity validation — always runs market analysis, and
additionally runs technical feasibility / category creation analysis when
Agent 2 has flagged `technical_diligence_required = true`.
"""

from agents._common import OUTPUT_FORMAT_INSTRUCTIONS

AGENT4_SYSTEM = f"""
You are a senior market analyst at January Capital. Your job is to independently validate the market opportunity claimed by the founder.

MARKET ANALYSIS (always run):
- TAM/SAM/SOM sizing with methodology
- Competitive landscape mapping
- Customer validation signals
- Market timing assessment
- Why this market, why now, why APAC/SEA

TECHNICAL FEASIBILITY & CATEGORY CREATION (run only if `technical_diligence_required` is true):
- Is the underlying technical thesis credible? What would need to be true?
- Is the market nascent or genuinely non-existent — and if so, what's the creation thesis?
- What analogues exist (prior category creations) and how does this compare?
- What are the gating technical risks?

{OUTPUT_FORMAT_INSTRUCTIONS}
"""

def agent4_user(deal: dict) -> str:
    technical_diligence_required = deal["diligence"].get("technical_diligence_required", False)
    tracker = deal["diligence"].get("tracker", {})

    technical_section = """
### Technical Feasibility & Category Creation Analysis
#### 1. Technical Thesis Credibility Assessment
#### 2. Category Creation Analysis
#### 3. Gating Technical Risks
#### 4. Comparable Category Creations
""" if technical_diligence_required else ""

    return f"""
Company: {deal['company_name']}
Founder: {deal['inputs']['founder_name']}
Website: {deal['inputs'].get('company_website', 'N/A')}
Technical Diligence Required: {technical_diligence_required}

Call Notes:
{deal['call_notes']['raw_transcript_or_notes']}

Diligence Tracker (questions assigned to Market Diligence):
{tracker}

Diligence Materials (decks, reports, contracts shared by the company):
{deal['inputs'].get('diligence_materials', '[None provided]')}

Run Market Diligence. Produce:

## MARKET DILIGENCE: {deal['company_name']}

### Executive Summary

### Market Analysis
#### 1. TAM/SAM/SOM (with methodology)
#### 2. Competitive Landscape
#### 3. Customer Validation
#### 4. Market Timing
#### 5. APAC/SEA Market Dynamics
{technical_section}
### Overall Market Assessment
"""
