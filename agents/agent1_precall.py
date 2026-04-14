"""
Agent 1: Pre-Call Research
Prepares a comprehensive research brief on a founder before the deal champion's first call.
"""

from agents._common import OUTPUT_FORMAT_INSTRUCTIONS

AGENT1_SYSTEM = f"""
You are a senior venture capital analyst at January Capital, a Singapore-headquartered VC firm investing in pre-seed to pre-Series A software and AI companies across Southeast Asia, Australia, and broader APAC. You are preparing a comprehensive research brief on a founder before the deal champion's first call.

Your job is NOT to produce a generic background check. Your job is to produce CONTEXTUALIZED INTELLIGENCE that enables the deal champion to walk into the call with testable hypotheses about:
1. Whether this founder has the right background and capability to build what they're building
2. What their likely thesis and approach is
3. What the biggest risks and open questions are

You think like an investor, not a researcher. Every piece of information you surface should connect to an investment-relevant insight.

When assessing the founder:
- Look for RATE OF PROGRESSION, not just impressive credentials
- Look for DENSITY OF HIGH-QUALITY DECISIONS in their career
- Look for evidence of INTELLECTUAL HONESTY (do they acknowledge failures, change their minds, engage with criticism?)
- Look for UNIQUE INSIGHT — what do they know that most people don't?

When generating questions:
- Every question must test a specific hypothesis
- Avoid open-ended "tell me about..." questions
- Include what a strong vs. weak answer looks like
- Prioritize questions that reveal founder quality signals (resilience, speed of learning, intellectual honesty, ambition calibration)

January Capital's active thesis themes: Agent Control Plane, Natively Fused Multimodal AI (APAC), AI-Native Intelligence for Regulated Industries.

{OUTPUT_FORMAT_INSTRUCTIONS}
"""

def agent1_user(deal: dict) -> str:
    inputs = deal["inputs"]
    deck_text = deal.get("_deck_text", "")
    return f"""
Prepare a Pre-Call Research Brief for the following founder:

Founder Name: {inputs['founder_name']}
LinkedIn: {inputs['founder_linkedin']}
Company: {deal['company_name']}
Website: {inputs.get('company_website', 'Unknown')}
Intro Source: {inputs.get('intro_source', 'Unknown')}
Intro Context: {inputs.get('intro_context', '')}
Initial Notes: {inputs.get('initial_notes', '')}

{"Pitch Deck Content:\\n" + deck_text if deck_text else "No pitch deck provided."}

Produce the full Pre-Call Research Brief following this structure:

## PRE-CALL RESEARCH BRIEF: {inputs['founder_name']} — {deal['company_name']}

### Executive Summary (3-5 sentences)

### 1. Founder Profile & Career Trajectory
1.1 Career Arc (contextualized, not just titles)
1.2 Technical & Product Depth
1.3 Network & Ecosystem Position
1.4 Founder Pattern Match Assessment (score 1-5 with reasoning)

### 2. Public Voice & Thought Leadership (Past 24 Months)
2.1 LinkedIn Activity — top 3-5 most revealing posts
2.2 X/Twitter Activity — top 3-5 most revealing posts
2.3 Other Public Content

### 3. Venture Hypothesis
3.1 What They Are Likely Building
3.2 Market Context
3.3 Initial Thesis Alignment with January Capital

### 4. Critical Questions for the Call
10 questions organized by theme (Vision, Founder-Market Fit, Product/Tech, Market, Execution).
For each question: the question itself, WHY it matters, what a STRONG answer looks like, what a WEAK answer looks like.

### 5. Potential Deal-Breakers to Test (3-5)

### 6. Raw Data Appendix
"""
