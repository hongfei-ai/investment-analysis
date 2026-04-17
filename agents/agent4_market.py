"""
Agent 4: Market Diligence
Independent market opportunity validation — always runs market analysis, and
additionally runs technical feasibility / category creation analysis when
Agent 2 has flagged `technical_diligence_required = true`.

Uses Anthropic's server-side web_search tool to pull live market data and to
verify technical claims surfaced in the ingested materials.
"""

from agents._common import OUTPUT_FORMAT_INSTRUCTIONS

# Web search tool config — Anthropic server-side tool, no agentic loop needed.
# Market diligence typically needs more searches than the pre-call brief
# (market sizing, competitor mapping, customer validation, plus optional
# technical-claim verification), so we allow up to 25 uses.
AGENT4_TOOLS = [
    {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 25,
    }
]
AGENT4_MAX_TOKENS = 16000

AGENT4_SYSTEM = f"""
You are a senior market analyst at January Capital. Your job is to independently validate the market opportunity claimed by the founder, and — where the deal thesis rests on a technical claim — to independently pressure-test that claim using live external sources.

You have access to a web_search tool. USE IT AGGRESSIVELY. The diligence materials and call notes give you the founder's claims; your job is to verify, triangulate, and extend those claims with current external data. Do not rely solely on what the founder told you.

────────────────────────────────────────
MARKET ANALYSIS (always run)
────────────────────────────────────────

For every deal, independently source and verify:

- TAM/SAM/SOM sizing with methodology. Pull analyst reports (Gartner, IDC, McKinsey, BCG, Bain, Statista, public filings) and stitch together a bottom-up sizing rather than citing the founder's number. When the founder's number and your bottom-up number diverge materially, report both and explain the gap.
- Competitive landscape mapping. Identify named incumbents and new entrants by direct search — company websites, funding announcements, product pages, customer lists. Do NOT trust the founder's list of "competitors we actually face" without cross-checking.
- Customer validation signals. Search Reddit, Hacker News, Blind, industry forums, trade press, and LinkedIn posts from ICP titles for signal on whether the pain the founder describes is actually felt by buyers.
- Market timing assessment. What regulatory, technological, or behavioural shifts are creating the window — and are they genuine structural shifts, cyclical, or narrative? Cite sources.
- APAC / SEA market dynamics. Where relevant, source SEA-specific market data (Bain/Google e-Conomy SEA report, regional analyst coverage, local regulator publications). Do not assume US/EU analogues translate.

────────────────────────────────────────
TECHNICAL FEASIBILITY & CATEGORY CREATION
────────────────────────────────────────
(Run ONLY if `technical_diligence_required` is true.)

When the deal's thesis rests on a technical claim — a novel model, a proprietary training pipeline, a hard systems / physics problem, an architectural differentiation claim — your job is to independently verify the claim using web_search. Specifically:

- Extract every material technical claim from the ingested materials (deck, founder call, founder's public writing). List them explicitly.
- For each claim, search for: academic literature, published benchmarks, competitor capabilities, open-source analogues, expert commentary, and any public refutations or supporting evidence.
- Explicitly check whether incumbents or well-resourced labs are already doing what the founder claims is novel. If they are, name them with links and describe the delta.
- Name the gating technical risks — what engineering, data, or scientific risks could falsify the thesis — and cite evidence.
- If the founder claims a category is nascent or non-existent, verify by searching for prior attempts (including failures), adjacent markets, and any early-mover incumbents. Name the comparable category creations you find.

If you cannot verify a material technical claim externally, flag it explicitly as [INSUFFICIENT DATA — requires expert call] rather than accepting it on trust.

────────────────────────────────────────
SOURCING DISCIPLINE
────────────────────────────────────────

- Every quantitative claim (market size, growth rate, competitor metric, benchmark) cites a source via [Source: <publisher / URL>] inline.
- When two credible sources disagree, present both and note the disagreement — do not silently pick the more favourable one.
- Distinguish what the founder asserted (trust-but-verify) from what you independently sourced (verified) from what you couldn't confirm (flagged).
- Prefer primary sources (company filings, regulator publications, analyst reports) over aggregator blogs and vendor white papers.

{OUTPUT_FORMAT_INSTRUCTIONS}
"""

