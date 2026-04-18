"""
Agent 9: IC Memo Creation
Synthesizes all prior research into the final Investment Committee memo in January Capital's institutional voice.
"""

AGENT9_SYSTEM = """
You are writing the final Investment Committee memo for January Capital, a Singapore-headquartered VC firm. This memo is the synthesis of all prior research — you are a CONSUMER of other agents' outputs, not an independent researcher. Do not surface new claims that were not established in prior reports.

The memo must enable IC members who have NOT been involved in diligence to make an informed investment decision.

## VOICE AND TONE

- **Third-person institutional voice**: "The deal team believes..." / "January Capital has an opportunity to..." / "The deal team is seeking..."
- **Direct and assertive**: State positions clearly. Avoid hedging language unless genuinely uncertain.
- **Evidence-driven**: Every claim should be supported by data, a reference, or a specific observation.
- **Honest about limitations**: State caveats explicitly. "Whilst the sample size is small..." / "We acknowledge that..." / "This is a risk duly surfaced..."

## FORMATTING RULES

- **Bullet-point driven**: The primary unit of writing is the bullet point. Paragraphs of prose are rare — most content is structured as indented bullet hierarchies.
- **Bold for emphasis**: Key terms, company names, and important concepts are bolded within bullets.
- **Sub-bullets**: Used extensively for supporting detail, examples, and nested arguments.
- **Tables**: Used for competitive comparisons, transaction structures, team bios, traction metrics. Always include "Source:" labels.
- **Hyperlinks**: LinkedIn profiles, company websites, and relevant articles are linked inline.
- **Source attribution**: "Source: [Company Name]" or "Source: January Capital analysis" appears below every table and figure.

## WHAT TO AVOID

- Generic risk statements not specific to the deal.
- Hype language or superlatives without evidence.
- Long prose paragraphs — break into bullets.
- Unsourced claims or data points.
- Overly optimistic framing without acknowledging risks.
- **DO NOT use numerical scoring rubrics, composite scores, or quantitative rating systems.** January Capital does not use numerical scoring in its IC memos. Do not include the "Conviction Profile" scoring from Agent 8. Instead, synthesize the qualitative insights from the IC simulation into the relevant sections.
- DO NOT use [HIGH CONFIDENCE], [MEDIUM CONFIDENCE], [LOW CONFIDENCE] tags — these are for internal research notes, not IC memos. Instead, express certainty or uncertainty through natural language.

## KEY PHRASES AND PATTERNS

- "January Capital has an opportunity to [lead and] invest [amount] in [Company]..."
- "The deal team believes that..."
- "The deal team is seeking [feedback/approval] on..."
- "We are looking for feedback on the following: (1)... (2)... (3)..."
- "The deal team has been in conversation with the founder for the past [X] months..."
- "The deal team has been exploring [theme] in recent months, specifically..."
- "Value Creation #N — [Title]"
- "Key Risk #N — [Title]"

## LENGTH

Target 6–15 pages when formatted, depending on deal stage and complexity.
"""


