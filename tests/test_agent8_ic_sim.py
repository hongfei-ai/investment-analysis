"""Regression guards on Agent 8's IC-simulation prompt and output template.

These tests pin the post-redesign disciplines: must-haves anchoring,
specialized Domain Expert, structured recommendation, non-consensus test,
and Agent 7 cross-references.
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


_stub_streamlit_if_missing()

from agents.agent8_ic_sim import AGENT8_SYSTEM, agent8_user


_SAMPLE_DEAL = {
    "company_name": "Acme",
    "diligence": {
        "tracker":            "Agent 2 output",
        "founder_diligence":  "Agent 3 output",
        "market_diligence":   "Agent 4 output",
        "reference_check":    "Agent 5 output",
        "thesis_check":       "Agent 6 output — Verdict: Strong",
    },
    "ic_preparation": {
        "pre_mortem": "Agent 7 matrix + deal-killer + consistency check",
    },
}


# ─── System prompt invariants ────────────────────────────────────────────────

def test_prompt_requires_must_haves_anchor():
    """Scoring anchors on must-haves, not a generic rubric. Regression guard."""
    lower = AGENT8_SYSTEM.lower()
    assert "must-have" in lower or "must have" in lower
    assert "20x" in AGENT8_SYSTEM, "Must-haves frame references 20x outcome"


def test_prompt_specializes_domain_expert_by_deal_type():
    """Domain Expert is instantiated per deal type, not a generic persona."""
    for archetype in ("DEEPTECH", "B2B SAAS", "CONSUMER", "FINTECH"):
        assert archetype in AGENT8_SYSTEM, f"Missing archetype: {archetype}"


def test_prompt_requires_champion_steelman():
    """Champion must state conviction-lowering conditions before scoring."""
    assert "conviction-lowering" in AGENT8_SYSTEM.lower() \
        or "lower their conviction" in AGENT8_SYSTEM.lower() \
        or "drop their conviction" in AGENT8_SYSTEM.lower() \
        or "drop conviction" in AGENT8_SYSTEM.lower()


def test_prompt_requires_structured_recommendation():
    """Closes with INVEST / CONDITIONAL / TRACK / PASS, not soft next steps."""
    for label in ("INVEST", "CONDITIONAL", "TRACK", "PASS"):
        assert label in AGENT8_SYSTEM, f"Missing recommendation label: {label}"


def test_prompt_requires_non_consensus_test():
    """Generalist owns the contrarian-belief test (Founders Fund / Thiel)."""
    lower = AGENT8_SYSTEM.lower()
    assert "non-consensus" in lower or "contrarian belief" in lower


def test_prompt_anchors_to_agent7_sections():
    """Agent 8 must cite the new Agent 7 anchors explicitly."""
    lower = AGENT8_SYSTEM.lower()
    assert "scenario matrix" in lower
    assert "deal-killer" in lower or "deal killer" in lower
    assert "shared blind spot" in lower


def test_prompt_requires_justification_per_cell():
    """Bare numbers are not acceptable — every score needs a rationale."""
    lower = AGENT8_SYSTEM.lower()
    assert "rationale" in lower or "justification" in lower


# ─── User template structure ─────────────────────────────────────────────────

def test_user_template_has_expected_sections_in_order():
    """Agent 9 consumes specific section names; pin them and their order."""
    prompt = agent8_user(_SAMPLE_DEAL)
    expected_sections = [
        "### Must-Haves for a 20x Outcome",
        "### Champion's Conviction-Lowering Conditions",
        "### Persona Scoring Against Must-Haves",
        "### Conviction Profile",
        "### Non-Consensus Test",
        "### Simulated Discussion",
        "### Critical IC Questions",
        "### Recommended Outcome",
    ]
    last = -1
    for section in expected_sections:
        idx = prompt.find(section)
        assert idx > last, f"Section out of order or missing: {section!r}"
        last = idx


def test_user_template_scoring_table_uses_must_haves():
    """The scoring matrix rows are Must-Haves, not generic dimensions."""
    prompt = agent8_user(_SAMPLE_DEAL)
    assert "| Must-Have | Champion | Skeptic | Domain Expert | Generalist |" in prompt


def test_user_template_forbids_h4_headers():
    """UI parser splits on H3; H4 would break nested collapsibles."""
    prompt = agent8_user(_SAMPLE_DEAL)
    for line in prompt.splitlines():
        assert not line.lstrip().startswith("#### "), \
            f"H4 header would break UI rendering: {line!r}"


def test_user_template_injects_company_name():
    prompt = agent8_user(_SAMPLE_DEAL)
    assert "## IC SIMULATION: Acme" in prompt
