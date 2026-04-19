"""Tests for dashboard.queries — pure-function dashboard read path."""

from datetime import datetime, timedelta, timezone

import pytest

import shared
from dashboard import queries


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def deals_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "DEALS_DIR", tmp_path)
    return tmp_path


def _make_deal(name: str, **overrides) -> dict:
    """Load a fresh skeleton and overlay the given fields."""
    deal = shared.load_deal(name)
    for k, v in overrides.items():
        # Support dotted paths for nested edits: "diligence.tracker"
        if "." in k:
            section, field = k.split(".", 1)
            deal.setdefault(section, {})[field] = v
        else:
            deal[k] = v
    return deal


def _save(deal: dict) -> None:
    shared.atomic_save_deal(deal)


# ─── agent_progress / thesis_verdict ─────────────────────────────────────────

def test_agent_progress_counts_nonempty_outputs():
    deal = {
        "pre_call":        {"research_output": "# Brief"},
        "diligence":       {"tracker": "P1 questions", "founder_diligence": "",  # empty string = not done
                            "market_diligence": "notes", "thesis_check": "verdict"},
        "ic_preparation":  {"pre_mortem": {}, "ic_simulation": "", "ic_memo": "memo text"},
    }
    done, total, keys = queries.agent_progress(deal)
    assert total == 9
    assert done == 5
    assert "agent1_precall" in keys
    assert "agent3_founder" not in keys  # empty string → not done


def test_agent_progress_all_empty():
    deal = {"pre_call": {}, "diligence": {}, "ic_preparation": {}}
    done, total, keys = queries.agent_progress(deal)
    assert done == 0 and total == 9 and keys == []


def test_thesis_verdict_extracts_from_standard_header():
    deal = {"diligence": {"thesis_check": """
### 7. Thesis Fit Verdict (Strong / Moderate / Weak / No Fit)

**Verdict: Moderate** — fits the thesis but geography is borderline.
"""}}
    assert queries.thesis_verdict(deal) == "Moderate"


def test_thesis_verdict_handles_no_fit():
    deal = {"diligence": {"thesis_check": "Thesis Fit Verdict: No Fit — wrong stage."}}
    assert queries.thesis_verdict(deal) == "No Fit"


def test_thesis_verdict_missing_returns_none():
    assert queries.thesis_verdict({"diligence": {"thesis_check": ""}}) is None
    assert queries.thesis_verdict({"diligence": {}}) is None


# ─── scan_deals ──────────────────────────────────────────────────────────────

def test_scan_deals_empty_dir(deals_dir):
    assert queries.scan_deals() == []


def test_scan_deals_returns_summaries(deals_dir):
    d1 = _make_deal("Acme", owner_email="ada@example.com",
                    deal_stage="diligence", priority="H")
    _save(d1)
    d2 = _make_deal("Beta", owner_email="grace@example.com",
                    deal_stage="ic")
    _save(d2)

    summaries = queries.scan_deals()
    assert {s.deal_id for s in summaries} == {"Acme", "Beta"}

    acme = next(s for s in summaries if s.deal_id == "Acme")
    assert acme.owner_email == "ada@example.com"
    assert acme.deal_stage == "diligence"
    assert acme.priority == "H"
    assert acme.agents_total == 9


def test_scan_deals_ignores_jsonl_sidecar_files(deals_dir):
    _save(_make_deal("Acme"))
    # Drop sidecar and hidden files that must not be confused for deals
    (deals_dir / "Acme.runs.jsonl").write_text('{"x":1}\n')
    (deals_dir / "Acme.audit.jsonl").write_text('{"x":1}\n')
    (deals_dir / ".hidden.json").write_text("{}")

    summaries = queries.scan_deals()
    assert [s.deal_id for s in summaries] == ["Acme"]


def test_scan_deals_skips_corrupt_file(deals_dir):
    _save(_make_deal("Good"))
    (deals_dir / "Bad.json").write_text("{not valid json")

    summaries = queries.scan_deals()
    assert [s.deal_id for s in summaries] == ["Good"]


# ─── filter_deals ────────────────────────────────────────────────────────────

