"""
Agent 5: Reference Check
Surfaces signal (including negative signal) through reference intelligence.
"""

from agents._common import OUTPUT_FORMAT_INSTRUCTIONS

AGENT5_SYSTEM = f"""
You are a senior VC analyst at January Capital conducting reference intelligence on a founder. This is NOT a standard reference call prep sheet. Your job is to surface SIGNAL, including negative signal that founders would not volunteer.

Section 0: Negative Signal Hunting
- Employee retention analysis (LinkedIn: who left, when, what did they say?)
- Absent reference detection (who is NOT available as a reference and why?)
- Anonymous platform mining (Glassdoor, Blind, Reddit, startup forums)
- Litigation and regulatory check (court records, regulatory filings)
- APAC-adapted indirect elicitation: given cultural norms around direct criticism in SEA, design questions that surface concerns indirectly

For reference call prep:
- Prioritize references NOT provided by the founder
- Design questions using the "contextualized assumption" technique to elicit honest responses
- Flag if reference network seems shallow or managed

{OUTPUT_FORMAT_INSTRUCTIONS}
"""

def agent5_user(deal: dict) -> str:
    tracker = deal["diligence"].get("tracker", {})
    return f"""
Company: {deal['company_name']}
Founder: {deal['inputs']['founder_name']}
LinkedIn: {deal['inputs'].get('founder_linkedin', 'N/A')}

Pre-Call Research:
{deal['pre_call'].get('research_output', '[Not available]')}

Call Notes:
{deal['call_notes']['raw_transcript_or_notes']}

Diligence Tracker (P1/P2 questions assigned to Reference Check):
{tracker}

Diligence Materials (decks, reports, contracts shared by the company):
{deal['inputs'].get('diligence_materials', '[None provided]')}

Produce:

## REFERENCE CHECK INTELLIGENCE: {deal['inputs']['founder_name']} / {deal['company_name']}

### Executive Summary

### Section 0: Negative Signal Hunting
0.1 Employee Retention Analysis
0.2 Absent Reference Detection
0.3 Anonymous Platform Intelligence
0.4 Litigation & Regulatory Check

### Section 1: Reference Map
(Who to call, in priority order, with relationship to founder and angle to probe)

### Section 2: Reference Call Question Scripts
(10-15 questions with APAC-adapted indirect elicitation techniques)

### Section 3: Red Flags to Probe
"""
