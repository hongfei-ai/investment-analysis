"""
Agent 3: Founder Diligence
Deep founder assessment — beyond surface credentials.
"""

from agents._common import OUTPUT_FORMAT_INSTRUCTIONS

AGENT3_SYSTEM = f"""
You are a senior VC analyst at January Capital conducting deep founder diligence. Your job is to go beyond surface credentials and assess whether this founder has what it takes to build a category-defining company in APAC/SEA.

Focus areas:
- Prior company building experience (exits, failures, lessons learned)
- Domain depth and unique insight
- Leadership and team-building track record
- Resilience signals (how they've navigated adversity)
- Integrity and reference signals
- Alignment between founder background and this specific venture

Be skeptical but fair. Flag concerns explicitly. Do not give benefit of the doubt without evidence.

{OUTPUT_FORMAT_INSTRUCTIONS}
"""

def agent3_user(deal: dict) -> str:
    tracker = deal["diligence"].get("tracker", {})
    return f"""
Company: {deal['company_name']}
Founder: {deal['inputs']['founder_name']}
LinkedIn: {deal['inputs'].get('founder_linkedin', 'N/A')}

Pre-Call Research:
{deal['pre_call'].get('research_output', '[Not available]')}

Call Notes:
{deal['call_notes']['raw_transcript_or_notes']}

Diligence Tracker (P1/P2 questions assigned to Founder Diligence):
{tracker}

Diligence Materials (decks, reports, contracts shared by the company):
{deal['inputs'].get('diligence_materials', '[None provided]')}

Produce a comprehensive Founder Diligence report:

## FOUNDER DILIGENCE: {deal['inputs']['founder_name']} / {deal['company_name']}

### Executive Summary

### 1. Career & Domain Deep Dive
### 2. Company Building Track Record
### 3. Founder-Market Fit Assessment
### 4. Leadership & Team-Building Signals
### 5. Integrity & Reference Signals
### 6. Risk Flags & Open Questions
### 7. Overall Founder Assessment (score 1-10 with rationale)
"""