def _summaries_for_test():
    def s(deal_id, **kw):
        defaults = dict(
            deal_id=deal_id, company_name=deal_id,
            owner_email="ada@example.com", deal_stage="diligence",
            priority="M", sector="SaaS", collaborators=[],
        )
        defaults.update(kw)
        return queries.DealSummary(**defaults)

    return [
        s("Acme",    owner_email="ada@example.com",  deal_stage="diligence", priority="H",
          sector="Fintech"),
        s("Beta",    owner_email="grace@example.com", deal_stage="ic",        priority="H",
          collaborators=["ada@example.com"]),
        s("Gamma",   owner_email="mal@example.com",   deal_stage="passed",    priority="L"),
        s("Delta",   owner_email="grace@example.com", deal_stage="tracking",  priority=None),
        s("Epsilon", owner_email="unassigned",        deal_stage="contacted", priority="M"),
    ]


def test_filter_my_deals_covers_owner_and_collaborator():
    out = queries.filter_deals(_summaries_for_test(), my_email="ada@example.com")
    assert {s.deal_id for s in out} == {"Acme", "Beta"}


def test_filter_active_only():
    summaries = _summaries_for_test()
    # Mark Gamma inactive; all others active by default
    for s in summaries:
        if s.deal_id == "Gamma":
            s.is_active = False
    out = queries.filter_deals(summaries, active_only=True)
    assert "Gamma" not in {s.deal_id for s in out}


def test_filter_combines_criteria():
    summaries = _summaries_for_test()
    for s in summaries:
        if s.deal_id == "Delta":
            s.is_active = False
    out = queries.filter_deals(
        summaries,
        my_email="ada@example.com",
        active_only=True,
    )
    assert {s.deal_id for s in out} == {"Acme", "Beta"}


# ─── stalled_deals ───────────────────────────────────────────────────────────

def test_stalled_deals_uses_threshold_and_excludes_terminal():
    now = datetime(2026, 4, 18, tzinfo=timezone.utc)
    old = (now - timedelta(days=30)).isoformat()
    recent = (now - timedelta(days=2)).isoformat()

    summaries = [
        queries.DealSummary(deal_id="Stale",  company_name="Stale",
                            owner_email="a", deal_stage="diligence",
                            updated_at=old),
        queries.DealSummary(deal_id="Fresh",  company_name="Fresh",
                            owner_email="a", deal_stage="diligence",
                            updated_at=recent),
        queries.DealSummary(deal_id="OldPass", company_name="OldPass",
                            owner_email="a", deal_stage="passed",
                            updated_at=old),  # terminal -> not stalled
    ]
    stalled = queries.stalled_deals(summaries, threshold_days=14, now=now)
    assert [s.deal_id for s in stalled] == ["Stale"]


def test_stalled_skips_deals_with_missing_timestamp():
    summaries = [queries.DealSummary(
        deal_id="NoTs", company_name="NoTs", owner_email="a",
        deal_stage="diligence", updated_at="")]
    assert queries.stalled_deals(summaries) == []


# ─── summary_tiles ───────────────────────────────────────────────────────────

def test_summary_tiles_counts_deals_and_agents_run(deals_dir):
    # A: 2 agents done. B: 0 agents done. C: 9 agents done. Total = 3 deals, 11 agents.
    a = _make_deal("A")
    a["pre_call"]["research_output"] = "brief"
    a["diligence"]["tracker"] = "P1s"
    _save(a)

    _save(_make_deal("B"))

    c = _make_deal("C")
    c["pre_call"]["research_output"] = "brief"
    c["diligence"]["tracker"] = "P1s"
    c["diligence"]["founder_diligence"] = "notes"
    c["diligence"]["market_diligence"] = "notes"
    c["diligence"]["reference_check"] = "notes"
    c["diligence"]["thesis_check"] = "notes"
    c["ic_preparation"]["pre_mortem"] = "notes"
    c["ic_preparation"]["ic_simulation"] = "notes"
    c["ic_preparation"]["ic_memo"] = "memo"
    _save(c)

    tiles = queries.summary_tiles(queries.scan_deals())
    assert tiles == {"total_deals": 3, "total_agents_run": 11}
