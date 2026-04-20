"""Regression guards on Agent 7's pre-mortem prompt and output template.

These tests pin the epistemic disciplines and output structure the IC
depends on — breaking any of them changes what Agents 8 and 9 see and
what the UI renders.
"""

import sys
import types
from pathlib import Path


def _stub_streamlit_if_missing():
    if "streamlit" in sys.modules:
        return
    st = types.ModuleType("streamlit")
    st.cache_data = lambda *a, **k: (lambda f: f)
    st.cache_resource = lambda *a, **k: (lambda f: f)
    sys.modules["streamlit"] = st


def _stub_markdown_if_missing():
    """ui/cards.py imports `markdown`; stub it so ui.output_parser can import."""
    if "markdown" in sys.modules:
        return
    md = types.ModuleType("markdown")
    md.markdown = lambda text, **kwargs: text
    sys.modules["markdown"] = md


_stub_streamlit_if_missing()
_stub_markdown_if_missing()

from agents.agent7_premortem import AGENT7_SYSTEM, agent7_user


_SAMPLE_DEAL = {
    "company_name": "Acme",
    "diligence": {
        "tracker":            "Agent 2 output here",
        "founder_diligence":  "Agent 3 output here",
        "market_diligence":   "Agent 4 output here",
        "reference_check":    "Agent 5 output here",
        "thesis_check":       "Agent 6 output — Verdict: Strong",
    },
}


# ─── System prompt invariants ────────────────────────────────────────────────

def test_prompt_contains_kill_vs_mediocre_split():
    """Every scenario must be tagged KILL or MEDIOCRE. Regression guard."""
    assert "KILL" in AGENT7_SYSTEM
    assert "MEDIOCRE" in AGENT7_SYSTEM


def test_prompt_requires_leading_indicators_at_standard_horizons():
    """Leading indicators at 6 / 12 / 18 months are the primary output axis."""
    for token in ("6", "12", "18"):
        assert token in AGENT7_SYSTEM, f"Missing horizon token {token!r}"
    assert "month" in AGENT7_SYSTEM.lower()


def test_prompt_removes_apac_hardcoding():
    """APAC must be inferred from Agent 4's market output, not hardcoded."""
    assert "APAC-specific risk factors" not in AGENT7_SYSTEM


def test_prompt_requires_consistency_check_vs_agent6():
    """Consistency check against Agent 6's thesis verdict is load-bearing."""
    assert "Agent 6" in AGENT7_SYSTEM
    assert "thesis" in AGENT7_SYSTEM.lower()


# ─── User template structure ─────────────────────────────────────────────────

def test_user_template_has_expected_sections_in_order():
    """Agent 8 and Agent 9 consume specific section names. Pin them here."""
    prompt = agent7_user(_SAMPLE_DEAL)
    expected_sections = [
        "### Executive Summary",
        "### Scenario Matrix",
        "### P1 Hypothesis Inversions",
        "### Deal-Killer Threshold",
        "### Consistency Check vs Upstream Verdicts",
        "### Shared Blind Spot Check",
        "### What Would Change This Bear Case",
    ]
    last = -1
    for section in expected_sections:
        idx = prompt.find(section)
        assert idx > last, f"Section out of order or missing: {section!r}"
        last = idx


def test_user_template_contains_markdown_table_skeleton():
    """The Scenario Matrix must be a valid markdown table (pipes + --- separator)."""
    prompt = agent7_user(_SAMPLE_DEAL)
    assert "| # | Scenario | Type |" in prompt
    assert "| -" in prompt  # row separator


def test_user_template_injects_company_name():
    prompt = agent7_user(_SAMPLE_DEAL)
    assert "## PRE-MORTEM: Acme" in prompt


def test_user_template_forbids_h4_headers():
    """The UI parser splits on H3; H4 would break nested collapsibles."""
    prompt = agent7_user(_SAMPLE_DEAL)
    for line in prompt.splitlines():
        assert not line.lstrip().startswith("#### "), \
            f"H4 header would break UI rendering: {line!r}"


# ─── UI parser compatibility ─────────────────────────────────────────────────

_SAMPLE_OUTPUT = """\
## PRE-MORTEM: Acme

### Executive Summary
- Most dangerous risk: founder cannot recruit a VP Eng at this geography [MEDIUM CONFIDENCE]
- Second: thin customer evidence behind the "10x faster" claim [LOW CONFIDENCE / INFERRED]
- Third: regulatory change in Q3 could reprice the TAM
- Deal-killer threshold: none identified — every concern is a risk, not a veto
- Consistency signal vs Agent 6 verdict: Strong thesis + compelling bear case = high-potential-signal territory

### Scenario Matrix
| # | Scenario | Type | Mechanism | 6-mo signal | 12-mo signal | 18-mo signal | Reference class & base rate | Refutable by |
| - | -------- | ---- | --------- | ----------- | ------------ | ------------ | --------------------------- | ------------ |
| 1 | Talent gap | KILL | No VP Eng hired, tech debt accrues | offer-accept rate < 30% | key hire missed | code-freeze rate rising | SEA pre-seed B2B; ~60% miss tech leadership by M18 | executed VP Eng offer letter |
| 2 | Traction illusion | MEDIOCRE | Top logo churns, ARR stalls | pilot-to-paid < 25% | NRR < 100% | ARR growth < 2x | [NO BASE RATE AVAILABLE] — default ~50% fail to double ARR | anchor-customer 12-mo commit letter |

### P1 Hypothesis Inversions
**Q1 — Can the founder attract technical talent?**
- Agent 2 hypothesis: yes, via his Optiver network
- If wrong, maps to scenario: 1
- Earliest observable sign: 6-month offer-accept rate < 30%
- Confidence: MEDIUM CONFIDENCE

### Deal-Killer Threshold
None identified — every concern is a risk, not a veto.

### Consistency Check vs Upstream Verdicts
- Agent 3 (Founder) verdict: Worth Partner Meeting
- Agent 6 (Thesis Fit) verdict: Strong
- Bear-case strength: moderate — two credible scenarios, one insufficient-data flag
- Pattern signal: Strong thesis + moderate bear case = Agent 8 should probe why the champion's conviction outpaces upstream skepticism

### Shared Blind Spot Check
"10x faster" performance claim is repeated across Agents 3, 4, and 6 but traces to a single founder-stated benchmark with no third-party verification. Most likely shared blind spot.

### What Would Change This Bear Case
- A signed anchor-customer letter with 12-month ARR commit would refute Scenario 2.
- An accepted VP Eng offer would refute Scenario 1.
- Independent benchmark from a design partner would refute the shared blind spot.
"""


def test_sample_output_parses_cleanly():
    """Hand-written sample must parse through the UI output parser."""
    from ui.output_parser import parse_output

    parsed = parse_output(_SAMPLE_OUTPUT)
    assert parsed.exec_summary is not None, "Executive Summary must be detected"

    section_titles = {s.title for s in parsed.sections}
    # Parser splits on H2 (one section for us) and further on H3 via cards.py,
    # so here we just verify the top-level parses and the exec summary exists.
    assert any("PRE-MORTEM" in t.upper() for t in section_titles)

    # Confidence tags should be tallied (we include HC/MC/LC in the sample).
    total = parsed.total
    total_tags = total.hc + total.mc + total.lc + total.gap
    assert total_tags >= 1, "At least one confidence tag should be counted"