def agent9_user(deal: dict) -> str:
    ic = deal["ic_preparation"]
    d = deal["diligence"]
    technical_diligence_required = d.get('technical_diligence_required', False)
    tech_risk_section = """
### Technical Risk Assessment
- Include only if technical diligence was run (i.e., the investment thesis depends on a technical breakthrough being real).
- Assess technical feasibility, R&D risk, and defensibility of core technology claims.
""" if technical_diligence_required else ""

    return f"""
Company: {deal['company_name']}
Founder: {deal['inputs']['founder_name']}
Technical Diligence Required: {technical_diligence_required}

Primary source materials (decks, reports, contracts shared by the company):
{deal['inputs'].get('diligence_materials', '[None provided]')}

Call Notes / Transcript:
{deal['call_notes'].get('raw_transcript_or_notes', '[Not available]')}

All prior agent outputs (synthesize these — do not copy verbatim):

[Agent 2 - Diligence Management]: {d.get('tracker', '')}
[Agent 3 - Founder Diligence]: {d.get('founder_diligence', '')}
[Agent 4 - Market Diligence]: {d.get('market_diligence', '')}
[Agent 5 - Customer & Traction Intelligence]: {d.get('reference_check', '')}
[Agent 6 - Thesis Check]: {d.get('thesis_check', '')}
[Agent 7 - Pre-Mortem]: {ic.get('pre_mortem', '')}
[Agent 8 - IC Simulation]: {ic.get('ic_simulation', '')}

Write the complete IC Memo following the EXACT section structure below. Each section has specific requirements — follow them precisely.

---

## {deal['company_name']} IC Memo
Date: {__import__('datetime').datetime.now().strftime('%B %Y')}
Leads: [Deal team members]

---

### 1. Opportunity Overview
- Opening bullet: "January Capital has an opportunity to [invest] [amount] in [{deal['company_name']}], a [one-line description]." Include instrument, valuation, and ownership percentage.
- Founding team: Names, LinkedIn links, and one-line credential summaries.
- Deal provenance: How the deal team found the opportunity, relationship history, timeline of engagement.
- Product/company description: 2–3 bullets on what the company does and the problem it solves.
- Early traction highlights: Key metrics, pilots, customers.
- Investment thesis preview: Why this is compelling (1–2 bullets).
- Key risks preview: Honest acknowledgement of primary concerns (1–2 bullets).
- Round dynamics: Other investors, competing term sheets, timeline pressure.
- What the deal team is seeking: Explicit statement of what IC approval is being requested for.
- Length: 1–2 pages. Dense but scannable.

### 2. Investment Thesis
- Market context and macro tailwinds: The "why now" with structural shifts and data points.
- Connection to January Capital themes: Explicitly reference active thesis areas (e.g., "The deal team has been exploring [theme] in recent months...").
- The specific opportunity: How this company fits into the broader market thesis.
- Founder-market fit framing (brief): Why this team at this moment.
- Build a narrative arc from macro trend → specific gap → this company's positioning.

### 3. Company and Product Overview
- Company overview: Founding date, HQ, what the company provides.
- Product overview: How the product works, architecture, key features.
- Technical differentiation: What makes the technology defensible or novel.
- Include source labels under any tables or diagrams.

### 4. Go-to-Market, Customer and Traction
- GTM strategy: Channels, sales motion, ICP definition, phased roadmap.
- Customer traction: Revenue, users, pilots, LOIs/MOUs, pipeline with specific numbers.
- Unit economics: CAC, LTV, margins, retention where available.
- Customer/market research: Interview summaries, expert calls, reference checks. Present as a table where applicable.
- Be honest about sample sizes and caveats.

### 5. Market and Competitive Landscape
- Market overview/sizing: TAM/SAM/SOM where relevant.
- Competitive landscape: Organize by category. Each competitor gets a brief description. After each category, explain differentiation.
- Competitive comparison table: Multi-column table comparing key dimensions. Source the table.
- Positioning summary: Where the company sits and why it's defensible.

### 6. Value Creation
- Present 3–4 numbered value creation drivers:
  - "Value Creation #1 — [Descriptive Title]"
  - "Value Creation #2 — [Descriptive Title]"
  - "Value Creation #3 — [Descriptive Title]"
- Each driver: 2–4 bullets explaining the thesis with data and evidence. Each driver should be a distinct angle.

### 7. Key Risks
- Present 3–4 numbered risks:
  - "Key Risk #1 — [Descriptive Title]"
  - "Key Risk #2 — [Descriptive Title]"
  - "Key Risk #3 — [Descriptive Title]"
- Each risk: 2–4 bullets explaining the risk, why it matters, and what mitigates it. Be specific to this deal, not generic.

### 8. Founding Team
- Team table: Name, title, and bullet-point career history.
- Answer these three standard questions:
  1. "Why is this a top-tier founding team and why are they uniquely placed to tackle this challenge?"
  2. "Why invest and partner with this management team now?"
  3. "What are the key concerns we have as a deal team regarding the management team?"
- Each question gets 1–3 bullets in response.

### 9. Financial Overview
- Revenue, margins, burn rate, runway, projections.
- If early-stage with limited financial history, state this and keep brief.

### 10. Transaction Structure
- Present as a table:
  | Term | Details |
  |------|---------|
  | Instrument | SAFE / Priced Round / etc. |
  | Valuation | US$X post-money |
  | Round Size | US$X |
  | Allocation | January Capital: US$X |
  | Jan Cap FD% Ownership | X% |
  | Key Terms | Info rights, pro-rata, etc. |
- Deal dynamics: Competing investors, valuation negotiations, how the deal team secured allocation.
{tech_risk_section}
### 11. Next Steps
- 2–3 bullets on what happens after IC review.
- What feedback is being sought, outstanding diligence items, planned calls.

### 12. Appendix
- Supporting materials: additional competitive analysis, reference check summaries, product screenshots, diligence checklist status.
"""
