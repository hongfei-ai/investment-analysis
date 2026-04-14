"""
Agent 8: IC Simulation
Simulates a January Capital Investment Committee discussion with four distinct personas.
"""

from agents._common import OUTPUT_FORMAT_INSTRUCTIONS

AGENT8_SYSTEM = f"""
You are simulating a January Capital Investment Committee discussion. You will roleplay four distinct IC personas:

1. CHAMPION — The deal advocate (enthusiastic, constructive, focused on upside)
2. SKEPTIC — The risk-focused IC member (probes assumptions, asks hard questions)
3. DOMAIN EXPERT — Deep knowledge of the specific sector or geography
4. GENERALIST — Pattern-matching across the portfolio and market

Each persona scores the deal independently on 10 dimensions (1-10). After independent scoring, produce a Conviction Profile — NOT a composite score.

Conviction Profile classification:
- STRONG CONVICTION: All scores 7+
- MODERATE CONVICTION: Mix of 6-8 scores, no extreme disagreement
- HIGH POTENTIAL SIGNAL: Champion scores 9-10 while others score 3-5 (flag explicitly — this is NOT a pass signal, it's a "why does the champion see something others don't?" signal)
- FALSE CONSENSUS WARNING: All scores 6-7 (flag — this may indicate groupthink)
- PASS: Multiple scores below 5 on critical dimensions

{OUTPUT_FORMAT_INSTRUCTIONS}
"""

def agent8_user(deal: dict) -> str:
    ic_prep = deal["ic_preparation"]
    diligence = deal["diligence"]
    return f"""
Company: {deal['company_name']}

Pre-Mortem output (Agent 7):
{ic_prep.get('pre_mortem', '[Not available]')}

All diligence summaries:
{diligence.get('tracker', '')}
{diligence.get('founder_diligence', '')}
{diligence.get('market_diligence', '')}
{diligence.get('reference_check', '')}
{diligence.get('thesis_check', '')}

Simulate the IC discussion and produce:

## IC SIMULATION: {deal['company_name']}

### Persona Scoring (each scores 1-10 independently)
Dimensions: Founder Quality, Market Size, Product Differentiation, Technical Credibility, Traction, Business Model, Competitive Moat, Thesis Fit, Risk/Reward, Overall Conviction

| Dimension | Champion | Skeptic | Domain Expert | Generalist |
|---|---|---|---|---|

### Conviction Profile Classification
[STRONG / MODERATE / HIGH POTENTIAL SIGNAL / FALSE CONSENSUS / PASS]

### Simulated Discussion
(Key arguments from each persona — where do they agree and disagree?)

### Critical IC Questions (that must be answered before a decision)

### Recommended Next Steps
"""
