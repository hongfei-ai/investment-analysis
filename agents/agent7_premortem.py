"""
Agent 7: Pre-Mortem / Devil's Advocate
Steelmans the bear case — surfaces all the ways the investment could fail.
"""

from agents._common import OUTPUT_FORMAT_INSTRUCTIONS

AGENT7_SYSTEM = f"""
You are the Devil's Advocate at January Capital's IC. Your job is to steelman the bear case — to articulate, as compellingly as possible, all the ways this investment could fail.

You are NOT trying to kill the deal. You are trying to surface risks the deal champion may have rationalized away. The goal is to make the IC discussion more rigorous.

Draw on:
- The key assumptions identified by Agent 2
- Weaknesses identified across all diligence reports
- Historical failure patterns for similar companies
- APAC-specific risk factors (regulatory, distribution, talent)

For each failure scenario: name it, articulate the mechanism, assess probability (Low/Medium/High), and identify what evidence would confirm or refute it.

{OUTPUT_FORMAT_INSTRUCTIONS}
"""

def agent7_user(deal: dict) -> str:
    diligence = deal["diligence"]
    return f"""
Company: {deal['company_name']}

All diligence outputs:

Diligence Management (Agent 2):
{diligence.get('tracker', '[Not available]')}

Founder Diligence (Agent 3):
{diligence.get('founder_diligence', '[Not available]')}

Market Diligence (Agent 4):
{diligence.get('market_diligence', '[Not available]')}

Reference Check (Agent 5):
{diligence.get('reference_check', '[Not available]')}

Thesis Check (Agent 6):
{diligence.get('thesis_check', '[Not available]')}

Produce:

## PRE-MORTEM / DEVIL'S ADVOCATE: {deal['company_name']}

### Executive Summary (the 3 most dangerous risks)

### Failure Scenario Analysis
(For each scenario: Name → Mechanism → Probability → Confirming/Refuting Evidence)

1. [Scenario name]
2. [Scenario name]
3. [Scenario name]
... (as many as credible, minimum 5)

### Assumptions Most Likely to Be Wrong
### Key Questions the IC Must Answer
### What Would Change This Bear Case
"""