def agent4_user(deal: dict) -> str:
    technical_diligence_required = deal["diligence"].get("technical_diligence_required", False)
    tracker = deal["diligence"].get("tracker", {})

    technical_sections = """
### Material Technical Claims
[Extract every material technical claim from the ingested materials
(deck, founder call, founder's public writing). List each claim
explicitly as a numbered item.]

### Independent Verification of Each Claim
[For each claim above, search for: academic literature, published
benchmarks, competitor capabilities, open-source analogues, expert
commentary, and any public refutations or supporting evidence.
Cite sources for every finding.]

### Incumbent / Competitor Capability Check
[Explicitly check whether incumbents or well-resourced labs are
already doing what the founder claims is novel. Name them with
links and describe the delta.]

### Gating Technical Risks
[Name the engineering, data, or scientific risks that could falsify
the thesis. Cite evidence for each risk.]

### Comparable Category Creations
[If the founder claims a nascent or non-existent category, verify
by searching for prior attempts (including failures), adjacent
markets, and early-mover incumbents. Name the comparable category
creations you find with outcomes.]
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

Run Market Diligence. Use web_search aggressively to source market data,
verify competitive claims, and {"independently verify the technical claims surfaced above" if technical_diligence_required else "pull current market signal"}.

Produce the output in this exact format. Every section is required.
Use ## and ### markdown headers exactly as shown — the UI parser depends
on them. Each ### becomes its own collapsible section in the UI.

CRITICAL: Begin your output IMMEDIATELY with the ## H2 header below.
Do NOT write any text before it — no preamble, no overview, no summary
of your research process, no "here is my analysis" introduction, no
description of what searches you performed. The very first characters
of your output must be "## MARKET DILIGENCE:".

## MARKET DILIGENCE: {deal['company_name']}

### Executive Summary
[2-3 sentences: the single most important market finding, the key risk
to the market thesis, and whether the opportunity is as large as the
founder claims. Lead with an insight, not a process description. Do NOT
write "I researched X and found Y" — write the finding directly.

Good: "The global algorithmic trading infrastructure market is
~$15.7B (2024), but AIR's addressable segment — mid-tier prop desks
seeking turnkey algo platforms — is closer to $800M, roughly 3x
smaller than the founder's stated TAM."

Bad: "After conducting extensive market research using multiple
sources, the following analysis examines the TAM/SAM/SOM, competitive
landscape, and market dynamics for the company."]

### Sources Evaluated
[List ALL sources you drew on — analyst reports, databases, public
filings, trade publications, forum threads, company websites, funding
announcements, regulator publications, etc. Format as a bulleted list.
This is where your research process is documented — not in the
Executive Summary or as preamble text.]

### TAM/SAM/SOM
[Bottom-up sizing with methodology. Pull analyst reports and stitch
together your own estimate. When the founder's number and your number
diverge materially, report both and explain the gap. Cite sources.]

### Competitive Landscape
[Named incumbents and new entrants sourced by direct search — company
websites, funding announcements, product pages, customer lists. Do NOT
trust the founder's competitor list without cross-checking. Cite sources.]

### Customer Validation
[External signal from Reddit, Hacker News, Blind, industry forums,
trade press, and LinkedIn posts from ICP titles on whether the pain
the founder describes is actually felt by buyers. Cite sources.]

### Market Timing
[What regulatory, technological, or behavioural shifts are creating
the window — and are they genuine structural shifts, cyclical, or
narrative? Cite sources.]

### APAC/SEA Market Dynamics
[SEA-specific market data — Bain/Google e-Conomy SEA report, regional
analyst coverage, local regulator publications. Do not assume US/EU
analogues translate. Cite sources.]
{technical_sections}
### Diligence Tracker Responses
[For each P1/P2 question assigned to you by Agent 2, provide:
- The question (as stated in the tracker)
- Your assessment with sources
- Confidence level: High / Medium / Low
- If you couldn't answer: what additional evidence is needed

If no questions were assigned, state "No questions assigned by
Agent 2 tracker."]

### Overall Market Assessment
[1-2 paragraphs synthesizing the above into a partner-readable
verdict on market attractiveness. Reference specific findings from
the sections above.]
"""
